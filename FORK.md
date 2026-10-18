# 这个 fork 是什么

`hs-t/portal-mcp-server` 是 [`TMYTiMidlY/portal-mcp-server`](https://github.com/TMYTiMidlY/portal-mcp-server)
的个人 fork，用于**自己用 + 本地改造**。

两条硬规则：

1. **不向上游提交**。`upstream` remote 只 fetch，从不 push（没有开 PR）。
2. **跟上游走**。上游有新提交时合并进来，而不是把自己的改动变基掉。

# 相对上游的改动

| 改动 | 位置 | 动机 |
|---|---|---|
| 日志目录不可写时不再让 `import` 崩溃 | `portal_mcp_server/paths.py`(`ensure_log_dir`)、`audit.py`、`cli.py` | 原实现 `audit.py` 在模块导入期裸调 `mkdir`；只读 home / 受限 `%LOCALAPPDATA%` 下 `import portal_mcp_server` 直接抛 `PermissionError`，连带把用户用来修问题的 `portal` CLI 也带崩。现在降级为**每次操作 fail-closed**（保持原有的安全语义）并给出可操作提示（`PORTAL_LOG_DIR`）。 |
| 日志不可用时的错误消息指明怎么修 | `audit.py` | 原来只说 "Audit write failed"，不告诉你去设哪个变量。 |
| 测试骨架的 Windows 兼容 | `tests/conftest.py`、`tests/test_paths.py` | 测试用 `HOME` 做隔离（POSIX 惯例），但 Windows 的 `expanduser()` 认 `USERPROFILE`，导致 ~45 个用例在 Windows 上假失败。加了一个仅当 `HOME` 被显式改写时生效的 `~` 解析 shim。 |
| 新增回归测试 | `tests/test_log_dir_resilience.py` | 其中一条用子进程真实复现"日志目录是普通文件时 import 仍成功"。 |
| 上游同步 workflow | `.github/workflows/sync-upstream.yml` | 见下节。 |

# 跟上游同步

自动（推荐）：`.github/workflows/sync-upstream.yml` 每天 03:17 UTC 把
`upstream/main` **合并**进 `main` 并推送；冲突则 job 失败并报错，不会丢弃任何一侧。

首次需要在 fork 上启用：Actions 标签页 → 启用 workflow，且
Settings → Actions → General → Workflow permissions 选 **Read and write**。

手动：

```bash
git fetch upstream
git merge upstream/main          # 合并，不要 rebase —— rebase 会重写本地提交
git push origin main
```

想看上游有什么新东西、但先不合并：

```bash
git fetch upstream
git log --oneline HEAD..upstream/main
git diff --stat HEAD..upstream/main
```

# 在这台机器上怎么跑

开发环境（`uv` 由 `vx` 按需提供，不污染 PATH）：

```bash
vx uv sync --all-extras
vx uv run python -m pytest tests/ -q -n 8
vx uv run ruff check portal_mcp_server/ tests/
```

安装成 DSH 的 MCP server：见 `portal-mcp-dsh-bundle/`（DSH profile 插件包，配置
`@deepseek-ai/dsh-mcp-client`，stdio 传输）。关键点：`%LOCALAPPDATA%\portal-mcp-server`
在受限环境下不可写，因此 bundle 显式把 `PORTAL_LOG_DIR` 和三个 `PORTAL_*_YAML`
指到可写目录。

> 上游 schema 版本为 v4.0.3；本 fork 不改工具签名，装了就能直接替换。

# 已知局限（Windows 本机）

- `pytest` 仍有 33 个失败，全部是 **POSIX 语义用例**：`password_command` 用
  `printf`/`echo` 的 shell 语法、以及用 `monkeypatch.setattr(sys.platform, ...)`
  模拟 systemd/launchd 的用例（`platformdirs`/`pathlib` 仍是 Windows，模拟不成立）。
  这些在 Linux CI 上通过；我没有用 `skip` 掩盖它们。基线见 `.portal/baseline-fails.txt`。
- 凭据 agent（`portal ssh set ...` 的无回显输入）需要 `schtasks` 登录任务，本机未安装；
  只用 key / ssh-agent 或 `hosts.yaml` 的 `*_command` 来源。
