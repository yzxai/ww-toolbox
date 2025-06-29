from pathlib import Path
from datetime import datetime
import ctypes
import os
import sys

def get_project_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.parent
    else:
        return Path(__file__).parent.parent.parent

def get_assets_dir() -> Path:
    return get_project_root() / "assets"

def get_config_dir() -> Path:
    return get_assets_dir() / "config"

def get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

def is_admin() -> bool:
    return ctypes.windll.shell32.IsUserAnAdmin() != 0

def check_privilege():
    if not is_admin():
        print("Backend is not granted with admin privilege.")
