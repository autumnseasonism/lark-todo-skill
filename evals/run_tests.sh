#!/bin/bash
# 待办行动扫描器 — 命令验证测试
# 验证所有 CLI 命令可执行、返回格式正确、参数名无误

TODAY=$(date +%Y-%m-%d)
PASS=0
FAIL=0
ERRORS=""

check() {
  local name="$1"
  local cmd="$2"
  local expect="$3"

  # 替换 <TODAY> 占位符
  cmd="${cmd//<TODAY>/$TODAY}"

  output=$(eval "$cmd" 2>&1)
  exit_code=$?

  # 检查期望字符串是否出现在输出中
  if echo "$output" | grep -qF -- "$expect"; then
    echo "  PASS  $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (exit=$exit_code, expected '$expect')"
    ERRORS="$ERRORS\n--- $name ---\ncmd: $cmd\nexpect: $expect\noutput (first 200 chars): ${output:0:200}\n"
    FAIL=$((FAIL + 1))
  fi
}

echo "================================================"
echo " Test Suite: lark-todo"
echo " Date: $TODAY"
echo "================================================"
echo ""

echo "[Test 1] 全量扫描 — 7 个数据源命令"
echo "------------------------------------------------"
check "contact +get-user" \
  'lark-cli contact +get-user --format json' \
  '"open_id"'

check "im +messages-search" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T00:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"ok": true'

check "vc +search" \
  'lark-cli vc +search --start "<TODAY>" --end "<TODAY>" --format json --page-size 30' \
  '"ok": true'

check "calendar +agenda" \
  'lark-cli calendar +agenda --format json' \
  '"ok": true'

check "docs +search" \
  "lark-cli docs +search --filter '{\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"},\"sort_type\":\"OPEN_TIME\"}' --format json" \
  '"ok": true'

check "approval tasks query" \
  "lark-cli approval tasks query --params '{\"topic\":\"1\"}' --format json" \
  '"code": 0'

check "task +get-my-tasks" \
  'lark-cli task +get-my-tasks --complete=false --due-end "<TODAY>T23:59:59+08:00" --format json' \
  '"ok": true'

check "mail +triage" \
  "lark-cli mail +triage --filter '{\"folder\":\"inbox\",\"is_unread\":true,\"time_range\":{\"start_time\":\"<TODAY>T00:00:00+08:00\",\"end_time\":\"<TODAY>T23:59:59+08:00\"}}' --max 20 --format json" \
  '"messages"'

echo ""
echo "[Test 2] 行动命令 — 参数名验证"
echo "------------------------------------------------"
check "im +messages-reply -h" \
  'lark-cli im +messages-reply -h' \
  '--message-id'

check "approval.tasks.approve schema" \
  'lark-cli schema approval.tasks.approve' \
  '"instance_code"'

check "approval.tasks.reject schema" \
  'lark-cli schema approval.tasks.reject' \
  '"instance_code"'

check "drive.file.comment.replys.create schema" \
  'lark-cli schema drive.file.comment.replys.create' \
  '"comment_id"'

check "mail +reply -h" \
  'lark-cli mail +reply -h' \
  '--confirm-send'

check "calendar +rsvp -h" \
  'lark-cli calendar +rsvp -h' \
  '--rsvp-status'

check "task +create -h" \
  'lark-cli task +create -h' \
  '--summary'

echo ""
echo "[Test 3] 增量扫描 — 缩窄时间范围"
echo "------------------------------------------------"
check "im incremental (12:00+)" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T12:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"ok": true'

check "mail incremental (12:00+)" \
  "lark-cli mail +triage --filter '{\"folder\":\"inbox\",\"is_unread\":true,\"time_range\":{\"start_time\":\"<TODAY>T12:00:00+08:00\",\"end_time\":\"<TODAY>T23:59:59+08:00\"}}' --max 20 --format json" \
  '"messages"'

echo ""
echo "================================================"
echo " Results: $PASS passed, $FAIL failed"
echo "================================================"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "FAILURES:"
  echo -e "$ERRORS"
  exit 1
fi
