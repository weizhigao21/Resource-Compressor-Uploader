import subprocess
import os
import datetime
import re


class BaiduPCSI:
    def __init__(self):
        self.pcs_command = "BaiduPCS-Py"

    def get_auto_directory(self, compress_id=None):
        """获取自动目录"""
        if compress_id:
            return f"/分享资源/{compress_id}/"
        else:
            now = datetime.datetime.now()
            return f"/分享资源/{now.strftime('%Y-%m-%d')}/"

    def upload_file(self, local_path, remote_path):
        """上传文件到百度网盘"""
        remote_dir = remote_path.rstrip("/")
        command = [
            self.pcs_command,
            "upload",
            local_path,
            remote_dir,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=3600,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            # 检查输出中是否包含失败关键词
            output = result.stdout + result.stderr
            if (
                "ERROR" in output
                or "error" in output
                or "失败" in output
                or "failed" in output.lower()
            ):
                print(f"上传失败：{output}")
                return False
            else:
                print("上传成功！")
                return True

        except subprocess.TimeoutExpired:
            print("上传超时，文件可能较大")
            return False
        except Exception as e:
            print(f"上传异常：{e}")
            return False

    def create_directory(self, remote_path):
        """创建远程目录"""
        command = [self.pcs_command, "mkdir", remote_path]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"创建目录异常：{e}")
            return False

    def get_share_link(self, remote_path, password="1234"):
        """获取分享链接和提取码"""
        try:
            share_result = run_share_command(remote_path, password)

            if share_result:
                full_link = share_result[0]
                if "?pwd=" in full_link:
                    link, pwd_part = full_link.split("?pwd=", 1)
                    share_password = pwd_part
                else:
                    link = full_link
                    share_password = password

                return {"link": link, "password": share_password}
            else:
                print("获取分享链接失败")
                return {
                    "link": "https://pan.baidu.com/s/1example",
                    "password": password,
                }
        except Exception as e:
            print(f"获取分享链接异常：{e}")
            return {"link": "https://pan.baidu.com/s/1example", "password": password}


def run_share_command(remote_path, password):
    """使用 BaiduPCS-Py 创建分享链接"""
    command = ["BaiduPCS-Py", "share", remote_path, "-p", password]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output = result.stdout + result.stderr

        # 匹配百度网盘链接
        url_pattern = r"https://pan\.baidu\.com/s/[a-zA-Z0-9_-]+"
        urls = re.findall(url_pattern, output)

        if urls:
            share_url = urls[0]
            # 检查是否已有密码参数
            if "?pwd=" in share_url:
                print(f"分享成功！{share_url}")
                return [share_url]
            else:
                full_url = f"{share_url}?pwd={password}"
                print(f"分享成功！{full_url}")
                return [full_url]
        else:
            print("分享失败：无法从输出中提取分享链接")
            return None

    except subprocess.TimeoutExpired:
        print("命令执行超时")
        return None
    except Exception as e:
        print(f"执行命令时发生异常: {e}")
        return None


def run_save_command(remote_url, path, password):
    """保存分享链接到指定目录"""
    command = ["BaiduPCS-Py", "save", remote_url, path, "-p", password]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output = result.stdout + result.stderr
        if "ERROR" in output or "error" in output:
            print(f"保存失败：{output}")
            return False
        else:
            print("保存成功！")
            return True

    except subprocess.TimeoutExpired:
        print("命令执行超时")
        return False
    except Exception as e:
        print(f"执行命令时发生异常: {e}")
        return False


def run_save_command_upload(path, path_bd):
    """上传文件到百度网盘"""
    remote_dir = path_bd.rstrip("/")

    command = ["BaiduPCS-Py", "upload", path, remote_dir]

    print("开始上传文件")
    print(f"上传命令: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=3600,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        output = result.stdout + result.stderr
        if "ERROR" in output or "error" in output or "失败" in output:
            print(f"上传失败：{output}")
            return False
        else:
            print("上传成功！")
            return True

    except subprocess.TimeoutExpired:
        print("命令执行超时，文件可能较大，上传仍在进行中")
        return False
    except FileNotFoundError:
        print("错误：未找到 BaiduPCS-Py 命令，请确保已正确安装")
        return False
    except Exception as e:
        print(f"执行命令时发生异常: {e}")
        return False
