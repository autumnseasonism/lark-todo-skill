# lark-todo

[中文](README.md)

**lark-todo** is an AI Agent skill based on [lark-cli](https://github.com/larksuite/cli), compatible with any agent that supports the SKILL.md specification — including [Claude Code](https://claude.com/claude-code), [Trae](https://www.trae.cn/), [Cline](https://cline.bot/), and more. It scans your entire Lark/Feishu platform for actionable items, prioritizes them, and lets you handle them on the spot or create tasks.

> "What do I need to deal with today?" — Say it, and let lark-todo do the rest.

## What It Does

Each time triggered, lark-todo scans 7 Lark data sources in parallel:

| Source | What It Looks For |
|--------|-------------------|
| IM Messages | Messages that @mention me and need a response |
| Meeting Notes | Action items assigned to me from today's meetings |
| Calendar | Upcoming meetings, pending RSVPs |
| Doc Comments | Unresolved comments on my docs, or comments that @mention me |
| Approvals | Approval requests waiting for my action |
| Tasks | Overdue or due-today incomplete tasks |
| Email | Unread emails that need a reply |

Then it:
- **Analyzes** — Sorts by urgency, links to upcoming calendar events, deduplicates across sources
- **Acts** — Handles things directly when possible (reply to messages, approve requests, reply to emails), or creates Lark tasks for the rest

## Prerequisites

- An AI agent that supports the SKILL.md specification (Claude Code, Trae, Cline, etc.)
- [lark-cli](https://github.com/larksuite/cli) >= 1.0.9
- A Lark/Feishu custom app (the skill guides you through setup on first use)

## Installation

Place the `lark-todo` directory where your agent can discover it:

**Claude Code**

```bash
# Option A: Project directory (auto-discovered)
git clone https://github.com/autumnseasonism/lark-todo-skill.git

# Option B: Global skills directory
git clone https://github.com/autumnseasonism/lark-todo-skill.git ~/.agents/skills/lark-todo
```

**Trae / Cline / Other Agents**

Place the `lark-todo` directory in the agent's skills scan path. Refer to your agent's documentation for the exact location.

## Usage

In your agent, just say:

- "What do I need to deal with today?"
- "Anyone looking for me?"
- "Scan my todos"
- "Anything new this afternoon?" (incremental scan)
- "One last check before I leave"

### First-Time Setup

On first use, the skill automatically guides you through three setup steps:

1. **App Configuration** — Connect your Lark custom app (`lark-cli config init`)
2. **User Authorization** — Log in with your Lark account, granting all required permissions at once
3. **Command Allowlist** (Claude Code only) — Add `lark-cli` to the permission allowlist to avoid repeated prompts

Once done, no further setup is needed.

### Sample Output

```
## Action Items for Today (2026-04-16 Wednesday) Full Scan

### Upcoming Calendar
  15:00-16:00 Design Review (pending — needs RSVP)
   └─ Related: Item #3 is about this meeting, handle before it starts

### Action Items

1. [Urgent] [Product Chat] Alice: Please review this PR (4 hours ago, no reply)
   └─ Source: Message | Suggestion: Reply directly
2. [Urgent] Finish quarterly report (overdue by 2 days)
   └─ Source: Lark Task
3. [Normal] [Purchase Approval] From: Bob, submitted 14:30
   └─ Source: Approval | Suggestion: Approve directly
4. [Low] [Design Doc] Charlie commented: Add performance test data
   └─ Source: Doc comment | Suggestion: Add benchmarks in section 3

---
Total: 4 items (Urgent 2 / Normal 1 / Low 1)
Enter a number to handle directly, or say "create tasks for all".
```

### Direct Actions

| Item Type | Direct Action |
|-----------|--------------|
| IM Message | Draft reply → you confirm → send |
| Approval | Show summary → you confirm approve/reject → execute |
| Doc Comment | Draft reply → you confirm → submit |
| Email | Draft reply → you confirm → send (saves as draft by default) |
| Calendar Invite | Show details → you confirm accept/decline → RSVP |
| Meeting Action Item | Create Lark task |

All write operations require your confirmation before execution.

## File Structure

```
lark-todo/
├── SKILL.md                  # Main skill file (workflow, priority logic, output format)
├── references/
│   ├── data-sources.md       # Detailed CLI commands for 7 data sources
│   └── action-dispatch.md    # Detailed CLI commands for 6 action types
├── evals/
│   ├── evals.json            # Test case definitions
│   ├── run_tests.sh          # Basic tests (17 checks)
│   └── run_full_tests.sh     # Comprehensive tests (44 checks)
├── LICENSE                   # MIT License
├── README.md                 # Chinese documentation
└── README_EN.md              # English documentation
```

## Testing

```bash
cd lark-todo

# Basic tests (17 checks, quick validation)
bash evals/run_tests.sh

# Comprehensive tests (44 checks, covers startup, two-route doc search, incremental scan, response structure, edge cases)
bash evals/run_full_tests.sh
```

Requires `lark-cli` to be configured and authorized. Tests cover:
- Startup checks (config, auth, user info)
- All 7 data source commands and response structure
- Two-route document search strategy (creator_ids + only_comment)
- All 15 action command parameter validations
- Incremental scan with different time ranges
- Edge cases (invalid params, permission checks)

## Self-Contained Design

lark-todo is fully self-contained:
- Authentication and permission handling logic is embedded in SKILL.md
- All CLI commands and parameters are documented in references/
- Does not depend on lark-shared or any other lark-* skill to function
- The only external dependency is the `lark-cli` command-line tool

## Dependencies

This project depends on [lark-cli](https://github.com/larksuite/cli) (MIT License) as the underlying CLI tool for calling Lark OpenAPI. lark-todo does not contain any lark-cli source code; it only invokes lark-cli through shell commands.

## Contributing

Issues and Pull Requests are welcome.

## License

[MIT](LICENSE)
