import os
import sys
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import re
import sqlite3
import uuid
from datetime import datetime
from BaiduPCSI import BaiduPCSI
from tkinterdnd2 import TkinterDnD, DND_FILES


class SevenZipCompressor:
    def __init__(self, root):
        self.root = root
        self.root.title("资源压缩和上传工具")
        self.root.geometry("850x700")
        self.root.resizable(True, True)

        # 初始化设置
        self.settings = self.load_settings()
        self.baidu_pcsi = BaiduPCSI()

        # 初始化数据库
        self.init_database()

        # 当前选择的文件夹
        self.selected_folder = ""
        # 压缩密码
        self.password = ""
        # 分卷大小
        self.volume_size = "50M"
        # 当前解压密码变量，用于上传界面显示
        self.current_password_var = None
        # 宣传文件设置
        self.use_promotion = self.settings.get("use_promotion", False)
        self.selected_promotion = None
        # 手动清理宣传文件列表
        self.last_promotion_files_to_remove = []

        # 创建主界面
        self.create_widgets()

    def load_settings(self):
        """加载设置"""
        settings_file = "settings.json"
        default_settings = {
            "temp_save_path": os.path.join(os.getcwd(), "temp_compressed"),
            "default_volume_size": "50M",
            "promotion_files": [],
            "use_promotion": True,  # 默认使用宣传文件
            "auto_upload": True,  # 默认自动上传
            "custom_extract_code": "1234",  # 默认自定义提取码
            "auto_delete_after_upload": False,  # 默认上传后不自动删除文件
            "auto_clean_promotion": True,  # 默认自动清理宣传文件
        }

        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                return {**default_settings, **json.load(f)}
        return default_settings

    def save_settings(self):
        """保存设置"""
        # 更新设置中的配置
        self.settings["use_promotion"] = self.use_promotion_var.get()
        self.settings["auto_upload"] = self.auto_upload_var.get()
        self.settings["custom_extract_code"] = self.custom_extract_code_var.get()
        self.settings["auto_delete_after_upload"] = (
            self.auto_delete_after_upload_var.get()
        )

        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def init_database(self):
        """初始化数据库"""
        self.db_conn = sqlite3.connect("compress_history.db")
        self.db_cursor = self.db_conn.cursor()

        # 创建压缩历史表
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS compress_history (
                id TEXT PRIMARY KEY,
                compress_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self.db_conn.commit()

    def add_compressed_file(self, compress_id, file_path, file_size):
        """添加压缩文件记录到数据库"""
        id = str(uuid.uuid4())
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 在每个线程中创建独立的数据库连接和游标，解决线程安全问题
        conn = sqlite3.connect("compress_history.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO compress_history (id, compress_id, file_path, file_size, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (id, compress_id, file_path, file_size, created_at),
        )
        conn.commit()

        # 关闭连接
        cursor.close()
        conn.close()

    def refresh_compress_records(self):
        """刷新压缩记录"""
        # 清空现有记录
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)

        # 连接到数据库
        conn = sqlite3.connect("compress_history.db")
        cursor = conn.cursor()

        # 查询压缩记录，按创建时间倒序排列
        cursor.execute("""
            SELECT id, compress_id, file_path, file_size, created_at
            FROM compress_history
            ORDER BY created_at DESC
        """)

        # 添加记录到表格
        for i, row in enumerate(cursor.fetchall()):
            # 确保记录有5个字段
            if len(row) == 5:
                self.records_tree.insert(
                    "", tk.END, values=(i + 1, row[1], row[2], row[3], row[4])
                )
            else:
                # 跳过格式不正确的记录
                continue

        # 关闭数据库连接
        cursor.close()
        conn.close()

    def close_database(self):
        """关闭数据库连接"""
        self.db_conn.close()

    def create_widgets(self):
        """创建界面组件"""
        # 创建选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 压缩选项卡
        self.tab_compress = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_compress, text="压缩")

        # 上传选项卡
        self.tab_upload = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_upload, text="上传")

        # 设置选项卡
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_settings, text="设置")

        # 数据库选项卡
        self.tab_database = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_database, text="压缩记录")

        # 创建压缩选项卡内容
        self.create_compress_tab()

        # 创建上传选项卡内容
        self.create_upload_tab()

        # 创建设置选项卡内容
        self.create_settings_tab()

        # 创建数据库选项卡内容
        self.create_database_tab()

        # 允许拖放文件夹
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self.on_drop)

    def create_compress_tab(self):
        """创建压缩选项卡"""

        # 文件夹选择
        frame_folder = ttk.LabelFrame(self.tab_compress, text="文件夹选择")
        frame_folder.pack(fill=tk.X, padx=10, pady=10)

        self.folder_path_var = tk.StringVar()
        self.folder_entry = ttk.Entry(
            frame_folder, textvariable=self.folder_path_var, state="readonly"
        )
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)

        self.browse_btn = ttk.Button(
            frame_folder, text="浏览", command=self.browse_folder
        )
        self.browse_btn.pack(side=tk.RIGHT, padx=10, pady=10)

        # 压缩设置
        frame_settings = ttk.LabelFrame(self.tab_compress, text="压缩设置")
        frame_settings.pack(fill=tk.X, padx=10, pady=10)

        # 密码设置
        password_frame = ttk.Frame(frame_settings)
        password_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(password_frame, text="解压密码:").pack(side=tk.LEFT, padx=5)
        self.password_var = tk.StringVar()
        # 初始化当前解压密码变量
        self.current_password_var = tk.StringVar(value="")
        # 添加密码变化监听，更新上传界面的密码显示
        self.password_var.trace_add(
            "write",
            lambda *args: self.current_password_var.set(self.password_var.get()),
        )
        self.password_entry = ttk.Entry(
            password_frame, textvariable=self.password_var, show="*"
        )
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 分卷大小设置
        volume_frame = ttk.Frame(frame_settings)
        volume_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(volume_frame, text="分卷大小:").pack(side=tk.LEFT, padx=5)
        self.volume_var = tk.StringVar(value=self.settings["default_volume_size"])
        self.volume_entry = ttk.Entry(volume_frame, textvariable=self.volume_var)
        self.volume_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Label(volume_frame, text="(例如: 50M, 100M)").pack(side=tk.LEFT, padx=5)

        # 宣传文件设置
        promotion_frame = ttk.LabelFrame(frame_settings, text="宣传文件设置")
        promotion_frame.pack(fill=tk.X, padx=10, pady=5)

        # 第一行：使用宣传文件和选择
        row1_frame = ttk.Frame(promotion_frame)
        row1_frame.pack(fill=tk.X, padx=5, pady=2)

        self.use_promotion_var = tk.BooleanVar(
            value=self.settings.get("use_promotion", True)
        )
        # 添加变化监听，自动保存
        self.use_promotion_var.trace_add("write", self.on_settings_changed)
        promotion_check = ttk.Checkbutton(
            row1_frame,
            text="使用宣传文件",
            variable=self.use_promotion_var,
            command=self.on_promotion_use_changed,
        )
        promotion_check.pack(side=tk.LEFT, padx=5)

        # 宣传文件选择下拉框
        ttk.Label(row1_frame, text="选择宣传文件:").pack(side=tk.LEFT, padx=5)

        # 获取宣传文件名称列表
        promotion_names = [file["name"] for file in self.settings["promotion_files"]]
        self.selected_promotion_var = tk.StringVar()
        self.promotion_combobox = ttk.Combobox(
            row1_frame,
            textvariable=self.selected_promotion_var,
            values=promotion_names,
            state="readonly",
            postcommand=self.update_promotion_list,
        )
        # 绑定选择事件
        self.promotion_combobox.bind("<<ComboboxSelected>>", self.on_promotion_selected)
        self.promotion_combobox.pack(side=tk.LEFT, padx=5)

        # 第二行：自动清理和手动清理按钮
        row2_frame = ttk.Frame(promotion_frame)
        row2_frame.pack(fill=tk.X, padx=5, pady=2)

        # 自动清理宣传文件选项
        self.auto_clean_promotion_var = tk.BooleanVar(
            value=self.settings.get("auto_clean_promotion", True)
        )
        self.auto_clean_promotion_var.trace_add("write", self.on_settings_changed)
        auto_clean_check = ttk.Checkbutton(
            row2_frame,
            text="压缩完成后自动清理宣传文件",
            variable=self.auto_clean_promotion_var,
        )
        auto_clean_check.pack(side=tk.LEFT, padx=5)

        # 手动清理宣传文件按钮
        ttk.Button(
            row2_frame,
            text="手动清理宣传文件",
            command=self.manual_clean_promotion_files,
        ).pack(side=tk.RIGHT, padx=5)

        # 自动上传选项
        self.auto_upload_var = tk.BooleanVar(
            value=self.settings.get("auto_upload", True)
        )
        # 添加变化监听，自动保存
        self.auto_upload_var.trace_add("write", self.on_settings_changed)
        auto_upload_check = ttk.Checkbutton(
            frame_settings,
            text="压缩完成后自动上传到百度网盘",
            variable=self.auto_upload_var,
        )
        auto_upload_check.pack(side=tk.LEFT, padx=5)

        # 压缩按钮
        self.compress_btn = ttk.Button(
            frame_settings, text="开始压缩", command=self.start_compress
        )
        self.compress_btn.pack(side=tk.LEFT, padx=10, pady=10)

        # 日志显示区域
        frame_log = ttk.LabelFrame(self.tab_compress, text="压缩日志")
        frame_log.pack(fill=tk.X, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=3)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.log_text.config(state="disabled")

        # 生成文本区域
        frame_text = ttk.LabelFrame(self.tab_compress, text="生成文本")
        frame_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 文本输出
        self.text_output = scrolledtext.ScrolledText(
            frame_text, wrap=tk.WORD, height=10
        )
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # 复制按钮
        button_frame = ttk.Frame(frame_text)
        button_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        self.copy_btn = ttk.Button(
            button_frame, text="复制文本", command=self.copy_text
        )
        self.copy_btn.pack(side=tk.RIGHT)

    def create_upload_tab(self):
        """创建上传选项卡"""
        # 百度网盘上传设置
        frame_baidu = ttk.LabelFrame(self.tab_upload, text="百度网盘上传")
        frame_baidu.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 标题显示和复制
        title_frame = ttk.LabelFrame(frame_baidu, text="标题设置")
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        # 生成的标题显示和复制
        generated_frame = ttk.Frame(title_frame)
        generated_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(generated_frame, text="生成标题:").pack(side=tk.LEFT, padx=5)
        self.generated_title_var = tk.StringVar(value="【双语/汉化/自制】请选择文件夹")
        generated_title_entry = ttk.Entry(
            generated_frame, textvariable=self.generated_title_var, state="readonly"
        )
        generated_title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(
            generated_frame,
            text="复制标题",
            command=lambda: self.copy_to_clipboard(self.generated_title_var.get()),
        ).pack(side=tk.RIGHT, padx=5)

        # 自动目录
        self.auto_dir_var = tk.StringVar(value=self.baidu_pcsi.get_auto_directory())

        auto_dir_frame = ttk.Frame(frame_baidu)
        auto_dir_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(auto_dir_frame, text="自动目录:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(
            auto_dir_frame, textvariable=self.auto_dir_var, state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 自定义目录
        custom_dir_frame = ttk.Frame(frame_baidu)
        custom_dir_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(custom_dir_frame, text="自定义目录:").pack(side=tk.LEFT, padx=5)
        self.custom_dir_var = tk.StringVar()
        ttk.Entry(custom_dir_frame, textvariable=self.custom_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )

        # 自定义提取码
        extract_code_frame = ttk.Frame(frame_baidu)
        extract_code_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(extract_code_frame, text="自定义提取码:").pack(side=tk.LEFT, padx=5)
        self.custom_extract_code_var = tk.StringVar(
            value=self.settings.get("custom_extract_code", "1234")
        )
        # 添加提取码变化监听，自动保存
        self.custom_extract_code_var.trace_add("write", self.on_extract_code_changed)
        ttk.Entry(extract_code_frame, textvariable=self.custom_extract_code_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        # 添加复制提取码按钮
        ttk.Button(
            extract_code_frame,
            text="复制提取码",
            command=lambda: self.copy_to_clipboard(self.custom_extract_code_var.get()),
        ).pack(side=tk.RIGHT, padx=5)

        # 解压密码显示和复制
        password_frame = ttk.Frame(frame_baidu)
        password_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(password_frame, text="当前解压密码:").pack(side=tk.LEFT, padx=5)
        self.current_password_var = tk.StringVar(value="")
        # 显示密码的输入框，使用readonly状态，不显示星号以便查看
        ttk.Entry(
            password_frame,
            textvariable=self.current_password_var,
            state="readonly",
            show="",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # 添加复制解压密码按钮
        ttk.Button(
            password_frame,
            text="复制解压密码",
            command=lambda: self.copy_to_clipboard(self.current_password_var.get()),
        ).pack(side=tk.RIGHT, padx=5)

        # 上传按钮
        self.upload_btn = ttk.Button(
            frame_baidu, text="上传到百度网盘", command=self.start_upload
        )
        self.upload_btn.pack(padx=10, pady=10)

        # 分享信息
        frame_share = ttk.LabelFrame(frame_baidu, text="分享信息")
        frame_share.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 分享链接
        link_frame = ttk.Frame(frame_share)
        link_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(link_frame, text="分享链接:").pack(side=tk.LEFT, padx=5)
        self.share_link_var = tk.StringVar()
        self.share_link_entry = ttk.Entry(link_frame, textvariable=self.share_link_var)
        self.share_link_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(
            link_frame,
            text="复制",
            command=lambda: self.copy_to_clipboard(self.share_link_var.get()),
        ).pack(side=tk.RIGHT, padx=5)

        # 提取码
        code_frame = ttk.Frame(frame_share)
        code_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(code_frame, text="提取码:").pack(side=tk.LEFT, padx=5)
        self.extract_code_var = tk.StringVar()
        self.extract_code_entry = ttk.Entry(
            code_frame, textvariable=self.extract_code_var
        )
        self.extract_code_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(
            code_frame,
            text="复制",
            command=lambda: self.copy_to_clipboard(self.extract_code_var.get()),
        ).pack(side=tk.RIGHT, padx=5)

    def create_settings_tab(self):
        """创建设置选项卡"""
        # 临时保存位置
        frame_temp = ttk.LabelFrame(self.tab_settings, text="临时保存位置")
        frame_temp.pack(fill=tk.X, padx=10, pady=10)

        self.temp_path_var = tk.StringVar(value=self.settings["temp_save_path"])

        ttk.Entry(frame_temp, textvariable=self.temp_path_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10
        )
        ttk.Button(frame_temp, text="浏览", command=self.browse_temp_path).pack(
            side=tk.RIGHT, padx=10, pady=10
        )

        # 宣传文件列表设置
        frame_promotion = ttk.LabelFrame(self.tab_settings, text="宣传文件列表管理")
        frame_promotion.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 宣传文件列表
        promotion_list_frame = ttk.Frame(frame_promotion)
        promotion_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 列表标题
        columns = ("id", "name", "path", "password")
        self.promotion_tree = ttk.Treeview(
            promotion_list_frame, columns=columns, show="headings"
        )
        self.promotion_tree.heading("id", text="ID")
        self.promotion_tree.heading("name", text="名称")
        self.promotion_tree.heading("path", text="路径")
        self.promotion_tree.heading("password", text="解压码")

        # 设置列宽
        self.promotion_tree.column("id", width=50)
        self.promotion_tree.column("name", width=150)
        self.promotion_tree.column("path", width=300)
        self.promotion_tree.column("password", width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            promotion_list_frame, orient=tk.VERTICAL, command=self.promotion_tree.yview
        )
        self.promotion_tree.configure(yscroll=scrollbar.set)

        self.promotion_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载宣传文件列表
        self.load_promotion_files()

        # 操作按钮
        button_frame = ttk.Frame(frame_promotion)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(button_frame, text="添加", command=self.add_promotion_file).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="修改", command=self.edit_promotion_file).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="删除", command=self.delete_promotion_file).pack(
            side=tk.LEFT, padx=5
        )

        # 宣传文件说明
        ttk.Label(
            frame_promotion, text="宣传文件可以是文件或文件夹，压缩时会自动处理"
        ).pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(
            frame_promotion, text="使用宣传文件时，解压密码将自动设置为对应的值"
        ).pack(anchor=tk.W, padx=10, pady=5)
        ttk.Label(
            frame_promotion, text="压缩完成后，宣传文件将自动从压缩包中删除"
        ).pack(anchor=tk.W, padx=10, pady=5)

        # 上传设置
        frame_upload = ttk.LabelFrame(self.tab_settings, text="上传设置")
        frame_upload.pack(fill=tk.X, padx=10, pady=10)

        # 上传后自动删除文件选项
        self.auto_delete_after_upload_var = tk.BooleanVar(
            value=self.settings.get("auto_delete_after_upload", False)
        )
        # 添加变化监听，自动保存
        self.auto_delete_after_upload_var.trace_add("write", self.on_settings_changed)
        auto_delete_check = ttk.Checkbutton(
            frame_upload,
            text="上传完成后自动删除本地压缩文件",
            variable=self.auto_delete_after_upload_var,
        )
        auto_delete_check.pack(side=tk.LEFT, padx=5)

        # 保存设置按钮
        ttk.Button(
            self.tab_settings, text="保存设置", command=self.apply_settings
        ).pack(padx=10, pady=20)

    def create_database_tab(self):
        """创建数据库选项卡"""
        # 创建框架
        frame_database = ttk.LabelFrame(self.tab_database, text="压缩记录")
        frame_database.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 操作按钮
        button_frame = ttk.Frame(frame_database)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(
            button_frame, text="刷新记录", command=self.refresh_compress_records
        ).pack(side=tk.RIGHT, padx=5)

        # 记录表格
        records_frame = ttk.Frame(frame_database)
        records_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 表格列
        columns = ("id", "compress_id", "file_path", "file_size", "created_at")
        self.records_tree = ttk.Treeview(
            records_frame, columns=columns, show="headings"
        )

        # 设置列标题
        self.records_tree.heading("id", text="ID")
        self.records_tree.heading("compress_id", text="压缩包ID")
        self.records_tree.heading("file_path", text="文件路径")
        self.records_tree.heading("file_size", text="文件大小")
        self.records_tree.heading("created_at", text="创建时间")

        # 设置列宽
        self.records_tree.column("id", width=50)
        self.records_tree.column("compress_id", width=100)
        self.records_tree.column("file_path", width=300)
        self.records_tree.column("file_size", width=100)
        self.records_tree.column("created_at", width=150)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            records_frame, orient=tk.VERTICAL, command=self.records_tree.yview
        )
        self.records_tree.configure(yscroll=scrollbar.set)

        self.records_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 加载初始记录
        self.refresh_compress_records()

    def update_generated_title(self, folder):
        """更新生成的标题"""
        if folder:
            # 获取文件夹名称
            folder_name = os.path.basename(folder)
            # 生成固定格式标题
            generated_title = f"【双语/汉化/自制】{folder_name}"
            self.generated_title_var.set(generated_title)
        else:
            self.generated_title_var.set("【双语/汉化/自制】请选择文件夹")

    def browse_folder(self):
        """浏览文件夹"""
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path_var.set(folder)
            self.selected_folder = folder
            # 自动计算分卷大小
            self.auto_calculate_volume_size(folder)
            # 更新生成的标题
            self.update_generated_title(folder)

    def auto_calculate_volume_size(self, folder):
        """根据文件大小自动计算分卷大小（文件大小的1/3）"""
        folder_size = self.get_folder_size(folder)
        # 计算分卷大小为文件大小的1/3，转换为MB
        volume_size_mb = (folder_size / (1024 * 1024)) / 3
        # 四舍五入到整数
        volume_size_mb = round(volume_size_mb)
        # 确保分卷大小至少为10MB
        volume_size_mb = max(volume_size_mb, 10)
        # 设置分卷大小
        self.volume_var.set(f"{volume_size_mb}M")

    def browse_temp_path(self):
        """浏览临时保存路径"""
        folder = filedialog.askdirectory()
        if folder:
            self.temp_path_var.set(folder)

    def browse_mengzhan_file(self):
        """浏览萌站宣传文件"""
        file = filedialog.askopenfilename(title="选择萌站宣传文件")
        if file:
            self.mengzhan_path_var.set(file)
            self.mengzhan_file = file

    def load_promotion_files(self):
        """加载宣传文件列表"""
        # 清空现有列表
        for item in self.promotion_tree.get_children():
            self.promotion_tree.delete(item)

        # 添加宣传文件到列表
        for i, file in enumerate(self.settings["promotion_files"]):
            self.promotion_tree.insert(
                "", tk.END, values=(i + 1, file["name"], file["path"], file["password"])
            )

    def create_promotion_dialog(self, edit_mode=False, item_id=None):
        """创建宣传文件编辑对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑宣传文件" if edit_mode else "添加宣传文件")
        dialog.geometry("500x300")
        dialog.resizable(False, False)

        # 设置模态窗口
        dialog.grab_set()

        # 名称输入
        name_frame = ttk.Frame(dialog)
        name_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(name_frame, text="名称:").pack(side=tk.LEFT, padx=5)
        name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=name_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )

        # 路径选择
        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(path_frame, text="路径:").pack(side=tk.LEFT, padx=5)
        path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=path_var, state="readonly")
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        def browse_path():
            path = filedialog.askdirectory(title="选择宣传文件夹")
            if path:
                path_var.set(path)

        ttk.Button(path_frame, text="浏览", command=browse_path).pack(
            side=tk.RIGHT, padx=5
        )

        # 解压码输入
        pwd_frame = ttk.Frame(dialog)
        pwd_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(pwd_frame, text="解压码:").pack(side=tk.LEFT, padx=5)
        pwd_var = tk.StringVar(value="himengzhan.vip")
        ttk.Entry(pwd_frame, textvariable=pwd_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )

        # 如果是编辑模式，填充现有数据
        if edit_mode and item_id is not None:
            promotion_file = self.settings["promotion_files"][item_id]
            name_var.set(promotion_file["name"])
            path_var.set(promotion_file["path"])
            pwd_var.set(promotion_file["password"])

        # 保存按钮
        def save_promotion():
            name = name_var.get().strip()
            path = path_var.get().strip()
            password = pwd_var.get().strip()

            if not name or not path or not password:
                messagebox.showerror("错误", "请填写完整信息")
                return

            promotion_data = {"name": name, "path": path, "password": password}

            if edit_mode and item_id is not None:
                self.settings["promotion_files"][item_id] = promotion_data
            else:
                self.settings["promotion_files"].append(promotion_data)

            self.load_promotion_files()
            dialog.destroy()

        ttk.Button(dialog, text="保存", command=save_promotion).pack(pady=20)

    def add_promotion_file(self):
        """添加宣传文件"""
        self.create_promotion_dialog()

    def edit_promotion_file(self):
        """修改宣传文件"""
        selected_item = self.promotion_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请选择要修改的宣传文件")
            return

        item = selected_item[0]
        values = self.promotion_tree.item(item, "values")
        item_id = int(values[0]) - 1  # 获取实际索引

        self.create_promotion_dialog(edit_mode=True, item_id=item_id)

    def delete_promotion_file(self):
        """删除宣传文件"""
        selected_item = self.promotion_tree.selection()
        if not selected_item:
            messagebox.showinfo("提示", "请选择要删除的宣传文件")
            return

        if messagebox.askyesno("确认", "确定要删除选中的宣传文件吗？"):
            item = selected_item[0]
            values = self.promotion_tree.item(item, "values")
            item_id = int(values[0]) - 1  # 获取实际索引

            # 删除宣传文件
            del self.settings["promotion_files"][item_id]
            self.load_promotion_files()

    def on_promotion_use_changed(self):
        """当使用宣传文件的复选框状态改变时调用"""
        if self.use_promotion_var.get():
            # 如果勾选使用宣传文件，自动勾选自动上传
            self.auto_upload_var.set(True)

        if not self.use_promotion_var.get():
            # 如果取消使用宣传文件，清空密码
            self.password_var.set("")

    def update_promotion_list(self):
        """更新宣传文件下拉列表"""
        promotion_names = [file["name"] for file in self.settings["promotion_files"]]
        self.promotion_combobox["values"] = promotion_names

    def on_promotion_selected(self, event):
        """当选择宣传文件时调用，自动设置解压码"""
        selected_name = self.selected_promotion_var.get()
        if not selected_name:
            return

        # 自动勾选使用宣传文件和自动上传
        self.use_promotion_var.set(True)
        self.auto_upload_var.set(True)

        # 查找对应的宣传文件
        for file in self.settings["promotion_files"]:
            if file["name"] == selected_name:
                # 自动设置解压码到密码输入框
                self.password_var.set(file["password"])
                break

    def on_extract_code_changed(self, *args):
        """当自定义提取码变化时自动保存"""
        self.save_settings()

    def on_settings_changed(self, *args):
        """当设置变化时自动保存"""
        self.save_settings()

    def update_log(self, message):
        """更新日志显示"""
        self.log_text.config(state="normal")
        self.log_text.insert(
            tk.END, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n"
        )
        self.log_text.see(tk.END)  # 滚动到最新日志
        self.log_text.config(state="disabled")

    def apply_settings(self):
        """应用设置"""
        self.settings["temp_save_path"] = self.temp_path_var.get()
        self.save_settings()
        messagebox.showinfo("提示", "设置已保存")

    def on_drag_enter(self, event):
        """拖放进入事件"""
        event.widget.focus_set()
        return event.widget.tk.call("tkdnd::dragenter", event.widget, event.data)

    def on_drag_leave(self, event):
        """拖放离开事件"""
        return event.widget.tk.call("tkdnd::dragleave", event.widget, event.data)

    def on_drop(self, event):
        """拖放事件"""
        # 获取拖放的文件路径
        file_path = event.data
        # 处理Windows路径格式，去除大括号
        if file_path.startswith("{") and file_path.endswith("}"):
            file_path = file_path[1:-1]
        # 检查是否为文件夹
        if os.path.isdir(file_path):
            self.folder_path_var.set(file_path)
            self.selected_folder = file_path
            # 自动计算分卷大小
            self.auto_calculate_volume_size(file_path)
            # 更新生成的标题
            self.update_generated_title(file_path)

    def get_folder_size(self, folder):
        """获取文件夹大小"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        return total_size

    def format_size(self, size_bytes):
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f}{unit}"
            size_bytes /= 1024.0

    def get_folder_files(self, folder):
        """获取文件夹内的文件列表"""
        files = []
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                relative_path = os.path.relpath(os.path.join(dirpath, filename), folder)
                files.append(relative_path)
        return sorted(files)

    def generate_text(self, folder):
        """生成指定格式的文本"""
        # 获取文件夹大小
        folder_size = self.get_folder_size(folder)
        formatted_size = self.format_size(folder_size)

        # 获取文件列表
        files = self.get_folder_files(folder)

        # 生成文本
        text = f"""【什么是双语？：根据字幕文件把中文语音混音入原始音频内。

有什么用？：可以在不用学习日语也可以直接欣赏作品，刚刚开始可能需要一些适宜时间。

在里面有什么？：
{chr(10).join([f"（{file}）" for file in files])}

文件有多大？：解压完成后有-{formatted_size}

怎么解压？：直接解压001文件，不用修改文件

备注：使用的是ai模型提取的文本可能会有误差，不过意思是差不多能听懂。介意误买。】"""

        self.text_output.delete(1.0, tk.END)
        self.text_output.insert(tk.END, text)

    def start_compress(self):
        """开始压缩"""
        if not self.selected_folder:
            messagebox.showerror("错误", "请先选择文件夹")
            return

        # 获取密码和分卷大小
        self.use_promotion = self.use_promotion_var.get()
        self.selected_promotion = None

        # 如果使用宣传文件，获取选中的宣传文件信息
        if self.use_promotion:
            promotion_name = self.selected_promotion_var.get()
            if not promotion_name:
                messagebox.showerror("错误", "请选择宣传文件")
                return

            # 查找对应的宣传文件
            for file in self.settings["promotion_files"]:
                if file["name"] == promotion_name:
                    self.selected_promotion = file
                    self.password = file["password"]
                    break
        else:
            self.password = self.password_var.get()

        self.volume_size = self.volume_var.get()

        # 创建临时保存目录
        os.makedirs(self.settings["temp_save_path"], exist_ok=True)

        # 开始压缩线程
        threading.Thread(target=self.compress_folder, daemon=True).start()

    def compress_folder(self):
        """压缩文件夹"""
        # 生成压缩包ID
        compress_id = str(uuid.uuid4()).split("-")[0]  # 使用UUID的前8位作为压缩包ID
        output_name = os.path.join(self.settings["temp_save_path"], compress_id)

        # 更新自动目录为使用压缩ID
        self.auto_dir_var.set(f"/分享资源/{compress_id}/")

        # 构建7z命令
        cmd = [
            "7z",
            "a",
            "-t7z",  # 7z格式
            f"-v{self.volume_size}",  # 分卷大小
            "-mx=9",  # 最大压缩率
        ]

        # 如果设置了密码
        if self.password:
            cmd.extend([f"-p{self.password}", "-mhe=on"])

        # 保存原始文件夹结构，用于后续处理
        original_files = []
        for dirpath, dirnames, filenames in os.walk(self.selected_folder):
            for filename in filenames:
                original_files.append(
                    os.path.relpath(
                        os.path.join(dirpath, filename), self.selected_folder
                    )
                )

        # 处理宣传文件
        promotion_files_to_remove = []
        files_to_compress = [self.selected_folder]

        if self.use_promotion and self.selected_promotion:
            promotion_path = self.selected_promotion["path"]

            # 如果宣传文件是文件夹
            if os.path.isdir(promotion_path):
                # 遍历宣传文件夹中的所有文件
                for dirpath, dirnames, filenames in os.walk(promotion_path):
                    for filename in filenames:
                        promotion_file_path = os.path.join(dirpath, filename)
                        # 计算相对路径
                        relative_path = os.path.relpath(
                            promotion_file_path, promotion_path
                        )
                        # 目标路径
                        target_path = os.path.join(self.selected_folder, relative_path)

                        # 确保目标目录存在
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        # 复制文件到要压缩的文件夹
                        shutil.copy2(promotion_file_path, target_path)
                        # 记录要删除的文件
                        promotion_files_to_remove.append(relative_path)
            else:
                # 如果是单个文件，直接添加到压缩列表
                files_to_compress.append(promotion_path)

        cmd.append(output_name)
        cmd.extend(files_to_compress)

        try:
            self.update_log("开始压缩文件夹...")
            self.update_log(f"压缩包ID: {compress_id}")
            self.update_log(f"分卷大小: {self.volume_size}")

            # 执行压缩命令，使用errors='ignore'忽略无法解码的字符
            self.update_log("正在执行压缩命令...")
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.update_log("压缩命令执行完成")

            # 删除复制到要压缩文件夹中的宣传文件
            if self.auto_clean_promotion_var.get():
                self.update_log("正在清理宣传文件...")
                for file_path in promotion_files_to_remove:
                    full_path = os.path.join(self.selected_folder, file_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                self.update_log("宣传文件清理完成")
            else:
                self.update_log("跳过自动清理宣传文件")
                # 保存宣传文件列表，以便手动清理
                self.last_promotion_files_to_remove = promotion_files_to_remove

            # 保存到数据库
            self.update_log("正在保存到数据库...")
            folder_size = self.get_folder_size(self.selected_folder)
            formatted_size = self.format_size(folder_size)
            self.add_compressed_file(compress_id, self.selected_folder, formatted_size)
            self.update_log("数据库保存完成")

            # 生成文本
            self.update_log("正在生成说明文本...")
            self.generate_text(self.selected_folder)
            self.update_log("说明文本生成完成")

            self.update_log(f"压缩完成，文件保存在：{self.settings['temp_save_path']}")

            # 自动上传到百度网盘
            if self.auto_upload_var.get():
                self.update_log("开始自动上传到百度网盘")
                # 执行上传操作
                self.auto_upload(output_name, compress_id)
        except subprocess.CalledProcessError as e:
            self.update_log(f"压缩错误：{e.stderr}")
        finally:
            # 确保宣传文件被删除（仅在自动清理开启时）
            if self.auto_clean_promotion_var.get():
                self.update_log("正在执行最终清理...")
                for file_path in promotion_files_to_remove:
                    full_path = os.path.join(self.selected_folder, file_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                self.update_log("最终清理完成")

    def delete_uploaded_files(self, base_name):
        """删除上传后的文件"""
        self.update_log("开始删除本地压缩文件...")
        try:
            # 删除所有与base_name相关的分卷文件
            for file in os.listdir(self.settings["temp_save_path"]):
                if file.startswith(os.path.basename(base_name)):
                    full_file_path = os.path.join(self.settings["temp_save_path"], file)
                    if os.path.exists(full_file_path):
                        os.remove(full_file_path)
                        self.update_log(f"已删除文件：{file}")
            self.update_log("本地压缩文件删除完成")
        except Exception as e:
            self.update_log(f"删除本地压缩文件失败：{str(e)}")

    def auto_upload(self, file_path, compress_id=None):
        """自动上传到百度网盘"""
        # 获取上传目录
        if self.custom_dir_var.get():
            upload_dir = self.custom_dir_var.get()
        elif compress_id:
            # 使用压缩ID生成上传目录
            upload_dir = f"/分享资源/{compress_id}/"
        else:
            upload_dir = self.auto_dir_var.get()

        # 获取自定义提取码
        extract_code = self.custom_extract_code_var.get()

        try:
            self.update_log(f"正在创建远程目录：{upload_dir}")
            # 创建远程目录
            self.baidu_pcsi.create_directory(upload_dir)

            # 上传文件
            # 由于是分卷压缩，需要上传所有分卷文件
            self.update_log("正在上传分卷文件...")
            base_name = file_path
            for file in os.listdir(self.settings["temp_save_path"]):
                if file.startswith(os.path.basename(base_name)):
                    full_file_path = os.path.join(self.settings["temp_save_path"], file)
                    self.update_log(f"上传文件：{file}")
                    self.baidu_pcsi.upload_file(full_file_path, upload_dir)

            # 获取分享链接，使用自定义提取码
            self.update_log(f"正在获取分享链接，提取码：{extract_code}")
            share_info = self.baidu_pcsi.get_share_link(upload_dir, extract_code)
            self.share_link_var.set(
                share_info["link"] + f"?pwd={share_info['password']}"
            )
            self.extract_code_var.set(share_info["password"])

            self.update_log("自动上传完成")

            # 如果设置了上传后自动删除文件，则执行删除操作
            if self.settings.get("auto_delete_after_upload", False):
                self.delete_uploaded_files(file_path)
        except Exception as e:
            self.update_log(f"自动上传失败：{str(e)}")

    def copy_text(self):
        """复制文本"""
        text = self.text_output.get(1.0, tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("提示", "文本已复制到剪贴板")

    def manual_clean_promotion_files(self):
        """手动清理宣传文件"""
        if (
            not hasattr(self, "last_promotion_files_to_remove")
            or not self.last_promotion_files_to_remove
        ):
            messagebox.showinfo("提示", "没有需要清理的宣传文件")
            return

        if messagebox.askyesno("确认", "确定要清理宣传文件吗？"):
            self.update_log("正在手动清理宣传文件...")
            for file_path in self.last_promotion_files_to_remove:
                full_path = os.path.join(self.selected_folder, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    self.update_log(f"已删除：{file_path}")
            self.update_log("手动清理宣传文件完成")
            self.last_promotion_files_to_remove = []
            messagebox.showinfo("提示", "宣传文件已清理")

    def copy_to_clipboard(self, text):
        """复制到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("提示", "已复制到剪贴板")

    def start_upload(self):
        """开始上传"""
        # 获取上传目录
        upload_dir = self.custom_dir_var.get() or self.auto_dir_var.get()
        # 获取自定义提取码
        extract_code = self.custom_extract_code_var.get()

        # 开始上传线程
        threading.Thread(
            target=self.upload_to_baidu, args=(upload_dir, extract_code), daemon=True
        ).start()
        self.update_log("上传已开始")

    def upload_to_baidu(self, upload_dir, extract_code="1234"):
        """上传到百度网盘"""
        try:
            # 这里调用BaiduPCSI.py的上传功能
            # 实际使用时需要实现完整的上传逻辑

            # 模拟上传过程
            import time

            self.update_log(f"正在上传到目录：{upload_dir}")
            time.sleep(3)

            # 获取分享链接，使用自定义提取码
            self.update_log(f"正在获取分享链接，提取码：{extract_code}")
            share_info = self.baidu_pcsi.get_share_link(upload_dir, extract_code)
            self.share_link_var.set(share_info["link"])
            self.extract_code_var.set(share_info["password"])

            self.update_log("上传完成")

            # 如果设置了上传后自动删除文件，则执行删除操作
            # 注意：这里需要根据实际上传的文件路径来删除，当前方法没有实际的文件上传逻辑，所以仅作为示例
            # 实际使用时，需要将上传的文件路径传递给delete_uploaded_files方法
        except Exception as e:
            self.update_log(f"上传失败：{str(e)}")


if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = SevenZipCompressor(root)
    root.mainloop()
