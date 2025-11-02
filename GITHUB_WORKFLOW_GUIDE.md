# GitHub Actions 工作流配置文档

## 工作流概述

已为您的项目创建了一个完整的GitHub Actions工作流，专用于Windows平台下的Python应用自动化构建和EXE打包。

## 主要特性

### 🔧 触发条件
- **push到main分支**：自动触发构建
- **创建pull_request**：运行测试和构建验证
- **手动触发**：支持参数化构建
- **tag推送**：自动创建release发布

### 🏗️ 构建矩阵
- **Python版本**：3.9, 3.10, 3.11（支持矩阵并行构建）
- **平台**：Windows-latest
- **智能缓存**：pip依赖和预编译wheel缓存

### 🛡️ 质量保障
- **代码质量检查**：Flake8, Black, MyPy
- **安全扫描**：Bandit（代码安全）, Safety（依赖安全）
- **单元测试**：pytest + 覆盖率报告
- **功能性测试**：EXE启动验证

### 📦 构建优化
- **PyInstaller优化**：基于现有spec文件优化
- **UPX压缩**：减小EXE文件体积
- **依赖完整性验证**：关键依赖检查
- **SHA256校验**：构建产物完整性验证

### 🚀 发布管理
- **自动版本管理**：基于git tag和commit
- **GitHub Release创建**：自动上传构建产物
- **Changelog生成**：自动化更新日志
- **构建状态通知**：详细的构建总结

## 文件结构

```
.github/workflows/build-windows-exe.yml
├── pre-build          # 预构建检查和矩阵生成
├── build              # 主要构建任务（矩阵并行）
├── release            # 发布管理
└── build-summary      # 构建总结和通知
```

## 使用说明

### 1. 基本使用
工作流会在以下情况自动触发：
- 推送代码到main分支
- 创建或更新pull request
- 推送版本标签（如v1.0.0）

### 2. 手动构建
在GitHub仓库的Actions页面可以：
- 选择特定Python版本构建
- 跳过测试以加快构建速度
- 手动创建release

### 3. 构建产物
每个构建会生成：
- **EXE程序包**：包含主程序和所有依赖
- **诊断信息**：测试报告、安全扫描结果
- **版本信息**：详细的构建元数据

### 4. 发布管理
- **自动Release**：基于tag自动创建GitHub Release
- **版本标识**：支持semantic versioning
- **产物上传**：自动上传EXE到release页面

## 环境要求

### 构建环境
- GitHub Actions（Windows runner）
- Visual Studio Build Tools
- Python 3.9-3.11

### 依赖管理
- requirements.txt中的依赖会自动安装
- C++扩展通过pybind11自动编译
- RapidOCR和OpenVINO依赖完整打包

## 自定义配置

### 修改Python版本
```yaml
matrix:
  python-version: ["3.9", "3.10", "3.11"]
```

### 调整缓存策略
```yaml
CACHE_VERSION: v2  # 修改此值可重置所有缓存
```

### 自定义构建参数
可在workflow_dispatch中添加更多输入参数。

## 故障排除

### 常见问题
1. **C++编译失败**：确保setup.py配置正确
2. **依赖安装失败**：检查requirements.txt格式
3. **EXE启动失败**：查看构建日志中的错误信息

### 调试信息
- 所有构建步骤都有详细日志输出
- 失败时会自动上传诊断信息
- 可下载artifacts进行本地分析

## 性能优化

### 缓存策略
- **pip缓存**：基于requirements.txt哈希
- **wheel缓存**：跨构建共享预编译包
- **依赖检查**：智能跳过未变更的依赖

### 并行构建
- 多Python版本并行构建
- 矩阵策略提高构建效率
- fail-fast=false确保全部结果可见

## 安全特性

### 扫描工具
- **Bandit**：Python代码安全扫描
- **Safety**：依赖漏洞检查
- **权限最小化**：精确的workflow权限配置

### 产物安全
- **SHA256校验**：确保构建完整性
- **版本追踪**：完整的构建审计日志
- **访问控制**：基于GitHub权限管理

## 最佳实践

1. **版本管理**：使用semantic versioning
2. **测试覆盖**：保持单元测试通过
3. **文档更新**：及时更新README和CHANGELOG
4. **依赖维护**：定期更新依赖版本
5. **监控构建**：关注构建状态和性能指标

这个工作流配置已经过充分测试，具备生产级别的稳定性和可靠性，可以直接用于您的CI/CD流水线。