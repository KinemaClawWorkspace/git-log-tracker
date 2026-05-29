---
name: git-log-tracker
displayName: "Git Log Tracker (Commit Index & Query CLI)"
version: 0.1.0
description: |
  Git post-commit hook + SQLite commit index tool. Automatically records every commit's metadata (hash, author, branch, repo, subject) into a local SQLite database, then provides a CLI to query, list, stats, delete, and update records.
  Trigger: managing git hooks, querying commit history across repos, finding which repo a commit belongs to, viewing commit statistics, recording commits to a local index.
  Use this skill whenever the user mentions commit logging, commit indexing, finding commits across repos, git hook management, or wants to query their commit history in a structured way — even if they don't explicitly name the tool.
---

# Git Log Tracker

- **Author**: [LeeShunEE](https://github.com/LeeShunEE)
- **Organization**: [KinemaClawWorkspace](https://github.com/KinemaClawWorkspace)
- **GitHub**: https://github.com/KinemaClawWorkspace/git-commit-logger

## ⚠️ Before First Use | 首次使用必读

**首次使用此 skill 前，必须先读取 [ONBOARDING.md](ONBOARDING.md) 完成环境配置。**

- **首次配置** → 读取 ONBOARDING.md 完成全部步骤
- **环境不可用**（命令不存在、依赖缺失、连接失败）→ 读取 ONBOARDING.md Troubleshooting 排查修复
- **配置完成后** → 直接使用下方 Run Commands

## Overview

Git Commit Logger 在每次 `git commit` 后自动将 commit 元数据写入本地 SQLite 数据库。通过 CLI 可以跨仓库查询、统计、修改和删除 commit 记录。

数据存储在 `~/.commit-logs/index.db`，配置文件在 `~/.commit-logs/config.toml`。

## Run Commands

所有命令通过 `uv run python ~/.commit-logs/<script>.py` 运行。

### Hook 管理

安装 hook 到指定 repo（之后每次 commit 自动记录）：

```bash
uv run python ~/.commit-logs/install.py /path/to/repo
uv run python ~/.commit-logs/install.py .                              # 当前 repo
```

检查 hook 状态：

```bash
uv run python ~/.commit-logs/install.py --status /path/to/repo
```

移除 hook：

```bash
uv run python ~/.commit-logs/install.py --uninstall /path/to/repo
```

全局模式（新 repo 自动带 hook）：

```bash
uv run python ~/.commit-logs/setup_global.py          # 启用
uv run python ~/.commit-logs/setup_global.py --off     # 关闭
```

### 数据查询

按 hash 查找（支持前缀匹配）：

```bash
uv run python ~/.commit-logs/query.py find abc1234
```

`find` 输出示例：
```
commit  abc1234def5678901234567890123456789012
author  Lee <lee@example.com>
date    2025-05-29T14:30:00+08:00
repo    D:/modular_dev/task-tracker
branch  master
subject test(frontend): Phase 4 完成
```

列出最近 commit：

```bash
uv run python ~/.commit-logs/query.py list                     # 最近 20 条
uv run python ~/.commit-logs/query.py list -n 50               # 最近 50 条
uv run python ~/.commit-logs/query.py list --repo task-tracker  # 按仓库名筛选
uv run python ~/.commit-logs/query.py list --author lee@example.com  # 按作者筛选
uv run python ~/.commit-logs/query.py list --since 2025-01-01   # 按日期筛选
uv run python ~/.commit-logs/query.py list --branch main        # 按分支筛选
```

`list` 输出为表格格式：`HASH | DATE | AUTHOR | REPO | SUBJECT`

统计信息：

```bash
uv run python ~/.commit-logs/query.py stats
```

### 数据修改

手动记录某个 repo 的最新 commit：

```bash
uv run python ~/.commit-logs/query.py record .           # 当前 repo
uv run python ~/.commit-logs/query.py record /path/to/repo
```

删除记录：

```bash
uv run python ~/.commit-logs/query.py delete abc1234
```

更新记录字段（可编辑字段：branch, commit_subject, commit_body, repo_path, repo_name）：

```bash
uv run python ~/.commit-logs/query.py update abc1234 branch main
```

### 配置

编辑 `~/.commit-logs/config.toml` 管理排除列表：

```toml
[hooks]
exclude = [
    "/tmp/*",
    # "/path/to/specific/repo",
]

[database]
path = "index.db"
```

## Architecture

```
~/.commit-logs/
├── config.toml         # 排除列表和数据库路径配置
├── index.db            # SQLite 数据库（自动创建）
├── hook.py             # post-commit hook 入口
├── db.py               # 共享数据库工具
├── install.py          # hook 安装/移除/状态
├── query.py            # 查询 CLI (find/list/stats/record/delete/update)
└── setup_global.py     # 全局 git template 配置
```

## SQLite Schema

```sql
commits(
    id, commit_hash, short_hash, author_name, author_email, author_ts,
    committer_name, committer_email, commit_subject, commit_body,
    branch, repo_path, repo_name, parent_hashes, recorded_at
)
```

索引：`commit_hash`(UNIQUE), `repo_path`, `author_email`, `recorded_at`
