# 行动分发 — 快速处理命令参考

本文件包含各事项类型的直接处理命令和安全规则。主流程见 [SKILL.md](../SKILL.md)。

> **参数发现**：对于下方未给出完整参数的命令，执行前先用 `lark-cli schema <service>.<resource>.<method>` 查看参数结构，不要猜测字段格式。
>
> **多账号模式**：所有命令追加 `--profile <PROFILE>` 参数，路由到事项所属的企业。`<PROFILE>` 为该事项在采集阶段记录的 appId。单账号模式下可省略。

---

## 快速行动详细命令

### 回复 IM 消息

```bash
lark-cli im +messages-reply --message-id <message_id> --content '<回复文本>' --profile <PROFILE>
```

### 审批同意/拒绝

```bash
# 同意审批（POST 请求，所有参数通过 --data 传入，无需 --params）
lark-cli approval tasks approve \
  --data '{"instance_code":"<INSTANCE_CODE>","task_id":"<TASK_ID>","comment":"同意"}' \
  --profile <PROFILE>

# 拒绝审批
lark-cli approval tasks reject \
  --data '{"instance_code":"<INSTANCE_CODE>","task_id":"<TASK_ID>","comment":"<拒绝理由>"}' \
  --profile <PROFILE>
```

> `instance_code` 和 `task_id` 来自采集阶段 `approval tasks query` 的返回结果。`comment` 为审批意见，可为空字符串。API 自动使用当前登录用户身份，无需传 `user_id`。

### 回复文档评论

```bash
# 先查参数结构
lark-cli schema drive.file.comment.replys.create

# 回复评论
lark-cli drive file.comment.replys create \
  --params '{"file_token":"<FILE_TOKEN>","file_type":"<FILE_TYPE>","comment_id":"<COMMENT_ID>"}' \
  --data '{"content":{"elements":[{"type":"text_run","text_run":{"text":"<回复内容>"}}]}}' \
  --profile <PROFILE>
```

> `file_token`、`file_type`、`comment_id` 来自采集阶段文档评论扫描的返回结果。如参数结构与上述不符，以 `lark-cli schema` 返回为准。

### 回复邮件

```bash
# 默认存草稿（不发送）
lark-cli mail +reply --message-id <message_id> --body '<p>回复内容</p>' --profile <PROFILE>

# 用户确认后才加 --confirm-send 真正发送
lark-cli mail +reply --message-id <message_id> --body '<p>回复内容</p>' --confirm-send --profile <PROFILE>
```

### 回复日程邀请（RSVP）

```bash
# 接受
lark-cli calendar +rsvp --event-id <event_id> --rsvp-status accept --profile <PROFILE>

# 拒绝
lark-cli calendar +rsvp --event-id <event_id> --rsvp-status decline --profile <PROFILE>

# 暂定
lark-cli calendar +rsvp --event-id <event_id> --rsvp-status tentative --profile <PROFILE>
```

---

## 安全规则

所有写操作都涉及对外发送或状态变更，一旦执行不可撤回。因此每个行动都必须经过用户确认：

- **回复消息**：先展示回复内容草稿，用户说"发吧"后执行
- **审批操作**：明确展示审批单摘要和操作（同意/拒绝），用户确认后执行
- **邮件回复**：先展示回复草稿。默认只存草稿（不发送），用户确认后加 `--confirm-send` 才真正发送
- **文档评论回复**：先展示回复内容，用户确认后提交
- **日程 RSVP**：展示日程标题和操作（接受/拒绝/暂定），用户确认后执行

---

## 任务创建

```bash
lark-cli task +create \
  --summary "<任务标题>" \
  --description "<任务描述，包含来源上下文>" \
  --assignee "<MY_OPEN_ID>" \
  --due "<截止时间>" \
  --profile <PROFILE>
```

### 标题规范

动词开头，简洁明确：
- "回复张三关于 PR 的评审意见"
- "整理需求文档并发送给开发团队"
- "处理王五在方案文档中的评论"

### 截止时间推断

| 来源 | 推断规则 |
|------|---------|
| 原始消息/会议提到了 deadline | 使用该时间 |
| 今天收到的消息，未指定 deadline | 今天 18:00 |
| 文档评论 | 明天 18:00 |
| 审批单 | 今天 18:00（审批通常有时效性） |

### 批量创建

用户说"全部建任务"时，逐个创建并报告结果（任务 ID + 链接）。

---

## 权限表

| 命令 | 所需 scope |
|------|-----------|
| `im +messages-reply --profile <PROFILE>` | `im:message:create_as_user` |
| `approval tasks approve/reject --profile <PROFILE>` | `approval:task:write` |
| `drive file.comment.replys create --profile <PROFILE>` | `docs:document.comment:create` |
| `mail +reply --profile <PROFILE>` | `mail:user_mailbox.message:send` |
| `calendar +rsvp --profile <PROFILE>` | `calendar:calendar.event:reply` |
| `task +create --profile <PROFILE>` | `task:task:write` |

> 每个 profile 的 scope 是独立的。某个 profile 缺少 scope 时，仅影响该 profile 下的操作，不影响其他 profile。
