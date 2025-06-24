# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import rapidocr
import openvino

package_name = 'rapidocr'
install_dir = Path(rapidocr.__file__).resolve().parent
openvino_dir = Path(openvino.__file__).resolve().parent

onnx_paths = list(install_dir.rglob('*.onnx'))
dll_paths = list(openvino_dir.rglob('*.dll'))
yaml_paths = list(install_dir.rglob('*.yaml'))

onnx_add_data = [(str(v.parent), f'{package_name}/{v.parent.name}')
                 for v in onnx_paths]

yaml_add_data = []

dll_add_data = []

for v in dll_paths:
    if 'openvino' == v.parent.name:
        dll_add_data.append((str(v.parent / '*.dll'), 'openvino'))
    else:
        dll_add_data.append(
            (str(v.parent / '*.dll'), f'openvino/{v.parent.name}')) 

for v in yaml_paths:
    if package_name == v.parent.name:
        yaml_add_data.append((str(v.parent / '*.yaml'), package_name))
    else:
        yaml_add_data.append(
            (str(v.parent / '*.yaml'), f'{package_name}/{v.parent.name}'))

add_data = list(set(yaml_add_data + onnx_add_data + dll_add_data))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=add_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
