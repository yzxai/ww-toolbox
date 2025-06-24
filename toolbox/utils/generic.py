from pathlib import Path
from datetime import datetime
import ctypes
import os
import sys

def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent

def get_assets_dir() -> Path:
    return get_project_root() / "assets"

def get_config_dir() -> Path:
    return get_project_root() / "assets" / "config"

def get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

def is_admin() -> bool:
    return ctypes.windll.shell32.IsUserAnAdmin() != 0

def run_as_admin():
    if is_admin():
        return
    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
    except Exception as e:
        print(f'Failed to run as admin: {e}')
    sys.exit(0)
