from setuptools import setup, Extension
import sys
import os
import pybind11

ext_modules = [
    Extension(
        "profile_cpp",
        [os.path.join("toolbox", "config", "profile.cpp")],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=["-std=c++17"] if sys.platform != "win32" else ["/std:c++17"],
    ),
]

setup(
    name="toolbox",
    version="0.1.0",
    description="A toolbox with fast C++ backend for profile calculations.",
    ext_modules=ext_modules,
    install_requires=["pybind11"],
    packages=["toolbox"],
    zip_safe=False,
)
