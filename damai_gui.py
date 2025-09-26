# -*- coding: utf-8 -*-
"""
大麦抢票 GUI 工具
一键式图形界面抢票工具，适合小白用户使用
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import subprocess
import sys
import os
import json
import re
import time
import webbrowser
import pickle
from pathlib import Path
import importlib.util
import shutil
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

# 确保能够导入selenium等模块
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# 导入App端运行器（如果可用）
try:
    from damai_appium import (
        AppTicketConfig,
        ConfigValidationError,
        DamaiAppTicketRunner,
        FailureReason,
        LogLevel,
        TicketRunReport,
    )
    from damai_appium.config import AdbDeviceInfo, parse_adb_devices

    APPIUM_AVAILABLE = True
except Exception:  # noqa: BLE001
    AppTicketConfig = None  # type: ignore[assignment]
    ConfigValidationError = None  # type: ignore[assignment]
    DamaiAppTicketRunner = None  # type: ignore[assignment]
    LogLevel = None  # type: ignore[assignment]
    FailureReason = None  # type: ignore[assignment]
    TicketRunReport = None  # type: ignore[assignment]
    AdbDeviceInfo = None  # type: ignore[assignment]
    parse_adb_devices = None  # type: ignore[assignment]
    APPIUM_AVAILABLE = False


class DamaiGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("大麦抢票工具 v3.0.0")
        self.root.geometry("1200x800")  # 调整为适中的尺寸比例
        self.root.resizable(True, True)
        
        # 设置最小窗口尺寸
        self.root.minsize(1000, 650)
        
        # 设置图标（如果有的话）
        try:
            self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 初始化变量
        self.driver = None
        self.target_url = ""
        self.is_grabbing = False  # 抢票状态标志
        self.config = {
            "city": "",
            "date": "",
            "price": "",
            "users": ["自动选择全部"],
            "if_commit_order": False
        }

        # 模式管理：web / app
        self.mode_var = tk.StringVar(value="web")
        self.steps_config = {
            "web": [
                "1. 环境检测",
                "2. 网页登录",
                "3. 页面分析",
                "4. 参数配置",
                "5. 开始抢票",
            ],
            "app": [
                "1. 环境检测",
                "2. 设备检查",
                "3. 参数配置",
                "4. 开始抢票",
                "5. 查看结果",
            ],
        }
        self.step_status = []
        self.app_config_data = {}
        self.app_loaded_config = None
        self.app_env_ready = False
        self.app_config_ready = False
        self.app_should_stop = False
        self.app_detected_devices: List[str] = []
        self.app_detected_device_records: List[Dict[str, Any]] = []
        self._device_refresh_in_progress = False
        self.app_device_status_var: Optional[tk.StringVar] = None
        self.app_device_detail_var: Optional[tk.StringVar] = None
        self.app_device_options_var: Optional[tk.StringVar] = None
        self.app_device_combobox: Optional[ttk.Combobox] = None
        self.log_entries = []  # type: List[Tuple[str, str, str]]
        self._last_config_errors: List[str] = []
        self.last_app_report = None
        self.log_filter_var = tk.StringVar(value="全部")
        self.app_runner_thread: Optional[threading.Thread] = None
        self._init_app_form_vars()
        self.app_metrics_var = tk.StringVar(value="尚未运行 App 抢票流程")
        
        # Cookie管理
        self.cookie_file = "damai_cookies.pkl"
        self.last_cookie_save = time.time()  # 记录上次保存cookie的时间
        
        # 设置字体 - 增加两个号
        self.default_font = ("微软雅黑", 12)  # 从10增加到12
        self.title_font = ("微软雅黑", 18, "bold")  # 从16增加到18
        self.button_font = ("微软雅黑", 11)  # 从9增加到11
        
        # 配置默认字体
        self.root.option_add("*Font", self.default_font)
        
        # 创建主界面
        self.create_interface()
        
        # 初始环境检测
        if not SELENIUM_AVAILABLE:
            self.log("⚠️ 警告：selenium模块未安装，部分功能可能无法使用")
    
    def save_cookies(self):
        """保存当前浏览器的cookies到文件"""
        try:
            if self.driver:
                cookies = self.driver.get_cookies()
                with open(self.cookie_file, 'wb') as f:
                    pickle.dump(cookies, f)
                self.last_cookie_save = time.time()  # 更新保存时间
                self.log("✅ Cookie已保存，下次启动时将自动登录")
                return True
        except Exception as e:
            self.log(f"❌ Cookie保存失败: {e}")
        return False
    
    def auto_save_cookies_if_needed(self):
        """如果需要，自动保存cookies（每5分钟保存一次）"""
        try:
            current_time = time.time()
            # 如果距离上次保存超过5分钟，就自动保存
            if self.driver and (current_time - self.last_cookie_save > 300):  # 300秒 = 5分钟
                if self.save_cookies():
                    self.log("🔄 自动保存Cookie（定期保存）")
        except Exception as e:
            self.log(f"⚠️ 自动保存Cookie失败: {e}")
        
        # 设置下次检查（30秒后）
        self.root.after(30000, self.auto_save_cookies_if_needed)
    
    def load_cookies(self):
        """从文件加载cookies到浏览器"""
        try:
            if os.path.exists(self.cookie_file) and self.driver:
                with open(self.cookie_file, 'rb') as f:
                    cookies = pickle.load(f)
                
                # 先访问大麦网主页
                self.driver.get("https://www.damai.cn")
                time.sleep(2)
                
                # 添加所有cookies
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        # 某些cookie可能已过期或无效，忽略错误
                        continue
                
                # 刷新页面使cookies生效
                self.driver.refresh()
                time.sleep(2)
                
                # 检查是否登录成功
                if self.check_login_status():
                    self.log("✅ 自动登录成功，使用已保存的登录状态")
                    return True
                else:
                    self.log("⚠️ Cookie已过期，需要重新登录")
                    self.clear_cookies()
                    
        except Exception as e:
            self.log(f"⚠️ Cookie加载失败: {e}")
        return False
    
    def check_login_status(self):
        """检查当前是否已登录"""
        try:
            if not self.driver:
                return False
                
            # 检查是否有登录标识元素
            login_indicators = [
                ".login-after",  # 登录后显示的元素
                ".user-info",    # 用户信息
                ".user-name",    # 用户名
                "[class*='login-after']",
                "[class*='user']"
            ]
            
            for selector in login_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(elem.is_displayed() for elem in elements):
                        return True
                except:
                    continue
            
            # 检查是否还有"登录"按钮
            login_buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), '登录') or contains(text(), '登陆')]")
            if not login_buttons:  # 没有登录按钮说明已经登录
                return True
                
            return False
            
        except Exception as e:
            self.log(f"登录状态检查失败: {e}")
            return False
    
    def clear_cookies(self):
        """清除保存的cookies"""
        try:
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
                self.log("✅ Cookie已清除")
            if self.driver:
                self.driver.delete_all_cookies()
        except Exception as e:
            self.log(f"Cookie清除失败: {e}")
            
    def run(self):
        """启动GUI"""
        self.root.mainloop()
        
    def create_interface(self):
        """创建主界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="🎫 大麦抢票工具", font=self.title_font)
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # 步骤显示区域
        self.create_steps_frame(main_frame, row=1)
        
        # 主要功能区域
        self.create_main_functions(main_frame, row=2)
        
        # 控制按钮区域
        self.create_control_buttons(main_frame, row=3)

        # 根据默认模式刷新界面
        self.switch_mode()
        
    def create_steps_frame(self, parent, row):
        """创建步骤显示框架"""
        steps_frame = ttk.LabelFrame(parent, text="📋 操作步骤", padding="10")
        steps_frame.grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 10))
        
        self.step_labels = []
        max_steps = max(len(steps) for steps in self.steps_config.values())
        for i in range(max_steps):
            label = ttk.Label(steps_frame, text="", foreground="gray", font=self.default_font)
            label.grid(row=0, column=i * 2, padx=5)
            self.step_labels.append(label)

            if i < max_steps - 1:
                sep = ttk.Label(steps_frame, text="→", foreground="gray", font=self.default_font)
                sep.grid(row=0, column=i * 2 + 1, padx=3)

        self.refresh_steps()
    
    def refresh_steps(self):
        """根据当前模式刷新步骤显示"""
        current_mode = self.mode_var.get()
        current_steps = self.steps_config.get(current_mode, [])
        self.steps = current_steps

        # 重置状态并更新标签文本
        self.step_status = ["inactive"] * len(self.step_labels)
        for idx, label in enumerate(self.step_labels):
            if idx < len(current_steps):
                label.config(text=current_steps[idx], foreground="gray")
            else:
                label.config(text="", foreground="gray")

    def create_main_functions(self, parent, row):
        """创建主要功能区域"""
        # 左侧功能面板
        left_frame = ttk.LabelFrame(parent, text="🔧 功能面板", padding="10")
        left_frame.grid(row=row, column=0, sticky="nsew", padx=(0, 5))
        
        # 环境检测区域
        env_frame = ttk.LabelFrame(left_frame, text="环境检测", padding="5")
        env_frame.pack(fill="x", pady=(0, 10))
        
        self.env_status_label = ttk.Label(env_frame, text="点击检测环境", foreground="orange", font=self.default_font)
        self.env_status_label.pack()
        
        self.check_env_btn = ttk.Button(env_frame, text="🔍 检测环境", command=self.check_environment)
        self.check_env_btn.pack(pady=5)

        # 模式面板容器
        self._setup_mode_notebook_style()
        self.mode_notebook = ttk.Notebook(left_frame, style="Mode.TNotebook")
        self.mode_notebook.pack(fill="both", expand=True, pady=(0, 10))

        self.web_panel = ttk.Frame(self.mode_notebook)
        self.app_panel = ttk.Frame(self.mode_notebook)

        self._build_web_panel(self.web_panel)
        self._build_app_panel(self.app_panel)

        self.mode_notebook.add(
            self.web_panel,
            text="🌐 网页模式",
            padding=(14, 8, 14, 8),
        )
        self.mode_notebook.add(
            self.app_panel,
            text="📱 App 模式",
            padding=(14, 8, 14, 8),
        )
        self.mode_notebook.bind("<<NotebookTabChanged>>", self._on_mode_tab_changed)
        
        # 右侧信息面板 - 改为运行日志
        right_frame = ttk.LabelFrame(parent, text="📝 运行日志", padding="10")
        right_frame.grid(row=row, column=1, sticky="nsew", padx=(5, 0))
        
        log_toolbar = ttk.Frame(right_frame)
        log_toolbar.pack(fill="x", pady=(0, 6))

        ttk.Label(log_toolbar, text="筛选：", font=self.button_font).pack(side="left")
        filter_values = ("全部", "仅信息", "仅成功", "仅警告", "仅错误")
        self.log_filter_combo = ttk.Combobox(
            log_toolbar,
            textvariable=self.log_filter_var,
            values=filter_values,
            state="readonly",
            width=10,
        )
        self.log_filter_combo.current(0)
        self.log_filter_combo.pack(side="left", padx=(4, 10))
        self.log_filter_combo.bind("<<ComboboxSelected>>", self._on_log_filter_changed)

        clear_btn = ttk.Button(log_toolbar, text="🧹 清空日志", command=self.clear_logs)
        clear_btn.pack(side="right")
        export_btn = ttk.Button(log_toolbar, text="💾 导出日志", command=self.export_logs)
        export_btn.pack(side="right", padx=(0, 6))

        metrics_frame = ttk.LabelFrame(right_frame, text="📊 运行统计", padding="6")
        metrics_frame.pack(fill="x", pady=(0, 6))
        self.metrics_label = ttk.Label(
            metrics_frame,
            textvariable=self.app_metrics_var,
            justify="left",
            font=self.default_font,
        )
        self.metrics_label.pack(anchor="w", fill="x")

        self.log_text = scrolledtext.ScrolledText(right_frame, height=15, width=40, font=self.default_font)
        self.log_text.pack(fill="both", expand=True)
        
        # 初始日志
        self.log("🚀 大麦抢票工具启动成功")
        self.log("💡 提示：请先检测环境，然后根据模式完成参数配置")
        self.log("ℹ️ 登录为可选项，可在抢票时再进行登录")
        
        # 启动定期保存cookie功能
        self.root.after(30000, self.auto_save_cookies_if_needed)  # 30秒后开始第一次检查
        
    def _build_web_panel(self, container: ttk.Frame) -> None:
        """构建网页模式下的控制面板"""

        url_frame = ttk.LabelFrame(container, text="演出链接", padding="5")
        url_frame.pack(fill="x", pady=(0, 10))

        self.url_entry = ttk.Entry(url_frame, width=50, font=self.default_font)
        self.url_entry.pack(fill="x", pady=2)
        self.url_entry.insert(0, "请输入大麦网演出详情页链接...")
        self.url_entry.bind("<FocusIn>", self.clear_url_placeholder)

        url_buttons_frame = ttk.Frame(url_frame)
        url_buttons_frame.pack(fill="x", pady=5)

        self.login_btn = ttk.Button(
            url_buttons_frame,
            text="🔐 网页登录",
            command=self.web_login,
            state="disabled",
        )
        self.login_btn.pack(side="left", padx=(0, 5))

        self.analyze_btn = ttk.Button(
            url_buttons_frame,
            text="🔍 分析页面",
            command=self.analyze_page,
            state="disabled",
        )
        self.analyze_btn.pack(side="left")

        config_frame = ttk.LabelFrame(container, text="抢票配置", padding="5")
        config_frame.pack(fill="x", pady=(0, 10))

        self.config_label = ttk.Label(
            config_frame,
            text="请先分析页面",
            foreground="gray",
            font=self.default_font,
        )
        self.config_label.pack()

    def _init_app_form_vars(self) -> None:
        """初始化 App 模式表单变量"""

        self.app_form_vars: dict[str, Any] = {
            "server_url": tk.StringVar(value="http://127.0.0.1:4723"),
            "keyword": tk.StringVar(value=""),
            "city": tk.StringVar(value=""),
            "date": tk.StringVar(value=""),
            "price": tk.StringVar(value=""),
            "price_index": tk.StringVar(value=""),
            "wait_timeout": tk.StringVar(value="2.0"),
            "retry_delay": tk.StringVar(value="2.0"),
            "device_name": tk.StringVar(value=""),
            "platform_version": tk.StringVar(value=""),
            "udid": tk.StringVar(value=""),
            "automation_name": tk.StringVar(value=""),
            "if_commit_order": tk.BooleanVar(value=True),
        }

        def _binding_callback(*_args: Any) -> None:
            self._on_app_form_changed()

        for key, var in self.app_form_vars.items():
            if isinstance(var, (tk.StringVar, tk.BooleanVar)):
                var.trace_add("write", _binding_callback)

        self.app_users_text = None
        self.app_form_entries: dict[str, tk.Widget] = {}

    def _build_app_panel(self, container: ttk.Frame) -> None:
        """构建App模式下的控制面板"""

        container.columnconfigure(0, weight=1)

        scroll_container = ttk.Frame(container)
        scroll_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(scroll_container, borderwidth=0, highlightthickness=0)
        v_scroll = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=v_scroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        content = ttk.Frame(canvas)
        content.columnconfigure(0, weight=1)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def _sync_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _expand_canvas(event: tk.Event) -> None:  # type: ignore[override]
            canvas.itemconfigure(content_window, width=event.width)

        content.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _expand_canvas)

        info_frame = ttk.Frame(content)
        info_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(
            info_frame,
            text="通过 Appium 控制大麦 App 自动抢票",
            font=self.default_font,
            wraplength=320,
            justify="left",
        ).pack(anchor="w")

        if not APPIUM_AVAILABLE:
            ttk.Label(
                info_frame,
                text="⚠️ 未检测到 Appium 运行环境，请先安装依赖",
                foreground="red",
                wraplength=320,
                justify="left",
            ).pack(anchor="w", pady=(5, 0))

        config_file_frame = ttk.LabelFrame(content, text="配置文件", padding="5")
        config_file_frame.pack(fill="x", pady=(0, 10))

        default_path = self._get_default_app_config_path()
        self.app_config_path_var = tk.StringVar(value=default_path or "")

        path_entry = ttk.Entry(
            config_file_frame,
            textvariable=self.app_config_path_var,
            font=self.default_font,
        )
        path_entry.pack(fill="x", pady=2)

        btn_row = ttk.Frame(config_file_frame)
        btn_row.pack(fill="x", pady=2)

        ttk.Button(btn_row, text="📂 选择文件", command=self.select_app_config).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(btn_row, text="🔄 重新加载", command=self.load_app_config).pack(side="left")

        ttk.Button(btn_row, text="📘 配置说明", command=self.open_app_docs).pack(side="right")

        params_frame = ttk.LabelFrame(content, text="运行参数", padding="5")
        params_frame.pack(fill="x", pady=(0, 10))

        self.app_retries_var = tk.IntVar(value=2)
        ttk.Label(params_frame, text="最大重试次数:").grid(row=0, column=0, sticky="w")
        retries_spin = ttk.Spinbox(
            params_frame,
            from_=1,
            to=10,
            textvariable=self.app_retries_var,
            width=5,
        )
        retries_spin.grid(row=0, column=1, sticky="w", padx=(5, 0))

        self.app_config_status = ttk.Label(
            params_frame,
            text="尚未加载配置",
            foreground="gray",
        )
        self.app_config_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        device_frame = ttk.LabelFrame(content, text="设备状态", padding="5")
        device_frame.pack(fill="x", pady=(0, 10))

        device_header = ttk.Frame(device_frame)
        device_header.pack(fill="x")

        self.app_device_status_var = tk.StringVar(value="尚未检测设备")
        self.app_device_status_label = ttk.Label(
            device_header,
            textvariable=self.app_device_status_var,
            foreground="gray",
        )
        self.app_device_status_label.pack(side="left", expand=True, fill="x")

        self.app_device_refresh_btn = ttk.Button(
            device_header,
            text="🔄 刷新设备",
            command=self._refresh_devices_clicked,
        )
        self.app_device_refresh_btn.pack(side="right")

        options_row = ttk.Frame(device_frame)
        options_row.pack(fill="x", pady=(6, 0))

        ttk.Label(options_row, text="选择设备：").pack(side="left")
        self.app_device_options_var = tk.StringVar(value="")
        self.app_device_combobox = ttk.Combobox(
            options_row,
            textvariable=self.app_device_options_var,
            state="disabled",
            width=36,
        )
        self.app_device_combobox.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.app_device_combobox.bind("<<ComboboxSelected>>", self._on_device_selection_changed)

        default_device_hint = "点击“刷新设备”或执行环境检测查看最新状态。"
        self.app_device_detail_var = tk.StringVar(value=default_device_hint)
        self.app_device_detail_label = ttk.Label(
            device_frame,
            textvariable=self.app_device_detail_var,
            wraplength=420,
            justify="left",
            foreground="gray",
        )
        self.app_device_detail_label.pack(anchor="w", pady=(4, 0))

        if not (APPIUM_AVAILABLE and parse_adb_devices is not None):
            self.app_device_refresh_btn.config(state="disabled")
            if not APPIUM_AVAILABLE:
                unsupported_hint = "当前环境未启用 Appium，安装完成后可刷新设备列表。"
            else:
                unsupported_hint = "缺少 adb 解析能力，安装 damai_appium 依赖后重启程序。"
            self.app_device_detail_var.set(unsupported_hint)
            self.app_device_detail_label.config(foreground="red")
            if self.app_device_combobox is not None:
                self.app_device_combobox.config(state="disabled")

        form_frame = ttk.LabelFrame(content, text="图形化配置", padding="5")
        form_frame.pack(fill="both", expand=True, pady=(0, 10))
        self._create_app_form_fields(form_frame)

        advanced_body = self._create_collapsible_section(
            content,
            title="高级选项",
            description="调整自动提交、超时重试等高级参数，默认保持推荐值即可。",
            initially_open=False,
        )
        self._create_app_advanced_fields(advanced_body)

        self.app_form_status_label = ttk.Label(
            content,
            text="⬆️ 请完善以上参数后即可启动",
            foreground="gray",
        )
        self.app_form_status_label.pack(anchor="w", pady=(0, 10))

        summary_frame = ttk.LabelFrame(content, text="配置摘要", padding="5")
        summary_frame.pack(fill="both", expand=True)

        self.app_summary_text = tk.Text(
            summary_frame,
            height=10,
            wrap="word",
            bg=self.root.cget("bg"),
            relief="flat",
            font=self.default_font,
        )
        self.app_summary_text.pack(fill="both", expand=True)
        self.app_summary_text.insert(tk.END, "请在左侧表单填写 Appium 配置，完成后将在此展示摘要。")
        self.app_summary_text.config(state="disabled")

    def _create_app_form_fields(self, container: ttk.LabelFrame) -> None:
        """创建 App 模式基础配置表单"""

        form = ttk.Frame(container)
        form.pack(fill="both", expand=True)
        for col in range(4):
            form.columnconfigure(col, weight=1 if col in (1, 3) else 0)

        ttk.Label(form, text="Appium 服务地址").grid(row=0, column=0, sticky="w", pady=2)
        server_entry = ttk.Entry(form, textvariable=self.app_form_vars["server_url"], width=35)
        server_entry.grid(row=0, column=1, columnspan=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["server_url"] = server_entry

        ttk.Label(form, text="设备名称").grid(row=1, column=0, sticky="w", pady=2)
        device_entry = ttk.Entry(form, textvariable=self.app_form_vars["device_name"], width=24)
        device_entry.grid(row=1, column=1, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["device_name"] = device_entry

        ttk.Label(form, text="设备 UDID").grid(row=1, column=2, sticky="w", pady=2)
        udid_entry = ttk.Entry(form, textvariable=self.app_form_vars["udid"], width=24)
        udid_entry.grid(row=1, column=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["udid"] = udid_entry

        ttk.Label(form, text="系统版本").grid(row=2, column=0, sticky="w", pady=2)
        version_entry = ttk.Entry(form, textvariable=self.app_form_vars["platform_version"], width=24)
        version_entry.grid(row=2, column=1, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["platform_version"] = version_entry

        ttk.Label(form, text="关键词").grid(row=2, column=2, sticky="w", pady=2)
        keyword_entry = ttk.Entry(form, textvariable=self.app_form_vars["keyword"], width=24)
        keyword_entry.grid(row=2, column=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["keyword"] = keyword_entry

        ttk.Label(form, text="城市").grid(row=3, column=0, sticky="w", pady=2)
        city_entry = ttk.Entry(form, textvariable=self.app_form_vars["city"], width=24)
        city_entry.grid(row=3, column=1, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["city"] = city_entry

        ttk.Label(form, text="日期").grid(row=3, column=2, sticky="w", pady=2)
        date_entry = ttk.Entry(form, textvariable=self.app_form_vars["date"], width=24)
        date_entry.grid(row=3, column=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["date"] = date_entry

        ttk.Label(form, text="票价文本").grid(row=4, column=0, sticky="w", pady=2)
        price_entry = ttk.Entry(form, textvariable=self.app_form_vars["price"], width=24)
        price_entry.grid(row=4, column=1, columnspan=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["price"] = price_entry

        ttk.Label(form, text="观演人（每行一个）").grid(row=5, column=0, sticky="nw", pady=2)
        self.app_users_text = scrolledtext.ScrolledText(form, height=4, wrap="word", font=self.default_font)
        self.app_users_text.grid(row=5, column=1, columnspan=3, sticky="we", padx=(5, 0), pady=2)
        self.app_users_text.bind("<<Modified>>", self._on_app_users_modified)

        ttk.Label(
            form,
            text="提示：如需多人抢票，可填写多行观演人姓名；留空将沿用配置文件或默认值。",
            foreground="gray",
            wraplength=420,
            justify="left",
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(2, 0))

        self._update_app_summary_from_form()

    def _create_app_advanced_fields(self, container: ttk.Frame) -> None:
        """创建 App 模式高级配置字段"""

        container.columnconfigure(1, weight=1)
        container.columnconfigure(3, weight=1)

        ttk.Label(container, text="AutomationName").grid(row=0, column=0, sticky="w", pady=2)
        auto_entry = ttk.Entry(container, textvariable=self.app_form_vars["automation_name"], width=24)
        auto_entry.grid(row=0, column=1, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["automation_name"] = auto_entry

        ttk.Label(container, text="票价索引").grid(row=0, column=2, sticky="w", pady=2)
        price_index_entry = ttk.Entry(container, textvariable=self.app_form_vars["price_index"], width=24)
        price_index_entry.grid(row=0, column=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["price_index"] = price_index_entry

        ttk.Label(container, text="等待超时(s)").grid(row=1, column=0, sticky="w", pady=2)
        wait_entry = ttk.Entry(container, textvariable=self.app_form_vars["wait_timeout"], width=24)
        wait_entry.grid(row=1, column=1, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["wait_timeout"] = wait_entry

        ttk.Label(container, text="重试间隔(s)").grid(row=1, column=2, sticky="w", pady=2)
        retry_entry = ttk.Entry(container, textvariable=self.app_form_vars["retry_delay"], width=24)
        retry_entry.grid(row=1, column=3, sticky="we", padx=(5, 0), pady=2)
        self.app_form_entries["retry_delay"] = retry_entry

        ttk.Label(container, text="自动提交订单").grid(row=2, column=0, sticky="w", pady=2)
        commit_check = ttk.Checkbutton(
            container,
            text="完成下单流程后自动提交",
            variable=self.app_form_vars["if_commit_order"],
            onvalue=True,
            offvalue=False,
        )
        commit_check.grid(row=2, column=1, columnspan=3, sticky="w", pady=2)
        self.app_form_entries["if_commit_order"] = commit_check

        ttk.Label(
            container,
            text="如需保留默认行为，可不用修改此处配置。",
            foreground="gray",
            wraplength=420,
            justify="left",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(2, 0))

    def _create_collapsible_section(
        self,
        parent: ttk.Frame,
        title: str,
        description: Optional[str] = None,
        initially_open: bool = False,
    ) -> ttk.Frame:
        """创建可折叠的配置面板并返回内容容器"""

        section = ttk.Frame(parent)
        section.pack(fill="x", pady=(0, 10))

        state_text = tk.StringVar()

        body = ttk.Frame(section)

        def _open() -> None:
            body.pack(fill="both", expand=True, pady=(6, 0))
            state_text.set(f"▼ {title}")

        def _close() -> None:
            body.pack_forget()
            state_text.set(f"▶ {title}")

        def _toggle() -> None:
            if body.winfo_ismapped():
                _close()
            else:
                _open()

        toggle_btn = ttk.Button(
            section,
            textvariable=state_text,
            command=_toggle,
            style="Toolbutton",
        )
        toggle_btn.pack(fill="x")

        if initially_open:
            _open()
        else:
            _close()

        if description:
            ttk.Label(
                body,
                text=description,
                foreground="gray",
                wraplength=420,
                justify="left",
            ).pack(anchor="w", pady=(0, 6))

        content_frame = ttk.Frame(body)
        content_frame.pack(fill="both", expand=True)

        toggle_btn.bind("<Return>", lambda _event: _toggle())
        toggle_btn.bind("<space>", lambda _event: _toggle())

        if not hasattr(self, "_collapsible_controls"):
            self._collapsible_controls: list[tuple[ttk.Button, ttk.Frame]] = []
        self._collapsible_controls.append((toggle_btn, body))

        return content_frame

    def _setup_mode_notebook_style(self) -> None:
        """初始化 Notebook 标签的样式与状态颜色"""

        style = ttk.Style(self.root)
        base_bg = self.root.cget("background")

        style.configure("Mode.TNotebook", background=base_bg, borderwidth=0)
        style.configure(
            "Mode.TNotebook.Tab",
            padding=(14, 6),
            font=self.default_font,
            foreground="#1F2937",
        )
        style.map(
            "Mode.TNotebook.Tab",
            background=[("selected", "#DBEAFE"), ("!selected", "#E2E8F0")],
            foreground=[("selected", "#1E3A8A"), ("!selected", "#1F2937")],
        )

    def _on_app_users_modified(self, event):  # type: ignore[override]
        if not getattr(event.widget, "edit_modified", None):
            return
        event.widget.edit_modified(False)
        self._on_app_form_changed()

    def _on_app_form_changed(self, *_args: Any) -> None:
        self.app_config_ready = self._validate_app_form()
        self._update_app_summary_from_form()
        self._refresh_app_start_button()

    def _refresh_app_start_button(self) -> None:
        if not hasattr(self, "start_btn"):
            return
        if self.mode_var.get() != "app":
            return
        state = "normal" if (self.app_env_ready and self.app_config_ready) else "disabled"
        self.start_btn.config(state=state)

    def _validate_app_form(self, update_label: bool = True) -> bool:
        config = self._collect_app_config_from_form(strict=False)
        errors = list(self._last_config_errors)

        ready = config is not None and not errors

        if update_label and hasattr(self, "app_form_status_label"):
            if errors:
                self.app_form_status_label.config(text=" ❌ " + errors[0], foreground="red")
            else:
                status = "✅ 配置已就绪" if ready else "⬆️ 请完善以上参数后即可启动"
                color = "green" if ready else "gray"
                self.app_form_status_label.config(text=status, foreground=color)

        if update_label and hasattr(self, "app_config_status"):
            if errors:
                self.app_config_status.config(text="配置不完整", foreground="red")
            else:
                status_text = "配置已就绪" if ready else "尚未完成配置"
                status_color = "green" if ready else "gray"
                self.app_config_status.config(text=status_text, foreground=status_color)

        return ready

    def _update_app_summary_from_form(self) -> None:
        if not hasattr(self, "app_summary_text"):
            return

        if AppTicketConfig is None:
            self.app_summary_text.config(state="normal")
            self.app_summary_text.delete("1.0", tk.END)
            self.app_summary_text.insert(tk.END, "当前环境未启用 Appium，请先安装相关依赖。")
            self.app_summary_text.config(state="disabled")
            return

        config = self._collect_app_config_from_form(strict=False)
        self._set_app_summary_text(config)

    def _populate_app_form(self, config: Any) -> None:
        if not config:
            return

        self.app_form_vars["server_url"].set(getattr(config, "server_url", ""))
        self.app_form_vars["keyword"].set(getattr(config, "keyword", "") or "")
        self.app_form_vars["city"].set(getattr(config, "city", "") or "")
        self.app_form_vars["date"].set(getattr(config, "date", "") or "")
        self.app_form_vars["price"].set(getattr(config, "price", "") or "")

        price_index = getattr(config, "price_index", None)
        self.app_form_vars["price_index"].set("" if price_index is None else str(price_index))

        self.app_form_vars["wait_timeout"].set(str(getattr(config, "wait_timeout", 2.0)))
        self.app_form_vars["retry_delay"].set(str(getattr(config, "retry_delay", 2.0)))
        self.app_form_vars["if_commit_order"].set(bool(getattr(config, "if_commit_order", True)))

        device_caps = getattr(config, "device_caps", {}) or {}
        self.app_form_vars["device_name"].set(device_caps.get("deviceName", ""))
        self.app_form_vars["platform_version"].set(device_caps.get("platformVersion", ""))
        self.app_form_vars["udid"].set(device_caps.get("udid", ""))
        self.app_form_vars["automation_name"].set(device_caps.get("automationName", ""))

        if self.app_users_text is not None:
            self.app_users_text.delete("1.0", tk.END)
            users = getattr(config, "users", []) or []
            if users:
                self.app_users_text.insert(tk.END, "\n".join(users))

        self._on_app_form_changed()

    def _build_app_config_payload(self, *, strict: bool) -> Dict[str, Any]:
        base_config = self.app_loaded_config
        payload: Dict[str, Any] = {}
        if base_config is not None:
            try:
                payload.update(asdict(base_config))
            except Exception:
                payload.update(
                    {
                        "server_url": getattr(base_config, "server_url", ""),
                        "keyword": getattr(base_config, "keyword", None),
                        "users": list(getattr(base_config, "users", []) or []),
                        "city": getattr(base_config, "city", None),
                        "date": getattr(base_config, "date", None),
                        "price": getattr(base_config, "price", None),
                        "price_index": getattr(base_config, "price_index", None),
                        "if_commit_order": getattr(base_config, "if_commit_order", True),
                        "device_caps": dict(getattr(base_config, "device_caps", {}) or {}),
                        "wait_timeout": getattr(base_config, "wait_timeout", 2.0),
                        "retry_delay": getattr(base_config, "retry_delay", 2.0),
                    }
                )

        server_url_raw = self.app_form_vars["server_url"].get().strip()
        if server_url_raw:
            payload["server_url"] = server_url_raw
        elif "server_url" not in payload:
            payload["server_url"] = ""

        for key in ("keyword", "city", "date", "price"):
            value = self.app_form_vars[key].get().strip()
            payload[key] = value or None

        price_index_raw = self.app_form_vars["price_index"].get().strip()
        if price_index_raw:
            payload["price_index"] = price_index_raw
        elif base_config is not None:
            payload["price_index"] = getattr(base_config, "price_index", None)
        else:
            payload["price_index"] = None

        payload["if_commit_order"] = bool(self.app_form_vars["if_commit_order"].get())

        users = self._get_users_from_widget()
        if users:
            payload["users"] = users
        elif base_config is None:
            payload["users"] = list(payload.get("users", []) or [])
        else:
            payload["users"] = list(getattr(base_config, "users", []) or [])

        wait_timeout_raw = self.app_form_vars["wait_timeout"].get().strip()
        if wait_timeout_raw:
            payload["wait_timeout"] = wait_timeout_raw
        elif base_config is not None:
            payload["wait_timeout"] = getattr(base_config, "wait_timeout", 2.0)
        else:
            payload["wait_timeout"] = None

        retry_delay_raw = self.app_form_vars["retry_delay"].get().strip()
        if retry_delay_raw:
            payload["retry_delay"] = retry_delay_raw
        elif base_config is not None:
            payload["retry_delay"] = getattr(base_config, "retry_delay", 2.0)
        else:
            payload["retry_delay"] = None

        existing_caps = dict(payload.get("device_caps", {}) or {})
        caps_mapping = {
            "device_name": "deviceName",
            "platform_version": "platformVersion",
            "udid": "udid",
            "automation_name": "automationName",
        }
        for field_key, cap_key in caps_mapping.items():
            value = self.app_form_vars[field_key].get().strip()
            if value:
                existing_caps[cap_key] = value
            elif strict and cap_key in existing_caps:
                existing_caps.pop(cap_key, None)
        payload["device_caps"] = existing_caps

        return payload

    def _collect_app_config_from_form(self, *, strict: bool = True) -> Optional[Any]:
        if AppTicketConfig is None:
            raise RuntimeError("当前环境未启用 Appium")

        payload = self._build_app_config_payload(strict=strict)

        try:
            config = AppTicketConfig.from_mapping(payload)
        except Exception as exc:  # noqa: BLE001
            if ConfigValidationError is not None and isinstance(exc, ConfigValidationError):
                self._last_config_errors = list(exc.errors)
                if strict:
                    raise
                return None
            self._last_config_errors = [str(exc)]
            if strict:
                raise
            return None

        self._last_config_errors = []
        return config

    def _format_config_errors(self, errors: List[str]) -> str:
        if not errors:
            return ""
        return "\n".join(f"• {item}" for item in errors if item)

    def _show_config_validation_error(self, title: str, message: str, errors: List[str]) -> None:
        detail = self._format_config_errors(errors)
        full_message = message if not detail else f"{message}\n\n{detail}"
        messagebox.showerror(title, full_message)
        self.log(f"❌ {message}")
        for item in errors:
            self.log(f"    ↳ {item}")

    def _get_users_from_widget(self) -> List[str]:
        if self.app_users_text is None:
            return []
        content = self.app_users_text.get("1.0", tk.END).strip()
        if not content:
            return []
        candidates = re.split(r"[\n,;]", content)
        return [item.strip() for item in candidates if item.strip()]

    def create_control_buttons(self, parent, row):
        """创建控制按钮区域"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="🎯 开始抢票", 
                                   command=self.start_grabbing, state="disabled")
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止", 
                                  command=self.stop_grabbing, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        # 添加清除登录状态按钮
        self.clear_login_btn = ttk.Button(control_frame, text="🗑️ 清除登录状态", 
                                         command=self.clear_login_status)
        self.clear_login_btn.pack(side="left", padx=5)
        
        self.help_btn = ttk.Button(control_frame, text="❓ 帮助", command=self.show_help)
        self.help_btn.pack(side="left", padx=5)
        
        ttk.Button(control_frame, text="❌ 退出", command=self.root.quit).pack(side="right", padx=5)
        
    def _on_mode_tab_changed(self, event: tk.Event) -> None:  # type: ignore[override]
        if not hasattr(self, "mode_notebook"):
            return
        try:
            current_index = event.widget.index("current")  # type: ignore[attr-defined]
        except Exception:
            current_index = 0
        mode = "web" if current_index == 0 else "app"
        if self.mode_var.get() != mode:
            self.mode_var.set(mode)
        self.switch_mode(from_notebook=True)

    def switch_mode(self, *, from_notebook: bool = False) -> None:
        """切换网页/App 模式"""

        mode = self.mode_var.get()
        self.refresh_steps()

        if not from_notebook and hasattr(self, "mode_notebook"):
            desired_index = 0 if mode == "web" else 1
            try:
                current_index = self.mode_notebook.index("current")
            except Exception:
                current_index = desired_index
            if current_index != desired_index:
                self.mode_notebook.select(desired_index)

        self.env_status_label.config(text="点击检测环境", foreground="orange")

        if mode == "web":
            if hasattr(self, "login_btn"):
                self.login_btn.config(state="disabled")
            if hasattr(self, "analyze_btn"):
                self.analyze_btn.config(state="disabled")
            if hasattr(self, "start_btn"):
                self.start_btn.config(state="disabled")
            self.log("🔁 已切换到网页模式")
        else:
            if hasattr(self, "start_btn"):
                self.start_btn.config(state="disabled")
            if hasattr(self, "stop_btn"):
                self.stop_btn.config(state="disabled")
            self._refresh_app_start_button()
            self.log("🔁 已切换到 App 模式，请先检测环境并完善配置表单")

    def _get_default_app_config_path(self) -> Optional[str]:
        """尝试查找默认的 App 配置文件路径"""

        candidates = [
            Path.cwd() / "damai_appium" / "config.jsonc",
            Path.cwd() / "damai_appium" / "config.json",
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        return None

    def select_app_config(self) -> None:
        """选择 App 配置文件"""

        file_path = filedialog.askopenfilename(
            title="选择 App 配置文件",
            filetypes=[("JSON/JSONC", "*.jsonc *.json"), ("所有文件", "*.*")],
        )
        if file_path:
            self.app_config_path_var.set(file_path)
            self.load_app_config()

    def open_app_docs(self) -> None:
        """打开 App 模式文档"""

        doc_candidates = [
            Path.cwd() / "damai_appium" / "app.md",
            Path.cwd() / "doc" / "app.md",
        ]
        for doc_path in doc_candidates:
            if doc_path.exists():
                try:
                    os.startfile(doc_path)  # type: ignore[attr-defined]
                except Exception:
                    webbrowser.open(doc_path.as_uri())
                return
        messagebox.showinfo("提示", "未找到 App 模式文档，可访问项目 README 了解详情。")

    def load_app_config(self) -> None:
        """加载 App 模式配置"""

        if not APPIUM_AVAILABLE or AppTicketConfig is None:
            messagebox.showerror("错误", "当前环境未启用 Appium，无法加载配置。")
            return

        config_path = self.app_config_path_var.get().strip()
        if not config_path:
            messagebox.showwarning("提示", "请先选择配置文件路径。")
            return

        path = Path(config_path)
        if not path.exists():
            messagebox.showerror("错误", f"配置文件不存在: {path}")
            return

        if self.mode_var.get() == "app":
            self.mark_step("3. 参数配置", "active")

        try:
            config = AppTicketConfig.load(path)
            self.app_loaded_config = config
            self.app_config_data = {
                "path": str(path),
                "config": config,
            }
            self._populate_app_form(config)
            self.app_config_status.config(text="配置加载成功", foreground="green")
            self.log(f"✅ 已加载 App 配置: {path.name}")
            self._last_config_errors = []

            if self.mode_var.get() == "app":
                self.mark_step("3. 参数配置", "completed")
            self._refresh_app_start_button()
        except Exception as exc:  # noqa: BLE001
            self.app_config_status.config(text="配置加载失败", foreground="red")
            self.app_config_ready = False
            if ConfigValidationError is not None and isinstance(exc, ConfigValidationError):
                errors = list(exc.errors)
                self._last_config_errors = errors
                self._show_config_validation_error("配置校验失败", exc.message, errors)
            else:
                self._last_config_errors = [str(exc)]
                messagebox.showerror("错误", f"配置加载失败: {exc}")
                self.log(f"❌ 配置加载失败: {exc}")

    def _set_app_summary_text(self, config: Any) -> None:
        """更新配置摘要显示"""

        self.app_summary_text.config(state="normal")
        self.app_summary_text.delete("1.0", tk.END)

        if not config:
            self.app_summary_text.insert(
                tk.END,
                "暂无有效配置，请在左侧表单填写 Appium 服务、设备信息和抢票参数。",
            )
            self.app_summary_text.config(state="disabled")
            return

        summary_lines = [
            f"🔌 Appium 服务: {config.server_url}",
        ]
        if config.city:
            summary_lines.append(f"🏙️ 城市: {config.city}")
        if config.keyword:
            summary_lines.append(f"🔎 关键词: {config.keyword}")
        if config.date:
            summary_lines.append(f"📅 日期: {config.date}")
        if config.price:
            summary_lines.append(f"💰 价格: {config.price}")
        if config.price_index is not None:
            summary_lines.append(f"🎯 价格索引: {config.price_index}")
        if config.users:
            summary_lines.append("👥 观演人: " + ", ".join(config.users))
        summary_lines.append(f"🕒 等待超时: {config.wait_timeout}s")
        summary_lines.append(f"🔁 重试间隔: {config.retry_delay}s")

        if getattr(self, "app_detected_devices", None):
            summary_lines.append("📱 已连接设备: " + ", ".join(self.app_detected_devices))
        elif self.mode_var.get() == "app":
            summary_lines.append("📱 已连接设备: 暂未检测到，可在“环境检测”后查看日志。")

        self.app_summary_text.insert(tk.END, "\n".join(summary_lines))
        self.app_summary_text.config(state="disabled")

    def update_step(self, step_index, status="active"):
        """更新步骤状态"""
        colors = {
            "inactive": "gray",
            "active": "blue", 
            "completed": "green",
            "error": "red"
        }
        
        if 0 <= step_index < len(self.step_labels):
            color = colors.get(status, "gray")
            self.step_labels[step_index].config(foreground=color)
            if status == "completed":
                text = "✓ " + self.steps[step_index]
                self.step_labels[step_index].config(text=text)

    def mark_step(self, step_label: str, status: str = "active") -> None:
        """根据名称更新当前模式步骤状态"""

        try:
            index = self.steps.index(step_label)
        except (ValueError, AttributeError):
            return
        self.update_step(index, status)
                
    def _on_log_filter_changed(self, *_args: Any) -> None:
        self._refresh_log_view()

    def clear_logs(self) -> None:
        """清空日志窗口与历史记录。"""

        self.log_entries.clear()
        if hasattr(self, "log_text"):
            self.log_text.delete("1.0", tk.END)
            self.log_text.see(tk.END)
            self.root.update_idletasks()

    def _infer_log_level(self, message: str) -> str:
        normalized = message.strip()
        lowered = normalized.lower()

        if normalized.startswith("❌") or "错误" in normalized or "fail" in lowered:
            return "error"
        if normalized.startswith("⚠️") or "警告" in normalized or "warning" in lowered:
            return "warning"
        if normalized.startswith("✅") or normalized.startswith("✔") or "成功" in normalized:
            return "success"
        if normalized.startswith("ℹ️") or normalized.startswith("📢"):
            return "info"
        return "info"

    def _log_passes_filter(self, level: str) -> bool:
        selected = self.log_filter_var.get()
        if selected == "全部":
            return True

        mapping = {
            "仅信息": "info",
            "仅成功": "success",
            "仅警告": "warning",
            "仅错误": "error",
        }
        target_level = mapping.get(selected)
        return target_level is None or level == target_level

    def _append_log_entry(self, entry: Tuple[str, str, str], *, auto_scroll: bool = True) -> None:
        timestamp, message, _level = entry
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        if auto_scroll:
            self.log_text.see(tk.END)
            self.root.update_idletasks()

    def _refresh_log_view(self) -> None:
        if not hasattr(self, "log_text"):
            return

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)

        for entry in self.log_entries:
            if self._log_passes_filter(entry[2]):
                self._append_log_entry(entry, auto_scroll=False)

        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def log(self, message: str, level: Optional[str] = None) -> None:
        """添加日志信息并记录在历史中。"""

        if level is None:
            level = self._infer_log_level(message)

        timestamp = time.strftime("%H:%M:%S")
        entry = (timestamp, message, level)
        self.log_entries.append(entry)

        if not hasattr(self, "log_text"):
            return

        if self._log_passes_filter(level):
            self._append_log_entry(entry)
        else:
            # 过滤后不显示，但保持滚动位置
            self.log_text.see(tk.END)
            self.root.update_idletasks()

    def _update_app_metrics_display(self, report: Optional[Any]) -> None:
        if report is None or not hasattr(report, "metrics"):
            self.app_metrics_var.set("尚未运行 App 抢票流程")
            return

        metrics = report.metrics
        duration = max(metrics.end_time - metrics.start_time, 0.0)
        retries = max(metrics.attempts - 1, 0)
        finished_at = datetime.fromtimestamp(metrics.end_time).strftime("%H:%M:%S")

        lines = [
            f"状态：{'成功' if metrics.success else '失败'}",
            f"总耗时：{duration:.2f} 秒",
            f"尝试次数：{metrics.attempts}（重试 {retries} 次）",
            f"最终阶段：{metrics.final_phase.value}",
            f"结束时间：{finished_at}",
        ]

        if not metrics.success:
            failure_text = self._format_failure_for_display(report)
            lines.append(f"失败说明：{failure_text}")

        self.app_metrics_var.set("\n".join(lines))

    def _format_failure_for_display(self, report: Optional[Any]) -> str:
        if report is None or not hasattr(report, "metrics"):
            return "未能成功抢票，原因未知。"

        metrics = report.metrics
        base_reason = metrics.failure_reason or "未能成功抢票"
        code = getattr(metrics, "failure_code", None)

        if FailureReason is None or code is None:
            return base_reason

        if code == FailureReason.MAX_RETRIES:
            return f"多次尝试仍未成功（共 {metrics.attempts} 次）。建议检查网络或稍后重试。"
        if code == FailureReason.APPIUM_CONNECTION:
            return f"无法连接 Appium 服务：{base_reason}"
        if code == FailureReason.FLOW_FAILURE:
            return f"流程执行失败：{base_reason}"
        if code == FailureReason.UNEXPECTED:
            return f"发生未预期的错误：{base_reason}"
        if code == FailureReason.USER_STOP:
            return base_reason or "流程已被用户停止。"
        return base_reason

    def export_logs(self) -> None:
        default_name = datetime.now().strftime("damai_logs_%Y%m%d_%H%M%S.json")
        target_path = filedialog.asksaveasfilename(
            title="导出运行日志",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            initialfile=default_name,
        )
        if not target_path:
            return

        payload = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "app_run_report": self.last_app_report.to_dict() if self.last_app_report else None,
            "log_entries": [
                {"timestamp": ts, "message": msg, "level": level}
                for ts, msg, level in self.log_entries
            ],
        }

        try:
            with open(target_path, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导出失败", f"无法写入日志文件：{exc}")
            return

        self.log(f"💾 日志已导出到 {target_path}")
        
    def clear_url_placeholder(self, event):
        """清除URL输入框占位符"""
        if self.url_entry.get() == "请输入大麦网演出详情页链接...":
            self.url_entry.delete(0, tk.END)
            
    def check_environment(self):
        """检测环境"""
        step_label = "1. 环境检测"
        self.mark_step(step_label, "active")
        self.log("🔍 开始检测环境...")

        if self.mode_var.get() == "app":
            self._check_app_environment()
        else:
            self._check_web_environment()

    def _check_web_environment(self) -> None:
        try:
            python_version = sys.version.split()[0]
            self.log(f"✅ Python版本: {python_version}")

            if not SELENIUM_AVAILABLE:
                raise RuntimeError("Selenium未安装，请先安装：pip install selenium")
            self.log("✅ Selenium已安装")

            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            driver.quit()
            self.log("✅ Chrome浏览器驱动正常")

        except Exception as exc:
            self.log(f"❌ 环境检测出错: {exc}")
            self.env_status_label.config(text="环境检测异常", foreground="red")
            self.mark_step("1. 环境检测", "error")
            messagebox.showerror("错误", str(exc))
            return

        self.env_status_label.config(text="环境检测完成", foreground="green")
        self.mark_step("1. 环境检测", "completed")
        self.log("✅ 环境检测完成，所有组件正常")

        if hasattr(self, "login_btn"):
            self.login_btn.config(state="normal")
        if hasattr(self, "analyze_btn"):
            self.analyze_btn.config(state="normal")

        self._try_auto_login()

    # ------------------------------------------------------------------
    # App 模式依赖检测
    # ------------------------------------------------------------------

    def _check_cli_dependency(self, command: str, args: List[str], friendly_name: str) -> Tuple[bool, str]:
        """尝试运行外部命令来检查依赖是否存在。"""

        if not shutil.which(command):
            return False, f"未找到 {friendly_name}（命令：{command}），请先安装并添加到 PATH。"

        try:
            result = subprocess.run(  # noqa: S603,S607
                [command, *args],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"{friendly_name} 检测失败：{exc}"

        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            message = output or "未知错误"
            return False, f"{friendly_name} 返回码 {result.returncode}：{message}"

        summary = output.splitlines()[0] if output else "检测通过"
        return True, summary

    def _check_node_cli(self) -> Tuple[bool, str]:
        return self._check_cli_dependency("node", ["--version"], "Node.js")

    def _check_appium_cli(self) -> Tuple[bool, str]:
        return self._check_cli_dependency("appium", ["-v"], "Appium CLI")

    def _check_adb_cli(self) -> Tuple[bool, str]:
        return self._check_cli_dependency("adb", ["version"], "ADB")

    def _check_app_environment(self) -> None:
        self.app_env_ready = False
        tracking_device_status = self.mode_var.get() == "app"

        if tracking_device_status:
            self._device_refresh_in_progress = True
            if hasattr(self, "app_device_refresh_btn") and (
                APPIUM_AVAILABLE and parse_adb_devices is not None
            ):
                self.app_device_refresh_btn.config(state="disabled")
            if APPIUM_AVAILABLE and parse_adb_devices is not None:
                self._set_device_status("正在检查 Appium 环境...", color="blue")
                self._set_device_detail("正在请求 Appium 服务并检测已连接的设备...", color="blue")
        try:
            config: Any = None

            node_ok, node_message = self._check_node_cli()
            if node_ok:
                self.log(f"✅ Node.js: {node_message}")
            else:
                install_hint = (
                    "请先安装 Node.js（https://nodejs.org/），安装时勾选添加到 PATH，"
                    "完成后重新启动本工具。"
                )
                self.log(f"❌ {node_message}")
                self.env_status_label.config(text="缺少 Node.js 环境", foreground="red")
                self.mark_step("1. 环境检测", "error")
                if tracking_device_status:
                    self._set_device_status("无法检测设备", color="red")
                    self._set_device_detail(install_hint, color="red")
                messagebox.showerror("缺少依赖", f"{node_message}\n\n{install_hint}")
                return

            appium_cli_ok, appium_message = self._check_appium_cli()
            if appium_cli_ok:
                self.log(f"✅ Appium CLI: {appium_message}")
            else:
                install_hint = (
                    "未检测到 Appium CLI。可在命令行执行 `npm install -g appium` 安装，"
                    "或使用 Appium Inspector 自带的服务器。安装完成后请重新打开本程序。"
                )
                self.log(f"❌ {appium_message}")
                self.env_status_label.config(text="缺少 Appium CLI", foreground="red")
                self.mark_step("1. 环境检测", "error")
                if tracking_device_status:
                    self._set_device_status("无法检测设备", color="red")
                    self._set_device_detail(install_hint, color="red")
                messagebox.showerror("缺少依赖", f"{appium_message}\n\n{install_hint}")
                return

            adb_ok, adb_message = self._check_adb_cli()
            if adb_ok:
                self.log(f"✅ ADB: {adb_message}")
            else:
                adb_hint = (
                    "未检测到 adb，请安装 Android 平台工具（Platform Tools）并将其加入 PATH。"
                    "没有 adb 将无法列出设备。"
                )
                self.log(f"⚠️ {adb_message}")
                if tracking_device_status:
                    self._set_device_status("未检测到 adb", color="orange")
                    self._set_device_detail(adb_hint, color="orange")

            if not APPIUM_AVAILABLE or DamaiAppTicketRunner is None:
                self.env_status_label.config(text="Appium 环境不可用", foreground="red")
                self.mark_step("1. 环境检测", "error")
                self._reset_device_status_ui()
                messagebox.showerror("错误", "未检测到 Appium 运行环境，请先安装依赖并配置 Python 包。")
                return

            try:
                python_version = sys.version.split()[0]
                self.log(f"✅ Python版本: {python_version}")
            except Exception:
                pass

            if not self.app_config_ready:
                self.log("⚠️ 尚未完成配置表单，检测将使用当前输入的默认值。")
            else:
                self.mark_step("3. 参数配置", "completed")

            try:
                config = self._validate_app_server()
            except Exception as exc:  # noqa: BLE001
                self.env_status_label.config(text="Appium 服务异常", foreground="red")
                self.mark_step("1. 环境检测", "error")
                messagebox.showerror("错误", f"Appium 服务不可用: {exc}")
                return

            if adb_ok:
                has_ready_device = self._detect_connected_devices()
            else:
                has_ready_device = False
            self._update_device_status_from_result(has_ready_device)

            self.app_env_ready = True
            if has_ready_device:
                status_text = "Appium 环境准备就绪"
                status_color = "green"
                self.mark_step("2. 设备检查", "completed")
                self.log("✅ Appium 环境检测通过，可以连接设备")
            else:
                status_text = "Appium 服务可用（未检测到设备）"
                status_color = "orange"
                self.mark_step("2. 设备检查", "error")
                self.log("⚠️ Appium 服务正常，但未检测到可用设备，请检查 adb 连接或设备授权。")

            self.env_status_label.config(text=status_text, foreground=status_color)
            self.mark_step("1. 环境检测", "completed")

            if config is not None:
                try:
                    self._set_app_summary_text(config)
                except Exception:
                    pass

            if self.app_config_ready and hasattr(self, "start_btn"):
                self.start_btn.config(state="normal")
        finally:
            if tracking_device_status:
                self._device_refresh_in_progress = False
                if hasattr(self, "app_device_refresh_btn"):
                    can_refresh = APPIUM_AVAILABLE and parse_adb_devices is not None
                    state = "normal" if can_refresh else "disabled"
                    self.app_device_refresh_btn.config(state=state)

    def _validate_app_server(self) -> Any:
        config = self._collect_app_config_from_form(strict=False)
        if config is None:
            error_detail = self._format_config_errors(self._last_config_errors)
            message = error_detail or "请先完善 App 配置后再检测服务"
            raise RuntimeError(message)

        try:
            caps = config.desired_capabilities
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"解析设备能力失败: {exc}") from exc

        server_url = config.server_url.rstrip("/")
        if not server_url:
            raise RuntimeError("Appium 服务地址不能为空")

        status_url = f"{server_url}/status"

        try:
            import urllib.request
            from urllib.error import URLError

            req = urllib.request.Request(status_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError(f"状态码异常: {response.status}")
                self.log("✅ Appium 服务响应正常")
                device_name = caps.get("deviceName") if isinstance(caps, dict) else None
                if device_name:
                    self.log(f"📱 目标设备: {device_name}")
        except URLError as exc:
            raise RuntimeError(f"无法连接 Appium 服务: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"检测 Appium 服务失败: {exc}") from exc

        return config

    def _set_device_status(self, message: str, *, color: str = "gray") -> None:
        var = getattr(self, "app_device_status_var", None)
        if var is None:
            return
        var.set(message)
        if hasattr(self, "app_device_status_label"):
            self.app_device_status_label.config(foreground=color)

    def _set_device_detail(self, message: str, *, color: Optional[str] = None) -> None:
        var = getattr(self, "app_device_detail_var", None)
        if var is None:
            return
        var.set(message)
        if hasattr(self, "app_device_detail_label") and color is not None:
            self.app_device_detail_label.config(foreground=color)

    def _reset_device_status_ui(self) -> None:
        can_refresh = APPIUM_AVAILABLE and parse_adb_devices is not None
        if can_refresh:
            self._set_device_status("尚未检测设备", color="gray")
            hint = "点击“刷新设备”或执行环境检测查看最新状态。"
            self._set_device_detail(hint, color="gray")
        else:
            if not APPIUM_AVAILABLE:
                hint = "当前环境未启用 Appium，安装完成后可刷新设备列表。"
            else:
                hint = "缺少 adb 解析能力，安装 damai_appium 依赖后重启程序。"
            self._set_device_status("无法检测设备", color="red")
            self._set_device_detail(hint, color="red")

        if hasattr(self, "app_device_refresh_btn"):
            state = "normal" if can_refresh else "disabled"
            self.app_device_refresh_btn.config(state=state)
        if self.app_device_combobox is not None:
            self.app_device_combobox.set("")
            self.app_device_combobox.config(values=())
            self.app_device_combobox.config(state="disabled")
        if self.app_device_options_var is not None:
            self.app_device_options_var.set("")
        self.app_detected_device_records = []
        self._device_refresh_in_progress = False

    def _refresh_devices_clicked(self) -> None:
        if not (APPIUM_AVAILABLE and parse_adb_devices is not None):
            messagebox.showwarning("提示", "当前环境未启用 Appium 或缺少 adb 支持，请先完成依赖安装。")
            return

        if self._device_refresh_in_progress:
            self.log("ℹ️ 正在刷新设备列表，请稍候...")
            return

        self._device_refresh_in_progress = True
        if hasattr(self, "app_device_refresh_btn"):
            self.app_device_refresh_btn.config(state="disabled")

        self._set_device_status("正在刷新设备列表...", color="blue")
        self._set_device_detail("正在执行 adb devices -l，请稍候...", color="blue")

        # 使用 after 避免阻塞当前事件循环
        self.root.after(50, self._perform_device_refresh)

    def _perform_device_refresh(self) -> None:
        try:
            has_ready_device = self._detect_connected_devices()
            self._update_device_status_from_result(has_ready_device)
            self._update_app_summary_from_form()
        finally:
            self._device_refresh_in_progress = False
            if hasattr(self, "app_device_refresh_btn") and (APPIUM_AVAILABLE and parse_adb_devices is not None):
                self.app_device_refresh_btn.config(state="normal")

    def _update_device_status_from_result(self, has_ready_device: bool) -> None:
        if not (APPIUM_AVAILABLE and parse_adb_devices is not None):
            self._reset_device_status_ui()
            return

        combo = self.app_device_combobox
        if not self.app_detected_device_records and self.app_detected_devices:
            self.app_detected_device_records = [
                {"label": label, "serial": label}
                for label in self.app_detected_devices
            ]

        device_labels = [record.get("label", "") for record in self.app_detected_device_records]

        if has_ready_device and device_labels:
            device_count = len(device_labels)
            status_text = f"已检测到 {device_count} 台可用设备"
            self._set_device_status(status_text, color="green")

            list_detail = self._format_detected_device_list(self.app_detected_device_records)
            self._set_device_detail(list_detail, color="green")

            if combo is not None:
                combo.config(values=device_labels)
                combo.config(state="readonly")

                previous = self.app_device_options_var.get().strip() if self.app_device_options_var else ""
                if previous and previous in device_labels:
                    combo.set(previous)
                else:
                    combo.current(0)
                    if self.app_device_options_var is not None:
                        self.app_device_options_var.set(device_labels[0])

                self._on_device_selection_changed()
        else:
            hint = "请检查 USB 连接、驱动和授权状态，然后点击“刷新设备”。"
            self._set_device_status("未检测到可用设备", color="orange")
            self._set_device_detail(hint, color="orange")

            if combo is not None:
                combo.set("")
                combo.config(values=())
                combo.config(state="disabled")
            if self.app_device_options_var is not None:
                self.app_device_options_var.set("")

    def _format_detected_device_list(self, records: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for idx, record in enumerate(records, start=1):
            label = record.get("label") or record.get("serial") or "未知设备"
            lines.append(f"{idx}. {label}")
        return "\n".join(lines) or "设备已成功连接，可直接开始抢票。"

    def _find_device_record_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        for record in self.app_detected_device_records:
            if record.get("label") == label:
                return record
        return None

    def _apply_device_record_to_form(self, record: Dict[str, Any]) -> None:
        if not record:
            return

        device_name_value = record.get("model") or record.get("device") or record.get("serial") or ""
        if device_name_value:
            self.app_form_vars["device_name"].set(device_name_value)

        serial = record.get("serial", "")
        if serial:
            self.app_form_vars["udid"].set(serial)

        if not self.app_form_vars["automation_name"].get().strip():
            self.app_form_vars["automation_name"].set("UiAutomator2")

    def _build_device_detail_message(self, record: Dict[str, Any]) -> str:
        lines: List[str] = []
        primary_label = record.get("label") or record.get("serial") or "未知设备"
        lines.append(f"当前选择：{primary_label}")
        serial = record.get("serial")
        if serial:
            lines.append(f"序列号：{serial}")
        model = record.get("model")
        if model:
            lines.append(f"型号：{model}")
        device_name = record.get("device")
        if device_name and device_name != model:
            lines.append(f"设备代号：{device_name}")
        transport_id = record.get("transport_id")
        if transport_id:
            lines.append(f"Transport ID：{transport_id}")
        lines.append("已自动填充“设备名称”和“设备 UDID”字段。")
        lines.append("如需修改，可在下方表单中手动调整。")

        other_devices = [
            other.get("label") or other.get("serial") or "未知设备"
            for other in self.app_detected_device_records
            if other is not record
        ]
        if other_devices:
            lines.append("其他设备：")
            lines.extend(f"• {label}" for label in other_devices)
        return "\n".join(lines)

    def _on_device_selection_changed(self, event: Optional[Any] = None) -> None:
        if self.app_device_options_var is None:
            return

        selected_label = self.app_device_options_var.get().strip()
        if not selected_label:
            return

        record = self._find_device_record_by_label(selected_label)
        if record is None:
            return

        self._apply_device_record_to_form(record)
        detail_message = self._build_device_detail_message(record)
        self._set_device_detail(detail_message, color="green")

        if event is not None:
            display_label = record.get("label") or record.get("serial") or "未知设备"
            self.log(f"ℹ️ 已应用设备：{display_label}")

    def _detect_connected_devices(self) -> bool:
        """Run ``adb devices -l`` and record any connected Android devices."""

        self.app_detected_devices = []
        self.app_detected_device_records = []

        if parse_adb_devices is None:
            return False

        adb_command = ["adb", "devices", "-l"]
        try:
            result = subprocess.run(  # noqa: S603,S607 - 受控命令
                adb_command,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            self.log("⚠️ 未找到 adb 命令，请安装 Android SDK 平台工具并配置到 PATH。")
            return False
        except Exception as exc:  # noqa: BLE001
            self.log(f"⚠️ 执行 adb 命令失败: {exc}")
            return False

        output = (result.stdout or "").strip()
        if result.returncode != 0:
            message = (result.stderr or "").strip() or output or "未知错误"
            self.log(f"⚠️ adb 命令执行失败: {message}")
            return False

        devices = parse_adb_devices(output)
        if not devices:
            self.log("⚠️ adb 未检测到任何设备，请确认设备已连接并授权 USB 调试。")
            return False

        ready_devices: List[str] = []
        ready_records: List[Dict[str, Any]] = []
        for device in devices:
            try:
                label = device.describe()
            except Exception:  # noqa: BLE001
                label = device.serial

            if device.is_ready:
                ready_devices.append(label)
                self.log(f"✅ 检测到设备: {label}")
                ready_records.append(
                    {
                        "label": label,
                        "serial": device.serial,
                        "model": device.properties.get("model"),
                        "device": device.properties.get("device"),
                        "transport_id": device.properties.get("transport_id"),
                        "properties": dict(device.properties),
                        "info": device,
                    }
                )
            else:
                self.log(f"⚠️ 设备状态 {device.status}: {label}")

        self.app_detected_devices = ready_devices
        self.app_detected_device_records = ready_records

        if ready_devices:
            self.log(f"✅ 共检测到 {len(ready_devices)} 台处于可用状态的设备。")
        else:
            self.log("⚠️ 设备已被识别，但尚未进入 device 状态，请确认已授权 USB 调试。")

        return bool(ready_devices)

        
    def _try_auto_login(self):
        """尝试自动登录"""
        if os.path.exists(self.cookie_file):
            self.log("🔍 发现已保存的登录信息，尝试自动登录...")
            threading.Thread(target=self._auto_login_worker, daemon=True).start()
        else:
            self.log("ℹ️ 未发现保存的登录信息，请手动登录")
    
    def _auto_login_worker(self):
        """自动登录工作线程"""
        try:
            # 创建临时driver用于测试登录状态
            options = webdriver.ChromeOptions()
            options.add_experimental_option("excludeSwitches", ['enable-automation'])
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            temp_driver = webdriver.Chrome(options=options)
            self.driver = temp_driver
            
            # 尝试加载cookies
            if self.load_cookies():
                self.root.after(0, lambda: self.update_step(1, "completed"))  # 网页登录完成
                self.root.after(0, lambda: self.log("🎉 自动登录成功！"))
            else:
                temp_driver.quit()
                self.driver = None
                self.root.after(0, lambda: self.log("⚠️ 自动登录失败，请手动登录"))
                
        except Exception as e:
            if 'temp_driver' in locals():
                temp_driver.quit()
            self.driver = None
            self.root.after(0, lambda: self.log(f"❌ 自动登录出错: {e}"))
        
    def web_login(self):
        """网页登录功能"""
        self.update_step(1, "active")  # 网页登录是index=1
        self.log("🔐 启动网页登录...")
        
        url = self.url_entry.get().strip()
        if not url or url == "请输入大麦网演出详情页链接...":
            messagebox.showwarning("警告", "请先输入演出链接")
            return
            
        # 在新线程中执行登录
        threading.Thread(target=self._web_login_worker, args=(url,), daemon=True).start()
        
    def _web_login_worker(self, url):
        """网页登录工作线程"""
        try:
            # 初始化webdriver
            options = webdriver.ChromeOptions()
            options.add_experimental_option("excludeSwitches", ['enable-automation'])
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            self.driver = webdriver.Chrome(options=options)
            self.log("✅ 浏览器启动成功")
            
            # 打开大麦网首页
            self.driver.get("https://www.damai.cn")
            self.log("🌐 已打开大麦网，请在浏览器中完成登录")
            
            # 等待用户登录
            self.root.after(0, self._show_login_instructions)
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ 网页登录失败: {e}"))
            self.root.after(0, lambda: self.update_step(1, "error"))  # 网页登录是index=1
            
    def _show_login_instructions(self):
        """显示登录说明"""
        login_window = tk.Toplevel(self.root)
        login_window.title("登录说明")
        login_window.geometry("450x350")
        login_window.transient(self.root)
        login_window.grab_set()
        
        ttk.Label(login_window, text="🔐 请在浏览器中完成登录", 
                 font=self.title_font).pack(pady=20)
        
        instructions = [
            "1. 浏览器已自动打开大麦网",
            "2. 请点击页面上的「登录」按钮",
            "3. 使用手机扫码或账号密码登录",
            "4. 登录成功后点击下方「登录完成」按钮",
            "",
            "注意：请保持浏览器窗口打开",
            "登录状态将用于后续的抢票操作"
        ]
        
        for instruction in instructions:
            label = ttk.Label(login_window, text=instruction, font=self.default_font)
            label.pack(pady=2)
        
        button_frame = ttk.Frame(login_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="✅ 登录完成", 
                  command=lambda: self._login_completed(login_window)).pack(side="left", padx=10)
        ttk.Button(button_frame, text="❌ 取消", 
                  command=lambda: self._login_cancelled(login_window)).pack(side="left", padx=10)
                  
    def _login_completed(self, window):
        """登录完成"""
        window.destroy()
        
        # 保存cookies
        if self.save_cookies():
            self.update_step(1, "completed")  # 网页登录是index=1
            self.log("✅ 网页登录完成，登录状态已保存")
            messagebox.showinfo("成功", "登录完成并已保存登录状态！下次启动将自动登录。")
        else:
            self.update_step(1, "completed")  # 网页登录是index=1
            self.log("✅ 网页登录完成")
            messagebox.showinfo("成功", "登录完成！现在可以输入演出链接进行分析。")
        
    def _login_cancelled(self, window):
        """取消登录"""
        window.destroy()
        if self.driver:
            self.driver.quit()
            self.driver = None
        self.update_step(1, "inactive")  # 网页登录是index=1
        self.log("❌ 登录已取消")
        
    def analyze_page(self):
        """分析页面功能"""
        url = self.url_entry.get().strip()
        if not url or url == "请输入大麦网演出详情页链接...":
            messagebox.showwarning("警告", "请输入演出链接")
            return
            
        # 登录变为可选，不强制要求
        if not self.driver:
            self.log("ℹ️ 未检测到浏览器实例，将创建新的浏览器进行分析")
            
        self.update_step(2, "active")  # 页面分析是index=2
        self.log(f"🔍 开始分析页面: {url}")
        
        # 在新线程中执行分析
        threading.Thread(target=self._analyze_page_worker, args=(url,), daemon=True).start()
        
    def _analyze_page_worker(self, url):
        """页面分析工作线程"""
        try:
            # 如果没有driver，创建一个临时的用于分析
            temp_driver = None
            if not self.driver:
                self.root.after(0, lambda: self.log("🚀 创建临时浏览器进行页面分析..."))
                options = webdriver.ChromeOptions()
                options.add_experimental_option("excludeSwitches", ['enable-automation'])
                options.add_argument('--disable-blink-features=AutomationControlled')
                temp_driver = webdriver.Chrome(options=options)
                analysis_driver = temp_driver
            else:
                analysis_driver = self.driver
            
            # 使用专用的页面分析器
            from gui_concert import PageAnalyzer
            
            analyzer = PageAnalyzer(
                driver=analysis_driver,
                log_callback=lambda msg: self.root.after(0, lambda: self.log(msg))
            )
            
            # 分析页面信息
            page_info = analyzer.analyze_show_page(url)
            
            if page_info:
                self.target_url = url
                # 更新UI
                self.root.after(0, lambda: self._update_page_info(page_info))
                self.root.after(0, lambda: self._create_config_interface(page_info))
            else:
                self.root.after(0, lambda: self.update_step(2, "error"))  # 页面分析是index=2
            
            # 如果使用了临时driver，关闭它
            if temp_driver:
                temp_driver.quit()
                self.root.after(0, lambda: self.log("🗑️ 临时浏览器已关闭"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ 页面分析失败: {e}"))
            self.root.after(0, lambda: self.update_step(2, "error"))  # 页面分析是index=2
            
    def _update_page_info(self, info):
        """更新页面信息显示 - 改为在日志中显示关键信息"""
        
        # 在日志中显示页面分析结果
        self.log(f"📊 演出信息分析结果")
        self.log(f"🎭 演出名称: {info['title']}")
        self.log(f"🏟️ 演出场地: {info['venue']}")
        self.log(f"🎫 售票状态: {info['status']}")
        
        if info['cities']:
            self.log(f"🏙️ 可选城市 ({len(info['cities'])}个): {', '.join(info['cities'][:3])}{'...' if len(info['cities']) > 3 else ''}")
        
        if info['dates']:
            self.log(f"📅 可选日期 ({len(info['dates'])}个): {', '.join(info['dates'][:3])}{'...' if len(info['dates']) > 3 else ''}")
        
        if info['prices']:
            self.log(f"💰 价格档位 ({len(info['prices'])}个): {', '.join(info['prices'][:3])}{'...' if len(info['prices']) > 3 else ''}")
        
        self.update_step(2, "completed")  # 页面分析是index=2
        self.log("✅ 页面分析完成")
        
        # 页面分析完成后自动保存cookies
        self.save_cookies()
        
    def _create_config_interface(self, info):
        """创建配置界面"""
        # 清除现有配置界面
        for widget in self.config_label.master.winfo_children():
            if widget != self.config_label:
                widget.destroy()
                
        self.config_label.config(text="")
        config_frame = self.config_label.master
        
        # 城市选择
        if info['cities']:
            ttk.Label(config_frame, text="🏙️ 选择城市:", font=self.default_font).pack(anchor="w", pady=2)
            self.city_var = tk.StringVar(value=info['cities'][0])
            city_combo = ttk.Combobox(config_frame, textvariable=self.city_var, 
                                     values=info['cities'], state="readonly", font=self.default_font)
            city_combo.pack(fill="x", pady=2)
            
        # 日期选择
        if info['dates']:
            ttk.Label(config_frame, text="📅 选择日期:", font=self.default_font).pack(anchor="w", pady=2)
            self.date_var = tk.StringVar(value=info['dates'][0])
            date_combo = ttk.Combobox(config_frame, textvariable=self.date_var, 
                                     values=info['dates'], state="readonly", font=self.default_font)
            date_combo.pack(fill="x", pady=2)
            
        # 价格选择
        if info['prices']:
            ttk.Label(config_frame, text="💰 选择价格:", font=self.default_font).pack(anchor="w", pady=2)
            self.price_var = tk.StringVar(value=info['prices'][0])
            price_combo = ttk.Combobox(config_frame, textvariable=self.price_var, 
                                      values=info['prices'], state="readonly", font=self.default_font)
            price_combo.pack(fill="x", pady=2)
            
        # 固定配置说明
        ttk.Label(config_frame, text="🎫 购买数量: 1张 (固定)", font=self.default_font).pack(anchor="w", pady=2)
        ttk.Label(config_frame, text="👥 观演人: 自动选择全部", font=self.default_font).pack(anchor="w", pady=2)
        
        # 提交订单选项
        self.commit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="自动提交订单 (谨慎使用)", 
                       variable=self.commit_var).pack(anchor="w", pady=2)
                       
        # 回流监听选项
        self.listen_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(config_frame, text="启用回流监听 (售罄后继续等待)", 
                       variable=self.listen_var).pack(anchor="w", pady=2)
        
        # 确认配置按钮
        ttk.Button(config_frame, text="✅ 确认配置", 
                  command=self._confirm_config).pack(pady=10)
                  
        self.update_step(3, "active")  # 参数配置是index=3
        
    def _confirm_config(self):
        """确认配置"""
        try:
            # 收集配置信息
            config = {}
            
            if hasattr(self, 'city_var'):
                config["city"] = self.city_var.get()
            if hasattr(self, 'date_var'):
                config["date"] = self.date_var.get()
            if hasattr(self, 'price_var'):
                config["price"] = self.price_var.get()
                
            config["users"] = ["自动选择全部"]
            config["if_commit_order"] = self.commit_var.get()
            config["if_listen"] = self.listen_var.get()  # 添加回流监听配置
            config["target_url"] = self.target_url
            
            self.config = config
            
            summary = f"""
✅ 配置完成

🏙️ 城市: {config.get('city', '未选择')}
📅 日期: {config.get('date', '未选择')}  
💰 价格: {config.get('price', '未选择')}
🎫 数量: 1张 (固定)
👥 观演人: 自动选择全部
📋 提交订单: {'是' if config['if_commit_order'] else '否'}
🔄 回流监听: {'是' if config['if_listen'] else '否'}
"""
            
            self.log(summary)
            self.update_step(3, "completed")  # 参数配置是index=3
            self.update_step(4, "active")     # 开始抢票是index=4
            self.start_btn.config(state="normal")
            
            messagebox.showinfo("配置完成", "抢票参数配置完成！可以开始抢票了。")
            
        except Exception as e:
            self.log(f"❌ 配置确认失败: {e}")
            
    def start_grabbing(self):
        """开始抢票"""
        if self.mode_var.get() == "app":
            self._start_app_grabbing()
        else:
            self._start_web_grabbing()

    def _start_web_grabbing(self) -> None:
        if not self.config:
            messagebox.showwarning("警告", "请先完成页面分析和参数配置")
            return

        if not self.driver:
            result = messagebox.askyesno(
                "登录确认",
                '您还未登录大麦网。\n\n点击"是"开始抢票（抢票过程中会弹出登录窗口）\n点击"否"取消操作',
            )
            if not result:
                return
            self.log("ℹ️ 将在抢票过程中进行登录")

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.is_grabbing = True
        self.log("🎯 开始执行抢票...")

        threading.Thread(target=self._grabbing_worker, daemon=True).start()

    def _start_app_grabbing(self) -> None:
        if not APPIUM_AVAILABLE or DamaiAppTicketRunner is None:
            messagebox.showerror("错误", "当前环境未配置 Appium，无法启动 App 抢票。")
            return

        if not self.app_env_ready:
            messagebox.showwarning("提示", "请先完成环境检测，确保 Appium 服务可用。")
            return

        if not self.app_config_ready:
            messagebox.showwarning("提示", "请先通过左侧表单完善 App 配置。")
            return

        try:
            config = self._collect_app_config_from_form()
        except Exception as exc:  # noqa: BLE001
            if ConfigValidationError is not None and isinstance(exc, ConfigValidationError):
                errors = list(exc.errors)
                self._last_config_errors = errors
                self._show_config_validation_error("配置校验失败", exc.message, errors)
            else:
                self._last_config_errors = [str(exc)]
                messagebox.showerror("错误", f"解析配置失败: {exc}")
                self.log(f"❌ 解析配置失败: {exc}")
            return

        try:
            max_retries = max(1, int(self.app_retries_var.get()))
        except Exception:
            max_retries = 1

        # 运行使用的配置与表单保持一致
        self.app_loaded_config = config

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.is_grabbing = True
        self.app_should_stop = False
        self.last_app_report = None
        self.app_metrics_var.set("App 抢票流程运行中…")
        self.mark_step("4. 开始抢票", "active")
        self.log("🎯 开始执行 App 抢票流程...")

        self.app_runner_thread = threading.Thread(
            target=self._run_app_runner,
            args=(config, max_retries),
            daemon=True,
        )
        self.app_runner_thread.start()
        
    def _grabbing_worker(self):
        """抢票工作线程"""
        try:
            # 如果没有driver，创建一个并提示用户登录
            if not self.driver:
                self.root.after(0, lambda: self.log("🚀 启动浏览器..."))
                options = webdriver.ChromeOptions()
                options.add_experimental_option("excludeSwitches", ['enable-automation'])
                options.add_argument('--disable-blink-features=AutomationControlled')
                self.driver = webdriver.Chrome(options=options)
                
                # 打开大麦网让用户登录
                self.driver.get("https://www.damai.cn")
                self.root.after(0, lambda: self.log("🌐 已打开大麦网，请在浏览器中完成登录"))
                
                # 弹出登录提示窗口
                self.root.after(0, self._show_login_for_grabbing)
                return  # 等待用户确认登录后再继续
            
            # 使用GUI专用的抢票模块
            from gui_concert import GUIConcert
            
            # 创建抢票实例
            concert = GUIConcert(
                driver=self.driver,
                config=self.config,
                log_callback=lambda msg: self.root.after(0, lambda: self.log(msg)),
                cookie_callback=lambda: self.root.after(0, self.auto_save_cookies_if_needed),
                stop_check=lambda: not self.is_grabbing  # 停止检查回调
            )
            
            self.root.after(0, lambda: self.log("🎫 开始执行抢票流程..."))
            
            # 执行抢票
            concert.choose_ticket()
            
            # 抢票完成后自动保存cookies
            self.root.after(0, lambda: self.save_cookies())
            
            self.root.after(0, lambda: self.log("✅ 抢票流程执行完成"))
            self.root.after(0, lambda: self.update_step(4, "completed"))  # 开始抢票是index=4
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ 抢票执行失败: {e}"))
            self.root.after(0, lambda: self.update_step(4, "error"))      # 开始抢票是index=4
        finally:
            self.is_grabbing = False  # 重置抢票状态
            self.root.after(0, lambda: self._reset_buttons())

    def _run_app_runner(self, config, max_retries: int) -> None:
        """App 模式抢票线程"""

        def stop_signal() -> bool:
            return self.app_should_stop

        if DamaiAppTicketRunner is None:
            self.root.after(0, lambda: self.log("❌ 当前环境未启用 Appium 运行器"))
            return

        runner = None
        try:
            runner = DamaiAppTicketRunner(
                config=config,
                logger=self._app_runner_logger,
                stop_signal=stop_signal,
            )
            success = runner.run(max_retries=max_retries)
            report = runner.get_last_report()
            stopped = self.app_should_stop
            self.root.after(
                0,
                lambda s=success, st=stopped, r=report: self._handle_app_run_result(s, st, r),
            )
        except Exception as exc:  # noqa: BLE001
            report = runner.get_last_report() if runner is not None else None
            self.root.after(
                0,
                lambda e=exc, r=report: self._handle_app_run_exception(e, r),
            )
        finally:
            self.is_grabbing = False
            self.app_runner_thread = None
            self.app_should_stop = False
            self.root.after(0, lambda: self._reset_buttons())

    def _handle_app_run_result(self, success: bool, stopped: bool, report: Optional[Any]) -> None:
        self.last_app_report = report
        self._update_app_metrics_display(report)

        metrics = getattr(report, "metrics", None)
        if metrics is not None:
            duration = max(metrics.end_time - metrics.start_time, 0.0)
            attempts = getattr(metrics, "attempts", 0)
            summary = f"尝试 {attempts} 次，耗时 {duration:.2f} 秒"
        else:
            summary = ""

        if success:
            if summary:
                self.log(f"📊 App 流程完成：{summary}")
            else:
                self.log("📊 App 流程完成")
            self.mark_step("4. 开始抢票", "completed")
            self.mark_step("5. 查看结果", "completed")
            return

        if stopped:
            self.log("⏹️ App 抢票流程已停止")
            self.mark_step("4. 开始抢票", "error")
            return

        reason = self._format_failure_for_display(report)
        self.log(f"⚠️ 未能成功抢票：{reason}")
        messagebox.showwarning("抢票未成功", reason)
        self.mark_step("4. 开始抢票", "error")
        self.mark_step("5. 查看结果", "error")

    def _handle_app_run_exception(self, exc: Exception, report: Optional[Any]) -> None:
        self.last_app_report = report
        self._update_app_metrics_display(report)
        self.log(f"❌ App 抢票异常: {exc}")
        messagebox.showerror("App 抢票异常", str(exc))
        self.mark_step("4. 开始抢票", "error")
        self.mark_step("5. 查看结果", "error")

    def _app_runner_logger(self, level: str, message: str, context=None) -> None:
        """适配 App 运行器日志到 GUI"""

        prefix = {
            "step": "🧭",
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }.get(level, "📄")

        extra = ""
        if context:
            try:
                extras = [f"{key}={value}" for key, value in context.items()]
                if extras:
                    extra = " (" + ", ".join(extras) + ")"
            except Exception:
                extra = ""

        text = f"{prefix} {message}{extra}"
        self.root.after(0, lambda: self.log(text))
            
    def _show_login_for_grabbing(self):
        """显示抢票时的登录说明"""
        login_window = tk.Toplevel(self.root)
        login_window.title("抢票登录")
        login_window.geometry("450x300")
        login_window.transient(self.root)
        login_window.grab_set()
        
        ttk.Label(login_window, text="🔐 请在浏览器中完成登录", 
                 font=self.title_font).pack(pady=20)
        
        instructions = [
            "抢票前需要登录大麦网：",
            "",
            "1. 浏览器已自动打开大麦网",
            "2. 请点击页面上的「登录」按钮",
            "3. 使用手机扫码或账号密码登录",
            "4. 登录成功后点击下方「开始抢票」按钮"
        ]
        
        for instruction in instructions:
            label = ttk.Label(login_window, text=instruction, font=self.default_font)
            label.pack(pady=2)
        
        button_frame = ttk.Frame(login_window)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="🎯 开始抢票", 
                  command=lambda: self._start_grabbing_after_login(login_window)).pack(side="left", padx=10)
        ttk.Button(button_frame, text="❌ 取消", 
                  command=lambda: self._cancel_grabbing_login(login_window)).pack(side="left", padx=10)
    
    def _start_grabbing_after_login(self, window):
        """登录后开始抢票"""
        window.destroy()
        
        # 保存cookies
        self.save_cookies()
        
        self.log("✅ 开始抢票流程...")
        # 重新启动抢票worker
        threading.Thread(target=self._grabbing_worker, daemon=True).start()
    
    def _cancel_grabbing_login(self, window):
        """取消抢票登录"""
        window.destroy()
        self.log("❌ 抢票已取消")
        self._reset_buttons()
            
    def _reset_buttons(self):
        """重置按钮状态"""
        if self.mode_var.get() == "app":
            start_state = "normal" if (self.app_env_ready and self.app_config_ready) else "disabled"
        else:
            start_state = "normal"
        self.start_btn.config(state=start_state)
        self.stop_btn.config(state="disabled")
        
    def clear_login_status(self):
        """清除登录状态"""
        result = messagebox.askyesno(
            "确认清除", 
            "确定要清除保存的登录状态吗？\n下次启动时需要重新登录。"
        )
        if result:
            self.clear_cookies()
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.update_step(1, "inactive")  # 重置登录状态
            messagebox.showinfo("完成", "登录状态已清除")
            
    def stop_grabbing(self):
        """停止抢票"""
        self.is_grabbing = False  # 设置停止标志
        if self.mode_var.get() == "app":
            self.app_should_stop = True
            self.log("⏹️ 正在请求停止 App 抢票...")
        else:
            self.log("⏹ 正在停止抢票...")
        self._reset_buttons()
        
    def show_help(self):
        """显示帮助信息"""
        help_window = tk.Toplevel(self.root)
        help_window.title("使用帮助")
        help_window.geometry("600x500")
        help_window.transient(self.root)

        help_text = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, font=self.default_font)
        help_text.pack(fill="both", expand=True, padx=10, pady=10)

        help_content = """
🎫 大麦抢票工具使用说明

🧭 模式概览：
• 网页模式 (Web)：使用 Chrome + Selenium 自动化网页端购票流程
• App 模式 (App)：通过 Appium 控制大麦 App，适合移动端极速抢票

📋 网页模式流程：
1. 环境检测 —— 检查 Python、Selenium 与 ChromeDriver 是否可用
2. 网页登录 —— 可选，可提前登录或在抢票时登录，状态会自动保存
3. 页面分析 —— 输入演出链接，自动解析城市、日期、价格等选项
4. 参数配置 —— 在界面中选择目标条件并确认
5. 开始抢票 —— 启动自动化流程，实时输出执行日志

📱 App 模式流程：
1. 环境检测 —— 校验 Python 环境与 Appium 客户端依赖
2. 设备检查 —— 请求 Appium Server /status，确认服务与设备在线
3. 参数配置 —— 选择或加载 config.jsonc/JSON，配置城市、价格、观演人
4. 开始抢票 —— 运行移动端抢票流程，可设置重试次数
5. 查看结果 —— 日志中查看 Appium 执行步骤与最终状态

🔧 关键说明：

网页模式：
• 支持自动保存/加载登录 Cookie，减少重复登录
• 页面分析无需登录即可完成，可先确认票务信息
• 观演人自动全选，支持可选的自动提交订单

App 模式前置条件：
• 已安装 Appium Server 并保持运行 (默认 http://127.0.0.1:4723)
• Android 设备已开启开发者模式并与电脑连接
• damai_appium/config.jsonc 配置正确，包含 server_url、device_caps 等
• 若设备未自动识别，请在配置中补充 deviceName、udid 等字段

App 模式小贴士：
• 先点击“重新加载”确认配置无误，再执行环境检测
• 环境检测通过后按钮会自动解锁，可随时停止流程
• 日志前缀：🧭步骤、ℹ️信息、✅成功、⚠️警告、❌异常，便于快速定位

⚠️ 通用注意事项：
• 确保网络与设备连接稳定
• 抢票前检查实名信息、观演人等是否完善
• 谨慎使用自动提交，建议保留人工确认
• 遵守大麦网条款，合理合法地使用工具

💡 使用技巧：
• 新用户推荐通过“环境检测”了解依赖情况
• 自动登录失败时，可清除登录状态后重新登录
• 多场演出可分别分析并保存日志作为参考
• 建议在开票前完成一次全流程演练
"""

        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")


def main():
    """主函数"""
    app = DamaiGUI()
    app.run()


if __name__ == "__main__":
    main()