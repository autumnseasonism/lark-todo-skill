#!/bin/bash
# lark-todo 综合测试集
# 覆盖：命令可用性、响应结构、两路文档搜索、增量扫描、行动命令、边界情况

TODAY=$(date +%Y-%m-%d)
NOW_HOUR=$(date +%H)
PASS=0
FAIL=0
TOTAL=0
ERRORS=""

check() {
  local name="$1"
  local cmd="$2"
  local expect="$3"
  TOTAL=$((TOTAL + 1))
  cmd="${cmd//<TODAY>/$TODAY}"
  output=$(eval "$cmd" 2>&1)
  exit_code=$?
  if echo "$output" | grep -qF -- "$expect"; then
    echo "  PASS  $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (exit=$exit_code, expected '$expect')"
    ERRORS="$ERRORS\n--- $name ---\ncmd: $cmd\nexpect: $expect\noutput (200 chars): ${output:0:200}\n"
    FAIL=$((FAIL + 1))
  fi
}

check_not() {
  local name="$1"
  local cmd="$2"
  local not_expect="$3"
  TOTAL=$((TOTAL + 1))
  cmd="${cmd//<TODAY>/$TODAY}"
  output=$(eval "$cmd" 2>&1)
  if echo "$output" | grep -qF -- "$not_expect"; then
    echo "  FAIL  $name (should NOT contain '$not_expect')"
    ERRORS="$ERRORS\n--- $name ---\ncmd: $cmd\nnot_expect: $not_expect\n"
    FAIL=$((FAIL + 1))
  else
    echo "  PASS  $name"
    PASS=$((PASS + 1))
  fi
}

check_json_field() {
  local name="$1"
  local cmd="$2"
  local field="$3"
  TOTAL=$((TOTAL + 1))
  cmd="${cmd//<TODAY>/$TODAY}"
  output=$(eval "$cmd" 2>&1)
  if echo "$output" | grep -qF -- "\"$field\""; then
    echo "  PASS  $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (missing field '$field')"
    ERRORS="$ERRORS\n--- $name ---\ncmd: $cmd\nmissing_field: $field\noutput (200 chars): ${output:0:200}\n"
    FAIL=$((FAIL + 1))
  fi
}

echo "========================================================"
echo " lark-todo 综合测试集"
echo " Date: $TODAY  Hour: $NOW_HOUR"
echo "========================================================"

# ─────────────────────────────────────────────
echo ""
echo "[1/8] 启动检查 — config & auth"
echo "--------------------------------------------------------"
check "config show 有 appId" \
  'lark-cli config show' \
  'appId'

check "auth status 是 user 身份" \
  'lark-cli auth status' \
  '"identity": "user"'

check "contact +get-user 返回 open_id" \
  'lark-cli contact +get-user --format json' \
  '"open_id"'

check "contact +get-user 返回 name" \
  'lark-cli contact +get-user --format json' \
  '"name"'

# ─────────────────────────────────────────────
echo ""
echo "[2/8] 数据源采集 — 7 个数据源命令可用性"
echo "--------------------------------------------------------"
check "IM 消息搜索" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T00:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"ok": true'

check "会议搜索" \
  'lark-cli vc +search --start "<TODAY>" --end "<TODAY>" --format json --page-size 30' \
  '"ok": true'

check "日程查询" \
  'lark-cli calendar +agenda --format json' \
  '"ok": true'

check "审批查询" \
  "lark-cli approval tasks query --params '{\"topic\":\"1\"}' --format json" \
  '"msg": "success"'

check "任务查询" \
  'lark-cli task +get-my-tasks --complete=false --due-end "<TODAY>T23:59:59+08:00" --format json' \
  '"ok": true'

check "邮件查询" \
  "lark-cli mail +triage --filter '{\"folder\":\"inbox\",\"is_unread\":true,\"time_range\":{\"start_time\":\"<TODAY>T00:00:00+08:00\",\"end_time\":\"<TODAY>T23:59:59+08:00\"}}' --max 20 --format json" \
  '"messages"'

check "文档搜索（通用）" \
  "lark-cli docs +search --filter '{\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"},\"sort_type\":\"OPEN_TIME\"}' --format json" \
  '"ok": true'

# ─────────────────────────────────────────────
echo ""
echo "[3/8] 文档两路搜索策略"
echo "--------------------------------------------------------"

MY_OPEN_ID=$(lark-cli contact +get-user --format json 2>/dev/null | grep -o '"open_id": "[^"]*"' | head -1 | cut -d'"' -f4)
MY_NAME=$(lark-cli contact +get-user --format json 2>/dev/null | grep -o '"name": "[^"]*"' | head -1 | cut -d'"' -f4)

check "路线一：我创建的文档（creator_ids 过滤）" \
  "lark-cli docs +search --filter '{\"creator_ids\":[\"$MY_OPEN_ID\"],\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"},\"sort_type\":\"OPEN_TIME\"}' --format json" \
  '"ok": true'

check "路线二：评论中 @我的文档（only_comment 过滤）" \
  "lark-cli docs +search --query '$MY_NAME' --filter '{\"only_comment\":true,\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"}}' --format json" \
  '"ok": true'

check "文档搜索结果含 token 字段" \
  "lark-cli docs +search --filter '{\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"},\"sort_type\":\"OPEN_TIME\"}' --format json" \
  '"token"'

# ─────────────────────────────────────────────
echo ""
echo "[4/8] 增量扫描 — 不同时间范围"
echo "--------------------------------------------------------"
check "增量：下午 12:00 起" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T12:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"ok": true'

HOUR_2AGO=$(printf "%02d" $((NOW_HOUR > 2 ? NOW_HOUR - 2 : 0)))
check "增量：最近 2 小时" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T'$HOUR_2AGO':00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"ok": true'

check "增量：邮件下午起" \
  "lark-cli mail +triage --filter '{\"folder\":\"inbox\",\"is_unread\":true,\"time_range\":{\"start_time\":\"<TODAY>T12:00:00+08:00\",\"end_time\":\"<TODAY>T23:59:59+08:00\"}}' --max 20 --format json" \
  '"messages"'

# ─────────────────────────────────────────────
echo ""
echo "[5/8] 行动命令 — 参数名验证"
echo "--------------------------------------------------------"
check "im +messages-reply 有 --message-id" \
  'lark-cli im +messages-reply -h' \
  '--message-id'

check "im +messages-reply 有 --content" \
  'lark-cli im +messages-reply -h' \
  '--content'

check "approval.tasks.approve 有 instance_code" \
  'lark-cli schema approval.tasks.approve' \
  '"instance_code"'

check "approval.tasks.approve 有 task_id" \
  'lark-cli schema approval.tasks.approve' \
  '"task_id"'

check "approval.tasks.approve 是 POST" \
  'lark-cli schema approval.tasks.approve' \
  '"httpMethod": "POST"'

check "approval.tasks.reject 有 instance_code" \
  'lark-cli schema approval.tasks.reject' \
  '"instance_code"'

check "drive comment reply 有 comment_id" \
  'lark-cli schema drive.file.comment.replys.create' \
  '"comment_id"'

check "drive comment reply 有 file_token" \
  'lark-cli schema drive.file.comment.replys.create' \
  '"file_token"'

check "mail +reply 有 --confirm-send" \
  'lark-cli mail +reply -h' \
  '--confirm-send'

check "mail +reply 有 --body" \
  'lark-cli mail +reply -h' \
  '--body'

check "calendar +rsvp 有 --rsvp-status" \
  'lark-cli calendar +rsvp -h' \
  '--rsvp-status'

check "calendar +rsvp 有 --event-id" \
  'lark-cli calendar +rsvp -h' \
  '--event-id'

check "task +create 有 --summary" \
  'lark-cli task +create -h' \
  '--summary'

check "task +create 有 --assignee" \
  'lark-cli task +create -h' \
  '--assignee'

check "task +create 有 --due" \
  'lark-cli task +create -h' \
  '--due'

# ─────────────────────────────────────────────
echo ""
echo "[6/8] 响应结构验证 — JSON 关键字段"
echo "--------------------------------------------------------"
check_json_field "IM 搜索结果含 messages 数组" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T00:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  "messages"

check_json_field "IM 搜索结果含 has_more" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T00:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  "has_more"

check_json_field "日程结果含 event_id" \
  'lark-cli calendar +agenda --format json' \
  "event_id"

check_json_field "日程结果含 self_rsvp_status" \
  'lark-cli calendar +agenda --format json' \
  "self_rsvp_status"

check_json_field "审批结果含 tasks 数组" \
  "lark-cli approval tasks query --params '{\"topic\":\"1\"}' --format json" \
  "tasks"

check_json_field "任务结果含 has_more" \
  'lark-cli task +get-my-tasks --complete=false --due-end "<TODAY>T23:59:59+08:00" --format json' \
  "has_more"

# ─────────────────────────────────────────────
echo ""
echo "[7/8] 边界情况 — 错误处理"
echo "--------------------------------------------------------"
check "无效 topic 值仍返回结构化响应" \
  "lark-cli approval tasks query --params '{\"topic\":\"999\"}' --format json" \
  '"code"'

check_not "IM 搜索不返回 error（权限正常）" \
  'lark-cli im +messages-search --is-at-me --start "<TODAY>T00:00:00+08:00" --end "<TODAY>T23:59:59+08:00" --page-all --format json' \
  '"type": "missing_scope"'

check_not "docs +search 不返回 error（权限正常）" \
  "lark-cli docs +search --filter '{\"open_time\":{\"start\":\"<TODAY>T00:00:00+08:00\"},\"sort_type\":\"OPEN_TIME\"}' --format json" \
  '"type": "missing_scope"'

# ─────────────────────────────────────────────
echo ""
echo "[8/8] 会议纪要链路 — vc +notes 参数验证"
echo "--------------------------------------------------------"
check "vc +notes 有 --meeting-ids 参数" \
  'lark-cli vc +notes -h' \
  '--meeting-ids'

check "vc +notes 有 --minute-tokens 参数" \
  'lark-cli vc +notes -h' \
  '--minute-tokens'

check "vc +recording 有 --meeting-ids 参数" \
  'lark-cli vc +recording -h' \
  '--meeting-ids'

# ─────────────────────────────────────────────
echo ""
echo "========================================================"
echo " Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================================"

if [ $FAIL -gt 0 ]; then
  echo ""
  echo "FAILURES:"
  echo -e "$ERRORS"
  exit 1
fi
