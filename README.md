# Git Commit Logger | Git Commit 索引工具

Git post-commit hook + SQLite 索引工具。每次 commit 自动记录元数据到本地 SQLite，支持跨仓库查询、统计和管理。

## 功能

- **自动记录** — git post-commit hook 自动写入 commit 元数据
- **跨仓库查询** — 按 hash、仓库、作者、日期、分支筛选
- **统计** — 按仓库/作者聚合统计
- **CRUD** — 支持 record/delete/update 操作
- **全局模式** — 新 repo 自动安装 hook
- **排除规则** — fnmatch 通配符排除指定路径

## 快速开始

```bash
# 1. 部署到 ~/.commit-logs/
mkdir -p ~/.commit-logs
cp scripts/*.py scripts/config.toml ~/.commit-logs/

# 2. 安装 hook 到当前 repo
uv run python ~/.commit-logs/install.py .

# 3. 创建一个 commit，数据自动入库

# 4. 查询
uv run python ~/.commit-logs/query.py list
uv run python ~/.commit-logs/query.py find <hash>
uv run python ~/.commit-logs/query.py stats
```

## 作者

- **Author**: [LeeShunEE](https://github.com/LeeShunEE)
- **Organization**: [KinemaClawWorkspace](https://github.com/KinemaClawWorkspace)

## 许可证

[GNU General Public License v3.0](LICENSE)
