# lark-todo

[English](README_EN.md)

**lark-todo** 是一个基于 [lark-cli](https://github.com/larksuite/cli) 的 AI Agent 技能（Skill），适用于 [Claude Code](https://claude.com/claude-code)、[Trae](https://www.trae.cn/)、[Cline](https://cline.bot/) 等支持 SKILL.md 规范的 Agent 应用。它帮你一键扫描飞书全平台上需要处理的事项，按优先级排列后支持直接处理或创建任务。

> "看看今天有啥还没干的活么" — 说完这句话，剩下的交给它。

## 它能做什么

每次触发时，lark-todo 会并行扫描飞书 7 个数据源：

| 数据源 | 找什么 |
|--------|--------|
| IM 消息 | @我的消息中需要回应的 |
| 会议纪要 | 已结束会议中分配给我的待办 |
| 今日日程 | 未开始的会议、待确认的邀请 |
| 文档评论 | 我的文档上未解决的评论、@我的评论 |
| 审批任务 | 等我处理的审批单 |
| 已有任务 | 今天到期或已过期的未完成任务 |
| 未读邮件 | 需要回复的邮件 |

然后：
- **研判** — 按紧急程度排序，关联今日日程，跨源去重
- **行动** — 能当场解决的直接处理（回复消息、批审批、回邮件），不能的创建飞书任务

## 前置条件

- 支持 SKILL.md 规范的 Agent 应用（如 Claude Code、Trae、Cline 等）
- [lark-cli](https://github.com/larksuite/cli) >= 1.0.9
- 一个飞书自建应用（首次使用时会引导配置）

## 安装

将 `lark-todo` 目录放到 Agent 应用能扫描到的 skills 路径下：

**Claude Code**

```bash
# 方式一：放在项目目录（自动发现）
git clone https://github.com/autumnseasonism/lark-todo-skill.git

# 方式二：放在全局 skills 目录
git clone https://github.com/autumnseasonism/lark-todo-skill.git ~/.agents/skills/lark-todo
```

**Trae / Cline / 其他 Agent**

将 `lark-todo` 目录放到对应 Agent 的 skills 扫描路径下，具体路径请参考各 Agent 的文档。

## 使用

在 Agent 中直接说：

- "看看今天有啥活"
- "有人找我吗"
- "扫一下待办"
- "下午有啥新的"（增量扫描）
- "收工前再扫一遍"

### 首次使用

首次使用时，技能会自动引导你完成三步初始化：

1. **应用配置** — 绑定飞书自建应用（`lark-cli config init`）
2. **用户授权** — 用你的飞书账号登录，一次性授权所有需要的权限
3. **命令白名单**（Claude Code）— 将 `lark-cli` 加入白名单，避免反复弹确认框

三步完成后，后续使用不再需要任何配置。

### 扫描结果示例

```
## 今日待处理事项（2026-04-16 星期三）全量扫描

### 即将到来的日程
  15:00-16:00 方案评审（待确认 — 需回复邀请）
   └─ 关联：第 3 项消息与此会议相关，建议提前处理

### 待处理事项

1. [紧急] [产品群] 张三：请帮忙 review 一下这个 PR（4小时前未回复）
   └─ 来源：消息 | 建议：直接回复
2. [紧急] 完成季度报告（已过期 2 天）
   └─ 来源：飞书任务
3. [普通] [采购审批] 申请人：小明，14:30 提交
   └─ 来源：审批 | 建议：直接审批
4. [低优先级] [方案文档] 王五评论：建议补充性能测试数据
   └─ 来源：文档评论 | 修改建议：在第3节补充压测结果

---
共 4 项（紧急 2 / 普通 1 / 低优先级 1）
输入序号直接处理，或说"全部建任务"。
```

### 直接处理

选择序号后，技能会根据事项类型自动选择最合适的处理方式：

| 事项 | 直接处理 |
|------|---------|
| IM 消息 | 拟好回复草稿 → 你确认 → 发送 |
| 审批单 | 展示摘要 → 你确认同意/拒绝 → 执行 |
| 文档评论 | 拟好回复 → 你确认 → 提交 |
| 邮件 | 拟好回复 → 你确认 → 发送（默认存草稿） |
| 日程邀请 | 展示详情 → 你确认接受/拒绝 → 回复 |
| 会议待办 | 创建飞书任务 |

所有写操作都会先展示给你确认，不会自动执行。

## 文件结构

```
lark-todo/
├── SKILL.md                  # 主技能文件（流程逻辑、优先级判断、输出格式）
├── references/
│   ├── data-sources.md       # 7 个数据源的详细 CLI 命令和字段提取规则
│   └── action-dispatch.md    # 6 种行动的详细 CLI 命令和安全规则
├── evals/
│   ├── evals.json            # 测试用例定义
│   ├── run_tests.sh          # 基础测试（17 项）
│   └── run_full_tests.sh     # 综合测试（44 项）
├── LICENSE                   # MIT License
├── README.md                 # 中文文档
└── README_EN.md              # English documentation
```

## 测试

```bash
cd lark-todo

# 基础测试（17 项，快速验证）
bash evals/run_tests.sh

# 综合测试（44 项，覆盖启动检查、两路文档搜索、增量扫描、响应结构、边界情况）
bash evals/run_full_tests.sh
```

需要先完成 `lark-cli` 配置和用户授权。测试覆盖：
- 启动检查（config、auth、用户信息）
- 7 个数据源采集命令的可用性和响应结构
- 两路文档搜索策略（creator_ids + only_comment）
- 15 个行动命令的参数正确性
- 增量扫描的不同时间范围
- 边界情况（无效参数、权限检查）

## 自包含设计

lark-todo 是完全自包含的技能包：
- 认证、权限处理逻辑内嵌在 SKILL.md 中
- 所有 CLI 命令和参数在 references/ 中完整记录
- 不依赖 lark-shared 或其他 lark-* 技能包即可独立运行
- 唯一的外部依赖是 `lark-cli` 命令行工具

## 依赖

本项目依赖 [lark-cli](https://github.com/larksuite/cli)（MIT License）作为底层命令行工具来调用飞书 OpenAPI。lark-todo 本身不包含 lark-cli 的任何代码，仅通过命令行调用其功能。

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

[MIT](LICENSE)
