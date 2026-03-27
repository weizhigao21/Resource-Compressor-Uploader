import subprocess
import os
import datetime


class ShareInfoParser:
    def __init__(self, text):
        self.text = text
        self.data = self.parse()

    def parse(self):
        data = {}
        lines = self.text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("+") or line == "STDOUT:":
                continue

            if line.startswith("|") and line.endswith("|"):
                content = line[1:-1].strip()
                if ":" in content:
                    key, value = content.split(":", 1)
                    data[key.strip()] = value.strip()

        return data

    def get_share_id(self):
        return self.data.get("share id")

    def get_shared_url(self):
        return self.data.get("shared url")

    def get_password(self):
        return self.data.get("password")

    def get_paths(self):
        return self.data.get("paths")

    def get_valid_period(self):
        return self.data.get("valid period")


class BaiduPCSI:
    def __init__(self):
        self.pcs_command = "BaiduPCS-Go"

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
            "--policy=rsync",
            "--norapid",
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
                "以下文件上传失败" in output
                or "获取文件列表错误" in output
                or "上传失败" in output
            ):
                print(f"上传失败：{output}")
                return False
            elif result.returncode == 0:
                return True
            else:
                print(f"上传失败：{result.stderr}")
                return False
        except Exception as e:
            print(f"上传异常：{e}")
            return False

    def create_directory(self, remote_path):
        """创建远程目录"""
        command = [self.pcs_command, "mkdir", "-p", remote_path]

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
            # 使用run_share_command函数获取分享链接
            share_result = run_share_command(remote_path, password)

            if share_result:
                full_link = share_result[0]
                # 解析分享链接，提取link和password
                # 格式：https://pan.baidu.com/s/1example?pwd=1234
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
    command = ["BaiduPCS-Go", "share", remote_path, "--access-code", password]

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

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        output = result.stdout + result.stderr

        if result.returncode == 0 or "分享成功" in output or "pan.baidu.com" in output:
            # 从输出中提取分享链接
            import re

            # 匹配百度网盘链接
            url_pattern = r"https://pan\.baidu\.com/s/[a-zA-Z0-9_-]+"
            urls = re.findall(url_pattern, output)

            if urls:
                share_url = urls[0]
                print(f"分享成功！{share_url}?pwd={password}")
                return [f"{share_url}?pwd={password}"]
            else:
                print("分享失败：无法从输出中提取分享链接")
                return None
        else:
            print("分享失败！")
            return None

    except subprocess.TimeoutExpired:
        print("命令执行超时")
        return None
    except Exception as e:
        print(f"执行命令时发生异常: {e}")
        return None


def run_save_command(remote_url, path, password):
    command = f'BaiduPCS-Py save "{remote_url}" "{path}" -p "{password}"'

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

        # 打印标准输出和标准错误
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return Code:", result.returncode)

        if result.returncode == 1:
            print("保存成功！")

        else:
            print("保存失败！")

    except subprocess.TimeoutExpired:
        print("命令执行超时")
    except Exception as e:
        print(f"执行命令时发生异常: {e}")


def run_save_command_upload(path, path_bd):
    # 确保路径格式正确 # 构建本地路径
    remote_dir = path_bd.rstrip("/")  # 清理远程目录路径

    # 构建命令 - 注意：根据您实际安装的包名，可能是 'baidupcs-py' 或 'BaiduPCS-Py'
    command = ["BaiduPCS-Go", "upload", path, remote_dir, "--policy=rsync", "--norapid"]

    print("开始上传文件")
    print(f"上传命令: {' '.join(command)}")

    try:
        # 使用列表形式传递命令，避免shell注入风险
        # 移除timeout或设置更长的超时时间，因为文件上传可能需要很长时间
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",  # 显式指定UTF-8编码
            errors="ignore",  # 忽略无法解码的字符
            timeout=3600,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # 打印详细输出信息
        # print("STDOUT:", result.stdout)
        # print("STDERR:", result.stderr)
        # print("Return Code:", result.returncode)

        # 修正逻辑：通常返回码0表示成功，非0表示失败
        if result.returncode == 0:
            print("上传成功！")
            return True
        else:
            print("上传失败！")
            # 可以添加更详细的错误处理
            if "BDUSS" in result.stderr or "login" in result.stderr.lower():
                print("错误：可能需要重新登录，请检查BDUSS是否有效")
            return False

    except subprocess.TimeoutExpired:
        print("命令执行超时，文件可能较大，上传仍在进行中")
        return False
    except FileNotFoundError:
        print("错误：未找到 baidupcs-py 命令，请确保已正确安装")
        return False
    except Exception as e:
        print(f"执行命令时发生异常: {e}")
        return False


# 使用示例
# run_share_command("/qrudpkk4/2288691", "8888")

# run_save_command('https://pan.baidu.com/s/1BB7Gvn0usbnkzG7YcTy6QQ','/qrudpkk4/2288692','1234')
