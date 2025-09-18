# -*- coding: utf-8 -*-
"""
大麦抢票 GUI 工具
一键式图形界面抢票工具，适合小白用户使用
"""

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


class DamaiGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("大麦抢票工具 v2.0")
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
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
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
        
    def create_steps_frame(self, parent, row):
        """创建步骤显示框架"""
        steps_frame = ttk.LabelFrame(parent, text="📋 操作步骤", padding="10")
        steps_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.steps = [
            "1. 环境检测",
            "2. 网页登录",
            "3. 页面分析", 
            "4. 参数配置",
            "5. 开始抢票"
        ]
        
        self.step_labels = []
        for i, step in enumerate(self.steps):
            label = ttk.Label(steps_frame, text=step, foreground="gray", font=self.default_font)
            label.grid(row=0, column=i, padx=10)
            self.step_labels.append(label)
            
        # 添加分隔符
        for i in range(len(self.steps) - 1):
            sep = ttk.Label(steps_frame, text="→", foreground="gray", font=self.default_font)
            sep.grid(row=0, column=len(self.steps) + i, padx=5)
    
    def create_main_functions(self, parent, row):
        """创建主要功能区域"""
        # 左侧功能面板
        left_frame = ttk.LabelFrame(parent, text="🔧 功能面板", padding="10")
        left_frame.grid(row=row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # 环境检测区域
        env_frame = ttk.LabelFrame(left_frame, text="环境检测", padding="5")
        env_frame.pack(fill="x", pady=(0, 10))
        
        self.env_status_label = ttk.Label(env_frame, text="点击检测环境", foreground="orange", font=self.default_font)
        self.env_status_label.pack()
        
        self.check_env_btn = ttk.Button(env_frame, text="🔍 检测环境", command=self.check_environment)
        self.check_env_btn.pack(pady=5)
        
        # URL输入区域
        url_frame = ttk.LabelFrame(left_frame, text="演出链接", padding="5")
        url_frame.pack(fill="x", pady=(0, 10))
        
        self.url_entry = ttk.Entry(url_frame, width=50, font=self.default_font)
        self.url_entry.pack(fill="x", pady=2)
        self.url_entry.insert(0, "请输入大麦网演出详情页链接...")
        self.url_entry.bind("<FocusIn>", self.clear_url_placeholder)
        
        url_buttons_frame = ttk.Frame(url_frame)
        url_buttons_frame.pack(fill="x", pady=5)
        
        self.login_btn = ttk.Button(url_buttons_frame, text="🔐 网页登录", 
                                   command=self.web_login, state="disabled")
        self.login_btn.pack(side="left", padx=(0, 5))
        
        self.analyze_btn = ttk.Button(url_buttons_frame, text="🔍 分析页面", 
                                     command=self.analyze_page, state="disabled")
        self.analyze_btn.pack(side="left")
        
        # 配置区域
        config_frame = ttk.LabelFrame(left_frame, text="抢票配置", padding="5")
        config_frame.pack(fill="x", pady=(0, 10))
        
        self.config_label = ttk.Label(config_frame, text="请先分析页面", foreground="gray", font=self.default_font)
        self.config_label.pack()
        
        # 右侧信息面板 - 改为运行日志
        right_frame = ttk.LabelFrame(parent, text="📝 运行日志", padding="10")
        right_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        self.log_text = scrolledtext.ScrolledText(right_frame, height=15, width=40, font=self.default_font)
        self.log_text.pack(fill="both", expand=True)
        
        # 初始日志
        self.log("🚀 大麦抢票工具启动成功")
        self.log("💡 提示：请先检测环境，然后输入演出链接进行分析")
        self.log("ℹ️ 登录为可选项，可在抢票时再进行登录")
        
        # 启动定期保存cookie功能
        self.root.after(30000, self.auto_save_cookies_if_needed)  # 30秒后开始第一次检查
        
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
                
    def log(self, message):
        """添加日志信息"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_url_placeholder(self, event):
        """清除URL输入框占位符"""
        if self.url_entry.get() == "请输入大麦网演出详情页链接...":
            self.url_entry.delete(0, tk.END)
            
    def check_environment(self):
        """检测环境"""
        self.update_step(0, "active")
        self.log("🔍 开始检测环境...")
        
        try:
            # 检测Python版本
            python_version = sys.version.split()[0]
            self.log(f"✅ Python版本: {python_version}")
            
            # 检测selenium
            if SELENIUM_AVAILABLE:
                self.log("✅ Selenium已安装")
            else:
                self.log("❌ Selenium未安装")
                self.env_status_label.config(text="环境检测失败", foreground="red")
                self.update_step(0, "error")
                messagebox.showerror("错误", "Selenium未安装，请先安装：pip install selenium")
                return
                
            # 检测Chrome
            try:
                options = webdriver.ChromeOptions()
                options.add_argument('--headless')
                driver = webdriver.Chrome(options=options)
                driver.quit()
                self.log("✅ Chrome浏览器驱动正常")
            except Exception as e:
                self.log(f"❌ Chrome驱动检测失败: {e}")
                self.env_status_label.config(text="Chrome驱动异常", foreground="red")
                self.update_step(0, "error")
                messagebox.showerror("错误", f"Chrome驱动检测失败:\n{e}")
                return
                
        except Exception as e:
            self.log(f"❌ 环境检测出错: {e}")
            self.env_status_label.config(text="环境检测异常", foreground="red")
            self.update_step(0, "error")
            return
            
        # 启用功能按钮
        self.login_btn.config(state="normal")
        self.analyze_btn.config(state="normal")
        
        self.env_status_label.config(text="环境检测完成", foreground="green")
        self.update_step(0, "completed")
        self.log("✅ 环境检测完成，所有组件正常")
        
        # 尝试自动加载已保存的登录状态
        self._try_auto_login()
        
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
        if not self.config:
            messagebox.showwarning("警告", "请先完成页面分析和参数配置")
            return
            
        # 如果没有driver，提示用户将在抢票过程中登录
        if not self.driver:
            result = messagebox.askyesno(
                "登录确认", 
                '您还未登录大麦网。\n\n点击"是"开始抢票（抢票过程中会弹出登录窗口）\n点击"否"取消操作'
            )
            if not result:
                return
            self.log("ℹ️ 将在抢票过程中进行登录")
            
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.is_grabbing = True  # 设置抢票状态
        self.log("🎯 开始执行抢票...")
        
        # 在新线程中执行抢票
        threading.Thread(target=self._grabbing_worker, daemon=True).start()
        
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
        self.start_btn.config(state="normal")
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

📋 基本流程：
1. 环境检测 - 检查Python和Chrome环境，自动尝试登录
2. 网页登录 - 可选项，也可在抢票时登录，登录状态会自动保存
3. 页面分析 - 输入演出链接并分析可选项
4. 参数配置 - 选择城市、日期、价格等
5. 开始抢票 - 自动执行抢票流程

🔧 详细说明：

环境检测：
• 检查Python版本和必要模块
• 验证Chrome浏览器驱动
• 自动尝试加载已保存的登录状态
• 确保抢票环境正常

网页登录：
• 登录为可选项，不是必须的
• 可以在抢票时再进行登录
• 首次登录成功后会自动保存登录状态
• 下次启动时会自动尝试免登录
• 建议提前登录以提高成功率

Cookie管理：
• 登录状态会自动保存为cookie文件
• 启动时自动尝试使用保存的登录状态
• 可以手动清除登录状态重新登录
• Cookie文件位置：damai_cookies.pkl

页面分析：
• 输入大麦网演出详情页链接
• 自动分析可选的城市、日期、价格
• 无需登录即可进行页面分析

参数配置：
• 根据分析结果选择抢票参数
• 购买数量固定为1张
• 观演人自动选择全部

开始抢票：
• 如未登录会提示登录
• 自动执行完整抢票流程
• 包含弹窗处理和智能重试

⚠️ 注意事项：
• 确保网络连接稳定
• 抢票前确认个人信息完整
• 谨慎使用自动提交订单功能
• 遵守大麦网使用条款
• 登录状态有效期约7-30天

💡 技巧：
• 首次使用时完成登录，后续启动会自动登录
• 如果自动登录失败，可清除登录状态重新登录
• 可以先做页面分析再决定是否登录
• 多个演出可以分别分析和配置
• 建议在演出开票前测试环境
"""
        
        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")


def main():
    """主函数"""
    app = DamaiGUI()
    app.run()


if __name__ == "__main__":
    main()