import os
import sys
import subprocess
import threading
import shutil
import zipfile
import json
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import urllib.request
import ctypes
import webbrowser
import traceback
import time

# 确保资源路径正确
def resource_path(relative_path):
    """ 获取资源绝对路径，适用于开发环境和PyInstaller打包环境 """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("./damai_installer")
    return os.path.join(base_path, relative_path)

class DamaiInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("大麦票务助手一键安装器")
        self.geometry("800x600")
        self.minsize(700, 500)
        
        self.log_lock = threading.Lock()
        self.install_thread = None
        self.stop_event = threading.Event()
        
        # 加载配置
        self.components = self.load_components_config()
        self.create_ui()
        
        # 自动检查环境
        self.after(500, self.check_environment)
    
    def load_components_config(self):
        """加载组件配置"""
        config_path = resource_path("resources/components.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def create_ui(self):
        """创建UI界面"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="大麦票务助手安装器", 
                 font=("Microsoft YaHei", 16, "bold")).pack()
        ttk.Label(header_frame, 
                 text="本工具将自动安装大麦票务助手所需的全部组件和依赖").pack()
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, padx=10, pady=5)
        
        component_frame = ttk.LabelFrame(main_frame, text="安装组件")
        component_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.component_listbox = ttk.Treeview(component_frame, 
                                             columns=("name", "type", "status"),
                                             show="headings",
                                             selectmode="browse")
        self.component_listbox.heading("name", text="组件名称")
        self.component_listbox.heading("type", text="类型")
        self.component_listbox.heading("status", text="状态")
        self.component_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        for i, component in enumerate(self.components):
            self.component_listbox.insert("", "end", values=(
                component["name"], component["type"], component["status"]
            ))
        
        log_frame = ttk.LabelFrame(main_frame, text="安装日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = ScrolledText(log_frame, height=10, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.install_btn = ttk.Button(button_frame, text="一键安装全部", 
                                     command=self.install_all)
        self.install_btn.pack(side=tk.LEFT, padx=5)
        
        self.check_btn = ttk.Button(button_frame, text="检查环境", 
                                   command=self.check_environment)
        self.check_btn.pack(side=tk.LEFT, padx=5)
    
    def log(self, message):
        """添加日志"""
        with self.log_lock:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.update_idletasks()
    
    def update_component_status(self, index, status):
        """更新组件状态"""
        self.components[index]["status"] = status
        item_id = self.component_listbox.get_children()[index]
        values = list(self.component_listbox.item(item_id, "values"))
        values[2] = status
        self.component_listbox.item(item_id, values=values)
        self.update_idletasks()
    
    def check_environment(self):
        """检查安装环境"""
        self.log("开始检查环境...")
        for i, component in enumerate(self.components):
            if "check_cmd" in component:
                try:
                    subprocess.run(
                        component["check_cmd"], shell=True, check=True, 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    self.update_component_status(i, "已安装")
                    self.log(f"'{component['name']}' 已安装")
                except:
                    self.update_component_status(i, "未安装")
                    self.log(f"'{component['name']}' 未安装")
        self.log("环境检查完成")
    
    def install_all(self):
        """安装所有组件"""
        self.install_btn.config(state=tk.DISABLED)
        self.check_btn.config(state=tk.DISABLED)
        self.install_thread = threading.Thread(target=self._install_all_thread, daemon=True)
        self.install_thread.start()
    
    def _install_all_thread(self):
        """安装线程"""
        try:
            installer_dir = resource_path("installer_files")
            self.log("开始安装，请耐心等待...")
            
            for i, component in enumerate(self.components):
                if self.components[i]["status"] == "已安装":
                    self.log(f"跳过已安装的 '{component['name']}'")
                    continue
                
                self.log(f"正在安装 '{component['name']}'...")
                self.install_component(i, installer_dir)
                self.update_component_status(i, "已安装")

            self.log("所有组件安装完成！")
            messagebox.showinfo("成功", "所有组件已成功安装！")

        except Exception as e:
            self.log(f"安装失败: {str(e)}")
            messagebox.showerror("错误", f"安装过程中发生错误: {e}")
        finally:
            self.install_btn.config(state=tk.NORMAL)
            self.check_btn.config(state=tk.NORMAL)
    
    def install_component(self, index, installer_dir):
        component = self.components[index]
        cmd = ""
        if component["type"] == "exe":
            cmd = component["install_cmd"].format(path=os.path.join(installer_dir, component["file"]))
        elif component["type"] == "msi":
            cmd = component["install_cmd"].format(path=os.path.join(installer_dir, component["file"]))
        elif component["type"] == "npm":
            cmd = component["install_cmd"]
        elif component["type"] == "zip":
            zip_path = os.path.join(installer_dir, component["file"])
            extract_dir = component["extract_dir"]
            self.log(f"解压 {zip_path} 到 {extract_dir}")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            # (此处省略添加环境变量的复杂逻辑)
            return
        elif component["type"] == "pip":
            cmd = component["install_cmd"].format(
                wheels_dir=os.path.join(installer_dir, "wheels"),
                requirements=resource_path("resources/requirements.txt")
            )
        
        self.run_command(cmd)

    def run_command(self, command):
        """运行命令并记录输出"""
        self.log(f"执行: {command}")
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8'
        )
        for line in process.stdout:
            self.log(line.strip())
        process.wait()
        if process.returncode != 0:
            error = process.stderr.read()
            self.log(f"错误: {error}")
            raise Exception(f"命令执行失败: {command}")

if __name__ == "__main__":
    app = DamaiInstaller()
    app.mainloop()