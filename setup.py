from setuptools import setup, Extension
import sys
import os
import pybind11

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

ext_modules = [
    Extension(
        "profile_cpp",
        [os.path.join("toolbox", "core", "profile.cpp")],
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
    install_requires=requirements,
    packages=["toolbox"],
    zip_safe=False,
)
