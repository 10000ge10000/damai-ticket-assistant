import os
import urllib.request
import sys

INSTALLER_FILES = {
    "python": {
        "url": "https://www.python.org/ftp/python/3.11.6/python-3.11.6-amd64.exe",
        "filename": "python-3.11.6-amd64.exe"
    },
    "nodejs": {
        "url": "https://nodejs.org/dist/v18.18.2/node-v18.18.2-x64.msi",
        "filename": "node-v18.18.2-x64.msi"
    },
    "platform-tools": {
        "url": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
        "filename": "platform-tools-latest-windows.zip"
    }
}

def download_file(url, destination):
    print(f"下载: {url} -> {destination}")
    urllib.request.urlretrieve(url, destination)

def main():
    install_dir = os.path.join("damai_installer", "installer_files")
    os.makedirs(install_dir, exist_ok=True)
    
    for name, info in INSTALLER_FILES.items():
        target_path = os.path.join(install_dir, info["filename"])
        if os.path.exists(target_path):
            print(f"'{info['filename']}' 已存在, 跳过下载。")
            continue
        try:
            download_file(info["url"], target_path)
        except Exception as e:
            print(f"下载 '{name}' 失败: {e}", file=sys.stderr)
            sys.exit(1)
            
    print("所有文件下载完成。")

if __name__ == "__main__":
    main()