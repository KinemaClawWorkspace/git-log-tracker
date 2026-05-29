# Git Commit Logger Onboarding

> 本文档指导 AI Agent 完成首次环境配置。按顺序执行，遇到问题时参考 Troubleshooting。

## Prerequisites | 前置条件

- Python 3.11+（需要 `tomllib` 标准库支持）
- `uv` 包管理器
- Git

## Step 1: 部署脚本到 ~/.commit-logs/

### 检测

```bash
test -f ~/.commit-logs/hook.py && echo "INSTALLED" || echo "NOT_INSTALLED"
```

### 安装

将 `scripts/` 目录下的所有文件复制到 `~/.commit-logs/`：

```bash
# 从 skill 仓库复制（agent 运行时替换 <skill_dir> 为实际路径）
mkdir -p ~/.commit-logs
cp <skill_dir>/scripts/hook.py ~/.commit-logs/
cp <skill_dir>/scripts/db.py ~/.commit-logs/
cp <skill_dir>/scripts/install.py ~/.commit-logs/
cp <skill_dir>/scripts/query.py ~/.commit-logs/
cp <skill_dir>/scripts/setup_global.py ~/.commit-logs/
```

如果 `~/.commit-logs/config.toml` 不存在，复制默认配置：

```bash
test -f ~/.commit-logs/config.toml || cp <skill_dir>/scripts/config.toml ~/.commit-logs/config.toml
```

### 验证

```bash
ls ~/.commit-logs/hook.py ~/.commit-logs/db.py ~/.commit-logs/install.py ~/.commit-logs/query.py ~/.commit-logs/setup_global.py
# 应输出 5 个文件路径
```

## Step 2: 验证 Python 环境

### 检测

```bash
python --version
# 期望: Python 3.11.x 或更高
```

### 安装

如未安装 Python 3.11+：

```bash
uv python install 3.11
```

### 验证

```bash
uv run python ~/.commit-logs/query.py --help
# 期望: 显示 query.py 帮助信息
```

## Step 3: 初始化数据库

### 检测

```bash
test -f ~/.commit-logs/index.db && echo "DB_EXISTS" || echo "NO_DB"
```

### 安装

数据库会在首次使用时自动创建，也可手动初始化：

```bash
uv run python -c "
import sys; sys.path.insert(0, '$HOME/.commit-logs')
from db import get_connection; get_connection(); print('DB initialized')
"
```

### 验证

```bash
uv run python ~/.commit-logs/query.py stats
# 期望: Total commits: 0
```

## Step 4: 安装 Hook 到当前 Repo

### 检测

```bash
uv run python ~/.commit-logs/install.py --status .
```

### 安装

```bash
uv run python ~/.commit-logs/install.py .
```

### 验证

```bash
uv run python ~/.commit-logs/install.py --status .
# 期望: Status: installed [<repo_path>]
```

## Troubleshooting | 故障排除

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `No module named 'tomllib'` | Python < 3.11 | 安装 Python 3.11+ 或 `uv pip install tomli` |
| `uv: command not found` | uv 未安装 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Hook not triggering` | hook 文件无执行权限 | `chmod +x .git/hooks/post-commit` |
| `database is locked` | 多进程并发写入 | 等待其他操作完成，SQLite 自动处理 |
| `No commits found` | 数据库为空或排除规则过滤了 repo | 检查 `~/.commit-logs/config.toml` 中的 exclude 列表 |
| `Multiple commits match prefix` | hash 前缀太短 | 使用更长的 hash 前缀或完整 hash |
