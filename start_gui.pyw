#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI启动器 - 简单版本
直接启动GUI程序，无额外检测和提示
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from damai_gui import main
    main()
except ImportError as e:
    import tkinter as tk
    from tkinter import messagebox
    
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    messagebox.showerror(
        "依赖缺失", 
        f"缺少必要的依赖库！\n\n错误信息：{e}\n\n请先运行 '安装依赖.bat' 或\n手动执行：pip install -r requirements.txt"
    )
    sys.exit(1)
except Exception as e:
    import tkinter as tk
    from tkinter import messagebox
    
    root = tk.Tk()
    root.withdraw()
    
    messagebox.showerror(
        "启动失败", 
        f"程序启动失败！\n\n错误信息：{e}\n\n请检查文件完整性或运行 '一键启动GUI版本.bat'"
    )
    sys.exit(1)
