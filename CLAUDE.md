# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


为当前项目创建一个GitHub Actions工作流YAML文件，专门针对Windows平台进行项目构建。工作流需在云端环境中运行，严格避免任何对本地环境的修改或依赖。请确保YAML配置文件语法正确、结构完整，包含从环境初始化、依赖安装到构建执行的全部必要步骤。工作流应仅支持Windows操作系统，涵盖完整的构建生命周期管理，包括但不限于环境变量设置、工具链安装、项目编译及构建结果验证。要求一次性提供完整、准确且可直接运行的工作流配置，确保零错误、零警告，能够稳定通过GitHub Actions的自动化执行，无需后续调试或修改。



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
