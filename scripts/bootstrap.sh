#!/usr/bin/env bash
# lark-todo 依赖自动装配
#
# 职责：保证 lark-cli 在 PATH 中可用。已装则直接跳过；缺失则尝试 npm 自动安装；
# 连 Node.js/npm 都没有时给出清晰的前置指引后退出。
#
# 退出码约定（SKILL.md Step 0 据此分支）：
#   0  lark-cli 可用（已存在或刚装上）→ 继续 Step A
#   2  缺少 Node.js 或 npm → 无法自动安装，提示用户先装 Node
#   3  npm install 失败或装完仍不在 PATH → 提示用户手动处理
#
# 只读副作用：命令日志全部写到 stderr（前缀 [lark-todo/bootstrap]），stdout 保持干净。

set -u

log() { printf '[lark-todo/bootstrap] %s\n' "$*" >&2; }

# 1) 已装？直接返回 0（幂等）
if command -v lark-cli >/dev/null 2>&1; then
  ver=$(lark-cli --version 2>/dev/null | head -1)
  log "lark-cli 已存在：${ver:-(version unknown)}"
  exit 0
fi

# 2) node / npm 任一缺失：不做自动安装，打印前置指引
missing=()
command -v node >/dev/null 2>&1 || missing+=("node")
command -v npm  >/dev/null 2>&1 || missing+=("npm")
if [ "${#missing[@]}" -gt 0 ]; then
  log "未检测到：${missing[*]}。lark-cli 依赖 npm 全局安装。"
  log "请先安装 Node.js（建议 >= 18）：https://nodejs.org/"
  log "安装完成并重开 shell 后，可再次执行本脚本或手动："
  log "  npm install -g @larksuite/cli"
  exit 2
fi

# 3) 自动 npm install
log "未检测到 lark-cli，准备通过 npm 全局安装 @larksuite/cli"
log "命令：npm install -g @larksuite/cli"
if npm install -g @larksuite/cli >&2; then
  # 安装成功后再验一次：有时全局 bin 不在当前 shell 的 PATH 里（常见于 Linux 自定义 prefix）
  if command -v lark-cli >/dev/null 2>&1; then
    ver=$(lark-cli --version 2>/dev/null | head -1)
    log "安装成功：${ver:-(version unknown)}"
    exit 0
  fi
  log "npm install 返回成功，但 lark-cli 仍不在当前 PATH。"
  log "通常是 npm 全局 bin 目录未加入 PATH：请执行 'npm prefix -g' 查看目录，"
  log "将其下的 bin 加入 PATH 后重开 shell 再试。"
  exit 3
fi

log "npm install 失败。常见原因与对策："
log "  · 权限问题（macOS/Linux）：尝试 'sudo npm install -g @larksuite/cli'"
log "      或配置 npm 用户级 prefix（npm config set prefix ~/.npm-global）后重试"
log "  · 网络问题：换镜像 'npm install -g @larksuite/cli --registry=https://registry.npmmirror.com'"
log "  · 企业代理：先设 HTTP(S)_PROXY 再重试"
exit 3
