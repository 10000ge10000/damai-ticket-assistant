# -*- coding: utf-8 -*-
"""
大麦抢票工具 - 无窗口启动器
使用pythonw启动，避免显示CMD窗口
"""
import subprocess
import sys
import os

def main():
    try:
        # 获取脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gui_script = os.path.join(script_dir, "damai_gui.py")
        
        # 使用pythonw启动GUI，不显示CMD窗口
        subprocess.Popen([
            sys.executable.replace("python.exe", "pythonw.exe"),
            gui_script
        ], cwd=script_dir)
        
    except Exception as e:
        # 如果出错，显示错误信息
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("启动失败", f"无法启动大麦抢票工具:\n{e}")
        root.destroy()

if __name__ == "__main__":
    main()