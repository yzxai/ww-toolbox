# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.




创建一个专业的GitHub Actions工作流YAML文件，用于Windows平台下Python应用的自动化编译、打包、测试和发布流程。工作流必须实现以下技术规范和功能要求：

技术环境配置：
- 运行环境：windows-latest
- 触发条件：push到main分支、pull_request创建/更新、手动workflow_dispatch
- 工作流名称：Build Windows EXE
- 权限配置：contents: write, actions: read, security-events: write

构建生命周期实现：
1. 环境初始化阶段：
   - 检出代码并设置Python环境（支持多版本矩阵：3.9, 3.10, 3.11）
   - 配置环境变量和系统路径
   - 初始化构建时间戳和版本号

2. 依赖管理优化：
   - 智能缓存pip依赖包（基于requirements.txt哈希值）
   - 缓存预编译的wheel包
   - 虚拟环境创建与依赖安装验证
   - 依赖安全漏洞扫描

3. 构建与打包阶段：
   - 代码质量检查（flake8, black, mypy）
   - 单元测试执行与覆盖率报告
   - PyInstaller优化配置（单文件模式、图标嵌入、版本信息）
   - UPX压缩优化（可选）
   - 构建产物完整性校验（SHA256）

4. 验证与测试阶段：
   - EXE文件功能性测试
   - 依赖库完整性验证
   - Windows兼容性测试
   - 性能基准测试
   - 安全扫描（bandit, safety）

5. 发布与部署阶段：
   - 自动版本号管理（基于git tag或commit）
   - 创建GitHub Release
   - 上传构建产物（EXE、日志、测试报告）
   - 生成changelog
   - 清理临时文件和缓存

高级功能特性：
- 并行构建支持
- 构建矩阵策略
- 条件执行逻辑
- 失败重试机制
- 详细的构建状态通知（邮件、Slack、Teams）
- 构建超时控制
- 资源使用监控
- 环境变量安全管理（GitHub Secrets）
- 构建产物自动清理策略

代码质量保障：
- YAML语法严格验证
- 工作流步骤原子化设计
- 错误处理和日志记录
- 构建状态持久化
- 诊断信息收集
- 性能指标追踪

输出要求：
- 生成可直接使用的YAML文件
- 代码注释详尽清晰
- 支持多模块项目结构
- 兼容主流Python GUI框架（PyQt/PySide, Tkinter, Kivy等）
- 提供构建配置的灵活性和可扩展性

确保生成的YAML文件具备生产级别的稳定性、安全性和可维护性，支持企业级CI/CD流水线集成。


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
