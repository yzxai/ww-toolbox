from setuptools import setup, Extension
import sys
import os

# 尝试导入pybind11，如果失败则使用空配置
try:
    import pybind11
    PB_INCLUDE_DIRS = [pybind11.get_include()]
    PB_AVAILABLE = True
except ImportError:
    PB_INCLUDE_DIRS = []
    PB_AVAILABLE = False

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

# 根据pybind11可用性决定是否构建C++扩展
if PB_AVAILABLE:
    ext_modules = [
        Extension(
            "profile_cpp",
            [os.path.join("toolbox", "core", "profile.cpp")],
            include_dirs=PB_INCLUDE_DIRS,
            language="c++",
            extra_compile_args=["-std=c++17", "-O2"] if sys.platform != "win32" else ["/std:c++17", "/O2"],
        ),
    ]
else:
    ext_modules = []

setup(
    name="toolbox",
    version="0.5.1",
    description="A toolbox with fast C++ backend for profile calculations.",
    ext_modules=ext_modules,
    install_requires=requirements,
    packages=["toolbox"],
    zip_safe=False,
)
