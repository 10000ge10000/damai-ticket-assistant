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
import locale

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
            components = json.load(f)

        # 补全缺失字段，防止 UI 初始化时报 KeyError
        for comp in components:
            if 'status' not in comp or comp.get('status') is None:
                comp['status'] = '未安装'
            comp.setdefault('file', '')
            comp.setdefault('install_cmd', '')
            comp.setdefault('extract_dir', '')

        return components

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
            # 获取安装文件的实际路径
            installer_dir = resource_path("installer_files")
            self.log(f"安装文件路径: {installer_dir}")
            self.log("开始安装，请耐心等待...")
            
            # 记录系统信息，便于调试
            self.log(f"系统编码: {locale.getpreferredencoding()}")
            self.log(f"Python 版本: {sys.version}")
            self.log(f"系统平台: {sys.platform}")
            
            # 记录是否以管理员权限运行
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                self.log(f"是否以管理员身份运行: {'是' if is_admin else '否'}")
                if not is_admin:
                    self.log("警告: 未以管理员身份运行，某些组件可能安装失败")
            except:
                self.log("无法检查管理员权限")
            
            for i, component in enumerate(self.components):
                if self.components[i]["status"] == "已安装":
                    self.log(f"跳过已安装的 '{component['name']}'")
                    continue
                
                self.log(f"正在安装 '{component['name']}'...")
                try:
                    self.install_component(i, installer_dir)
                    self.update_component_status(i, "已安装")
                except Exception as e:
                    self.log(f"组件 '{component['name']}' 安装失败: {str(e)}")
                    self.update_component_status(i, "安装失败")
                    # 继续安装其他组件而不直接中止
                    continue

            # 检查是否所有组件都已安装
            all_installed = all(comp["status"] == "已安装" for comp in self.components)
            
            if all_installed:
                self.log("所有组件安装完成！")
                messagebox.showinfo("成功", "所有组件已成功安装！")
            else:
                failed_components = [comp["name"] for comp in self.components if comp["status"] != "已安装"]
                self.log(f"部分组件安装失败: {', '.join(failed_components)}")
                messagebox.showwarning("部分完成", f"以下组件安装失败: {', '.join(failed_components)}\n请查看日志获取详情")

        except Exception as e:
            self.log(f"安装失败: {str(e)}")
            self.log(f"堆栈跟踪: {traceback.format_exc()}")
            messagebox.showerror("错误", f"安装过程中发生错误: {e}")
        finally:
            self.install_btn.config(state=tk.NORMAL)
            self.check_btn.config(state=tk.NORMAL)
    
    def install_component(self, index, installer_dir):
        component = self.components[index]
        cmd = ""
        try:
            if component["type"] == "exe":
                # 使用引号包围路径防止空格问题
                path = os.path.normpath(os.path.join(installer_dir, component["file"]))
                cmd = component["install_cmd"].format(path=f'"{path}"')
            elif component["type"] == "msi":
                # MSI 安装需要特别处理路径，确保路径被正确引用
                path = os.path.normpath(os.path.join(installer_dir, component["file"]))
                # 移除命令中可能已经存在的引号，然后重新添加
                cmd = component["install_cmd"].format(path=f'"{path}"')
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
                # 使用绝对路径并确保引号正确包围带空格的路径
                wheels_dir = os.path.normpath(os.path.join(installer_dir, "wheels"))
                requirements_path = os.path.normpath(resource_path("resources/requirements.txt"))
                
                # 构建更健壮的 pip 命令，使用 --no-cache-dir 以避免编码问题
                cmd = f'pip install --no-cache-dir --no-index --find-links="{wheels_dir}" -r "{requirements_path}"'
            
            self.run_command(cmd)
        except Exception as e:
            error_msg = f"安装 {component['name']} 时发生错误: {str(e)}"
            self.log(error_msg)
            # 在组件安装失败时提供更清晰的错误消息
            if "msiexec" in str(cmd).lower():
                self.log("MSI 安装提示: 请确保您有管理员权限运行此程序")
            elif "pip" in str(cmd).lower():
                self.log("PIP 安装提示: 可能的编码问题，尝试使用 --no-cache-dir 选项")
            raise Exception(error_msg)

    def run_command(self, command):
        """运行命令并记录输出"""
        self.log(f"执行: {command}")
        # Use the system preferred encoding (on Windows this will be the ANSI code page)
        # and set errors='replace' so that decoding errors from commands (like pip)
        # won't crash the installer when the tool prints non-UTF-8 output.
        preferred_enc = locale.getpreferredencoding(False)
        # On Windows prefer 'mbcs' to match the native ANSI code page
        if os.name == 'nt':
            preferred_enc = 'mbcs'
            
        # 为特定命令使用更健壮的错误处理
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=preferred_enc,
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            # 记录命令输出
            for line in process.stdout:
                self.log(line.strip())
                
            process.wait()
            if process.returncode != 0:
                error = process.stderr.read()
                self.log(f"错误: {error}")
                
                # 添加更多调试信息以帮助诊断
                self.log(f"命令返回代码: {process.returncode}")
                if 'msiexec' in command.lower():
                    self.log("MSI 安装失败: 请尝试手动运行以获取更多信息，或确保以管理员身份运行")
                
                raise Exception(f"命令执行失败: {command}")
                
        except Exception as e:
            self.log(f"执行命令时出现异常: {str(e)}")
            self.log(f"命令: {command}")
            self.log(f"异常类型: {type(e).__name__}")
            self.log(f"堆栈跟踪: {traceback.format_exc()}")
            raise Exception(f"命令执行异常: {command}")

if __name__ == "__main__":
    app = DamaiInstaller()
    app.mainloop()