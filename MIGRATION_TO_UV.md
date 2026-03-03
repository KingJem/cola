# 从 Poetry 迁移到 uv

本文档记录了 Cola 项目从 Poetry 迁移到 uv 包管理工具的过程。

## 为什么选择 uv？

uv 是一个极快的 Python 包管理工具，具有以下优势：

- ⚡ **极快的速度** - 比 pip 和 Poetry 快 10-100 倍
- 🔒 **可靠的依赖解析** - 更准确的依赖版本锁定
- 🎯 **简单易用** - 更简洁的命令和配置
- 🚀 **现代化** - 支持最新的 Python 打包标准（PEP 621）

## 迁移步骤

### 1. 更新 pyproject.toml

从 Poetry 格式：
```toml
[tool.poetry]
name = "cola"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.8"
aiohttp = "^3.8.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

转换为 PEP 621 标准格式（uv 兼容）：
```toml
[project]
name = "cola"
version = "0.1.0"
requires-python = ">=3.8"
dependencies = [
    "aiohttp>=3.8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

### 2. 删除 Poetry 文件

```bash
rm poetry.lock
```

### 3. 初始化 uv 并同步依赖

```bash
uv sync
```

这将：
- 创建 `uv.lock` 文件
- 安装所有依赖到虚拟环境
- 创建或更新 `.venv` 目录

## 常用命令对比

| 操作 | Poetry | uv |
|------|--------|-----|
| 安装依赖 | `poetry install` | `uv sync` |
| 添加依赖 | `poetry add package` | `uv add package` |
| 添加开发依赖 | `poetry add --dev package` | `uv add --dev package` |
| 运行脚本 | `poetry run python script.py` | `uv run python script.py` |
| 激活虚拟环境 | `poetry shell` | `source .venv/bin/activate` |
| 更新依赖 | `poetry update` | `uv sync --upgrade` |
| 导出依赖 | `poetry export -f requirements.txt` | `uv pip compile pyproject.toml` |

## 验证迁移

运行测试确保一切正常：

```bash
# 使用 uv 运行测试
uv run pytest tests/

# 运行示例爬虫
cd demo_project
uv run python run.py
```

## 项目结构变化

### 文件变化

- ❌ `poetry.lock` - 已删除
- ✅ `uv.lock` - 新创建（uv 的锁文件）
- ✅ `pyproject.toml` - 已更新为 PEP 621 格式
- ✅ `.venv/` - 虚拟环境（如果不存在会自动创建）

### pyproject.toml 主要变化

1. **项目元数据** - 从 `[tool.poetry]` 移到 `[project]`
2. **依赖声明** - 从 Poetry 的 `^` 版本语法改为标准的 `>=` 语法
3. **构建系统** - 从 `poetry-core` 改为 `hatchling`
4. **包配置** - 添加 `[tool.hatch.build.targets.wheel]` 指定 src 目录

## 文档更新

以下文档已更新，将 Poetry 命令替换为 uv：

- ✅ [README.md](README.md)
- ✅ [USER_GUIDE.md](USER_GUIDE.md)
- ✅ [demo_project/README.md](demo_project/README.md)

## 优势总结

迁移到 uv 后的改进：

1. **安装速度提升** - 依赖安装速度提升 10-100 倍
2. **标准兼容** - 使用 PEP 621 标准，与 Python 生态更兼容
3. **简化工作流** - 命令更简洁，配置更清晰
4. **更好的性能** - 特别是在 CI/CD 环境中效果明显

## 注意事项

1. **虚拟环境位置** - uv 默认在项目根目录创建 `.venv`，而 Poetry 通常在其缓存目录
2. **版本语法** - 依赖版本从 `^3.8.0` 改为 `>=3.8.0`
3. **构建后端** - 从 `poetry-core` 改为 `hatchling`（更标准的选择）

## 回退方案

如果需要回退到 Poetry：

1. 恢复旧的 `pyproject.toml`
2. 删除 `uv.lock` 和 `.venv`
3. 运行 `poetry install`

---

**迁移完成！** 🎉

现在可以使用 `uv sync` 来安装依赖，使用 `uv run` 来运行脚本。
