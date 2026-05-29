# Git Log Tracker | Git Commit 索引工具

Git post-commit hook + SQLite 索引工具。每次 commit 自动记录元数据到本地 SQLite，支持跨仓库查询、统计和管理。

## 功能

- **自动记录** — git post-commit hook 自动写入 commit 元数据
- **跨仓库查询** — 按 hash、仓库、作者、日期、分支筛选
- **统计** — 按仓库/作者聚合统计
- **CRUD** — 支持 record/delete/update 操作
- **全局模式** — 新 repo 自动安装 hook
- **排除规则** — fnmatch 通配符排除指定路径
- **重装功能** — 支持重置数据目录或仅重置数据库

## 安装

```bash
# 从本地安装
uv tools install D:/modular_dev/kinema_skills/git-log-tracker/src

# 或从 git 仓库安装
uv tools install git+https://github.com/KinemaClawWorkspace/git-log-tracker.git
```

## 快速开始

```bash
# 1. 初始化配置和数据库
git-log-tracker setup

# 2. 安装 hook 到当前 repo
git-log-tracker install .

# 3. 创建一个 commit，数据自动入库

# 4. 查询
git-log-tracker list
git-log-tracker find <hash>
git-log-tracker stats
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `setup` | 初始化配置和数据库 |
| `install <repo>` | 安装 hook 到指定仓库 |
| `uninstall <repo>` | 从指定仓库移除 hook |
| `status <repo>` | 检查仓库 hook 状态 |
| `global [--off]` | 配置全局 git 模板 |
| `find <hash>` | 按 hash 查找 commit |
| `list` | 列出最近的 commits |
| `stats` | 显示统计信息 |
| `record [repo]` | 手动记录最新 commit |
| `delete <hash>` | 删除 commit 记录 |
| `update <hash> <field> <value>` | 更新 commit 字段 |
| `reinstall [--keep-config]` | 重置数据目录并重新初始化 |
| `hook` | 运行 hook 逻辑 (由 post-commit 调用) |

## 作者

- **Author**: [LeeShunEE](https://github.com/LeeShunEE)
- **Organization**: [KinemaClawWorkspace](https://github.com/KinemaClawWorkspace)

## 许可证

[GNU General Public License v3.0](LICENSE)