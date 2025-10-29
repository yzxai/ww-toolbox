# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.



为Python项目创建一个完整的GitHub Actions工作流配置文件，专用于Windows平台的自动化构建和EXE打包流程。该工作流需在云端环境中独立运行，完全隔离本地环境依赖，提供企业级的构建质量和稳定性保障。工作流必须包含完整的构建生命周期管理：环境准备与缓存优化、多版本Python矩阵构建、依赖管理与虚拟环境配置、PyInstaller打包优化、全面的构建验证与测试、产物管理与发布流程。工作流应命名为"Build Windows EXE"，在push到main分支或创建pull_request时触发，运行于windows-latest环境，并支持以下核心功能：智能缓存依赖加速构建、多Python版本并行构建矩阵、详细的构建日志与错误报告、EXE文件完整性验证、自动上传构建产物到GitHub Releases、构建失败时的详细诊断信息、安全性扫描与代码质量检查、环境变量的安全管理、构建资源的自动清理、以及完整的构建状态通知。要求生成的YAML文件语法完美、结构清晰、零错误零警告，可直接应用于生产环境，支持持续集成和持续部署流程。



## Project Overview

Wuthering Waves Toolbox is a CV-based automation tool for the game "Wuthering Waves". It provides holistic analysis and automation features including customizable echo analysis, echo scan, and upgrade automation with optimal resource management.

**Architecture**: Hybrid desktop application with:
- **Backend**: Python (FastAPI) + C++ extension (via pybind11)
- **Frontend**: Electron application
- **Build System**: PyInstaller for Windows distribution

## Quick Start

### Development Setup

```bash
# Create Python virtual environment
conda create -n ww-toolbox python=3.11
conda activate ww-toolbox

# Install Python dependencies and build C++ extension
pip install -e .

# Setup frontend dependencies
cd frontend
npm install

# Run the application
cd frontend
npm start .
```

### Build for Production

```bash
# Build executable using PyInstaller
pyinstaller main.spec
```

The executable will be created in `dist/main/`.

## Code Architecture

### Backend Structure (`/toolbox/`)

**Core Components** (`toolbox/core/`):
- `api.py`: FastAPI endpoints that handle HTTP requests from frontend
- `profile.py`: Echo profile calculations with C++ backend (`profile.cpp`)
- `interaction.py`: Game interaction via Windows API (screenshots, clicks, OCR)

**Task System** (`toolbox/tasks/`):
- `base_task.py`: Abstract base class for all automated tasks
- `echo_task.py`: Page navigation and UI interaction logic
- `echo_scan.py`: Scan and collect echo data from game
- `echo_manipulate.py`: Automated echo upgrade/management
- `echo_search.py`, `echo_punch.py`, `echo_discard.py`: Specific automation tasks

**Utilities** (`toolbox/utils/`):
- `ocr.py`: OCR setup and utilities using RapidOCR
- `logger.py`: Colored logging with HTTP log handler
- `generic.py`: Utility functions (privilege check, paths, timestamps)

**C++ Extension** (`toolbox/core/profile.cpp`):
- Performance-critical profile calculations
- Built via pybind11 as `profile_cpp` module
- Exports: `EchoProfile`, `EntryCoef`, `DiscardScheduler` classes

### Frontend Structure (`/frontend/`)

- `main.js`: Electron main process
- `preload.js`: Security bridge between main and renderer
- `index.html`: Main UI
- `page1.html/js`: Echo management interface
- Uses Tailwind CSS + Material Design Icons

## Key Dependencies

### Python Backend
- `fastapi` + `uvicorn`: Web server
- `pybind11`: C++ binding generator
- `rapidocr`: OCR engine (with OpenVINO/ONNX runtime)
- `Pillow`: Image processing
- `numpy`: Numerical operations
- `pywin32`: Windows API access

### Frontend
- `electron`: Desktop app framework
- `tailwindcss`: CSS framework

## Common Development Tasks

### Modifying the C++ Extension

The C++ code is in `toolbox/core/profile.cpp`:
- Compile with: `pip install -e .` (runs setup.py)
- Changes are automatically compiled on install
- Must restart Python backend after changes

### Adding New Echo Tasks

1. Create new task file in `toolbox/tasks/` (e.g., `echo_new_feature.py`)
2. Inherit from `BaseTask` or `EchoTask`
3. Implement required methods
4. Register in `toolbox/core/api.py`

Example pattern:
```python
from toolbox.tasks.base_task import BaseTask

class NewEchoTask(BaseTask):
    def run(self, **kwargs):
        # Implementation
        pass
```

### Working with OCR

OCR is configured in `toolbox/utils/ocr.py`:
- Uses RapidOCR with OpenVINO backend
- Pattern matching in `ocr_pattern()`
- Game elements defined in `toolbox/core/interaction.py`

### Logging

Access logger via `toolbox.utils.logger`:
- Colored console output
- HTTP log handler on port 2590
- Configure with DEBUG env var for verbose logs

## Configuration Files

- `requirements.txt`: Python dependencies
- `main.spec`: PyInstaller build configuration
- `.gitignore`: Build artifacts, logs, node_modules
- `assets/`: Game assets (icons, templates)
- `docs/`: Documentation and screenshots

## Important Notes

### Requirements
- **Windows x86 only** (for game compatibility)
- Python 3.8+ (tested on 3.11)
- Visual Studio Build Tools (for C++ compilation)
- Node.js (for frontend)
- Administrator privileges (required for game screen capture)

### Game Integration
- Application requires admin rights to capture game window
- Uses Windows-specific APIs via pywin32
- OCR regions configured for 1920x1080 (adjust in `interaction.py` if needed)

### Performance
- C++ extension handles CPU-intensive profile calculations
- OpenVINO acceleration available if CUDA installed
- Async task management via FastAPI

### Testing Resources
Test images in `toolbox/utils/tests/`:
- `test.png`: General screenshot
- `test-level.png`: Level display
- `test-match.png`: Echo matching
- `test-rect*.png`: UI rectangles
- `test-template.png`: Template matching

## API Reference

### Core Endpoints (toolbox/core/api.py)

- `POST /api/stop_work`: Cancel current automation task
- `POST /api/filter`: Apply echo filter and analyze
- `GET /api/scan`: Scan echo data from game
- `POST /api/manual`: Start manual echo manipulation mode
- `POST /api/discard`: Discard selected echoes

### Data Structures

- `EchoProfile`: Echo statistics and analysis
- `EntryCoef`: Statistical coefficients for calculations
- `DiscardScheduler`: Waste management strategy
- `AnalysisResult`: Score predictions and probabilities

## Troubleshooting

### Build Issues
- **C++ compilation fails**: Ensure Visual Studio Build Tools installed
- **Module not found**: Re-run `pip install -e .`
- **Frontend won't start**: Check `npm install` in frontend directory

### Runtime Issues
- **OCR fails**: Check game window is active and visible
- **Permission errors**: Run as Administrator
- **Port already in use**: Change port in `main.py` or kill existing process

### Game Compatibility
- **Window detection fails**: Check game is running in windowed mode
- **Screenshots black**: Verify admin privileges
- **UI detection off**: Adjust OCR regions in `interaction.py`
