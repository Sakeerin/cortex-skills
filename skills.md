# AI Skills — Quick Reference

> Universal skill collection สำหรับ Claude Code, Gemini CLI, ChatGPT, Ollama และ AI agent อื่นๆ

---

## การใช้งาน

```bash
<skill-name> [command] [options]
```

Skills ทั้งหมดรับ `--help` เพื่อดูคำสั่งแบบเต็ม

---

## Skills ที่มีทั้งหมด

### ported จาก thaitype/skills

| Skill | วัตถุประสงค์ | สถานะ |
|---|---|---|
| [time](#time) | ดึงเวลาปัจจุบัน | ✅ stable |
| [todo](#todo) | Task management พร้อม priority/tags | ✅ enhanced |
| [sync-git](#sync-git) | Git sync helper | ✅ stable |
| [skill-creator](#skill-creator) | สร้าง skill ใหม่จาก template | ✅ enhanced |

### AI Provider Layer

| Skill | วัตถุประสงค์ | สถานะ |
|---|---|---|
| [ai-provider](#ai-provider) | ตรวจจับและ configure AI provider | 🔧 phase 2 |
| [ai-cost](#ai-cost) | Track cost ข้าม provider | 🔧 phase 2 |
| [ai-context](#ai-context) | Context window status | 🔧 phase 2 |
| [ai-model-list](#ai-model-list) | List available models | 🔧 phase 2 |
| [ai-session-log](#ai-session-log) | Unified session log | 🔧 phase 4 |
| [token-budget](#token-budget) | ตั้ง token/cost budget | 🔧 phase 2 |
| [env-check](#env-check) | ตรวจสอบ API keys & connectivity | 🔧 phase 1 |

### Productivity Skills

| Skill | วัตถุประสงค์ | สถานะ |
|---|---|---|
| [notes](#notes) | Quick note-taking | 🔧 phase 3 |
| [prompt-lib](#prompt-lib) | Personal prompt library | 🔧 phase 3 |
| [memory](#memory) | Persistent memory ข้าม session | 🔧 phase 3 |
| [project-brief](#project-brief) | Load project context เข้า AI agent | 🔧 phase 3 |
| [git-summary](#git-summary) | Human-readable git diff/log summary | 🔧 phase 3 |
| [daily-report](#daily-report) | Auto-generate daily standup report | 🔧 phase 4 |

---

## รายละเอียด Skills

### `time`

ดึงเวลาและวันที่ปัจจุบัน

```bash
time                    # แสดงเวลาปัจจุบัน
time --timezone UTC     # ระบุ timezone
time --format iso       # ISO 8601 format
```

---

### `todo`

Task management พร้อม priority, tags และ project grouping

```bash
todo add "task title"                          # เพิ่ม task
todo add "task" --priority high --tag backend  # พร้อม priority และ tag
todo add "task" --due 2026-04-20               # พร้อม due date
todo list                                      # แสดงทั้งหมด
todo list --project lms                        # กรองตาม project
todo list --tag backend                        # กรองตาม tag
todo list --priority high                      # กรองตาม priority
todo done <id>                                 # mark เสร็จ
todo delete <id>                               # ลบ task
todo export --format markdown                  # export เป็น Markdown checklist
```

**Priority levels:** `low` | `medium` | `high` | `urgent`

---

### `sync-git`

Git sync helper — fetch, pull, push พร้อมตรวจสอบ conflicts

```bash
sync-git                # sync กับ remote ปัจจุบัน
sync-git --push         # sync และ push
sync-git --status       # แสดงสถานะ
```

---

### `skill-creator`

สร้าง skill ใหม่จาก boilerplate template พร้อมโครงสร้าง multi-provider

```bash
skill-creator new <skill-name>     # สร้าง skill ใหม่
skill-creator list                 # แสดง skill ที่มีอยู่
skill-creator validate <skill>     # ตรวจสอบโครงสร้าง skill
```

---

### `ai-provider`

ตรวจจับ AI provider ที่กำลังใช้งานอยู่ และจัดการ config

```bash
ai-provider status          # แสดง provider/model ที่ active
ai-provider set claude      # ตั้ง provider
ai-provider list            # แสดง provider ที่รองรับทั้งหมด
ai-provider test            # ping API เพื่อตรวจสอบ connectivity
ai-provider setup           # interactive setup wizard
```

**Providers ที่รองรับ:** `claude` | `gemini` | `openai` | `ollama` | `mistral` | `lmstudio`

---

### `ai-cost`

Track และ visualize token cost ข้าม provider ทุกตัว

```bash
ai-cost today                 # cost วันนี้ แยก provider
ai-cost week                  # cost สัปดาห์นี้
ai-cost month                 # cost เดือนนี้
ai-cost breakdown             # breakdown ต่อ model/provider
ai-cost export --format csv   # export เป็น CSV
ai-cost budget set 10         # ตั้ง daily budget $10
```

**Data:** `~/.ai-skills-data/cost-log.jsonl`

---

### `ai-context`

แสดง context window status ของ model ปัจจุบัน

```bash
ai-context                    # context ของ session ปัจจุบัน
ai-context --model gpt-4o     # limit ของ model ที่ระบุ
ai-context --all              # limit ของทุก model ที่รองรับ
```

**Context limits:**
| Model | Context Window |
|---|---|
| claude-opus-4-6 / sonnet-4-6 | 200,000 tokens |
| gpt-4o | 128,000 tokens |
| gemini-2.5-pro / flash | 1,000,000 tokens |
| llama3.3 (Ollama) | 128,000 tokens |
| mistral-large | 128,000 tokens |

---

### `ai-model-list`

แสดง model ที่ใช้งานได้ของแต่ละ provider พร้อม spec

```bash
ai-model-list                       # list จาก provider ปัจจุบัน
ai-model-list --provider openai     # list จาก OpenAI
ai-model-list --provider ollama     # list local Ollama models
ai-model-list --compare             # เปรียบเทียบ spec ทุก provider
ai-model-list --pull llama3.3       # pull Ollama model
```

---

### `ai-session-log`

Unified session log ที่ทำงานข้าม provider

```bash
ai-session-log --latest             # log session ล่าสุด
ai-session-log --provider claude    # log เฉพาะ Claude sessions
ai-session-log --search "keyword"   # ค้นหาจาก content
ai-session-log --export markdown    # export เป็น Markdown
ai-session-log --stats              # สถิติ (duration, tokens, turns)
```

---

### `token-budget`

ตั้ง token/cost budget และแจ้งเตือนเมื่อใกล้หมด

```bash
token-budget set daily 5.00         # ตั้ง daily budget $5
token-budget set session 1.00       # ตั้ง per-session budget $1
token-budget set monthly 50.00      # ตั้ง monthly budget $50
token-budget status                 # แสดง budget ปัจจุบัน
token-budget reset session          # reset session counter
token-budget alert --threshold 80   # แจ้งเตือนที่ 80%
```

---

### `env-check`

ตรวจสอบ AI API keys และ connectivity ก่อนเริ่มงาน

```bash
env-check                       # ตรวจสอบ provider ปัจจุบัน
env-check --all                 # ตรวจสอบทุก provider
env-check --provider ollama     # ตรวจสอบ Ollama local server
env-check --fix                 # แนะนำวิธีแก้ปัญหา
```

---

### `notes`

Quick note-taking ระหว่าง coding session

```bash
notes add "ข้อความ"                  # เพิ่ม note
notes add "ข้อความ" --tag idea       # พร้อม tag
notes list                          # แสดง notes วันนี้
notes list --all                    # แสดงทั้งหมด
notes list --tag idea               # กรองตาม tag
notes search "keyword"              # ค้นหา
notes done <id>                     # mark ว่าทำแล้ว
notes delete <id>                   # ลบ
notes export --format markdown      # export เป็น Markdown
```

> ต่างจาก `todo`: notes เป็น freeform และ ephemeral — ไม่มี priority หรือ due date

---

### `prompt-lib`

Personal prompt library — จัดเก็บและเรียกใช้ prompt template

```bash
prompt-lib add "name" "prompt text"             # เพิ่ม prompt
prompt-lib list                                 # แสดงทั้งหมด
prompt-lib search "keyword"                     # ค้นหา
prompt-lib use "name"                           # print prompt (copy ได้)
prompt-lib use "name" --with "var=value"        # แทน template variable
prompt-lib edit "name"                          # เปิด editor
prompt-lib delete "name"                        # ลบ
prompt-lib export                               # export เป็น JSON
prompt-lib import prompts.json                  # import
```

**Template syntax:** ใช้ `{{variable_name}}` สำหรับ variable ใน template

**Data:** `~/.ai-skills-data/prompts.json`

---

### `memory`

Persistent memory ข้าม session และข้าม provider

```bash
memory add "key" "value"            # บันทึก memory
memory add "key" "value" --tag pref # พร้อม tag
memory list                         # แสดงทั้งหมด
memory list --tag project           # กรองตาม tag
memory get "key"                    # ดึง memory ชิ้นเดียว
memory search "keyword"             # ค้นหา
memory delete "key"                 # ลบ
memory context                      # สร้าง context block สำหรับ inject ลง prompt
memory export                       # export ทั้งหมด
memory clear                        # ล้างทั้งหมด
```

**`memory context`** — ใช้ inject เข้า system prompt เพื่อให้ AI จำ context ข้าม session

**Data:** `~/.ai-skills-data/memory.jsonl`

---

### `project-brief`

Load project context เข้า AI agent ได้ทันที

```bash
project-brief init          # สร้าง BRIEF.md template ใน project root
project-brief show          # แสดง brief ปัจจุบัน
project-brief inject        # print brief สำหรับ inject ลง system prompt
project-brief edit          # เปิด editor
project-brief validate      # ตรวจสอบความครบถ้วน
```

**ไฟล์:** `BRIEF.md` ใน project root — ครอบคลุม stack, domain glossary, conventions, key files

---

### `git-summary`

สร้าง human-readable summary ของ git diff/log

```bash
git-summary                     # summary ของ unstaged changes
git-summary --staged            # summary ของ staged changes
git-summary --last 5            # summary 5 commits ล่าสุด
git-summary --since yesterday   # summary ตั้งแต่เมื่อวาน
git-summary --format prompt     # format สำหรับให้ AI สร้าง commit message
git-summary --branch main       # diff กับ branch อื่น
```

---

### `daily-report`

Auto-generate daily standup report จากข้อมูลจริง

```bash
daily-report                    # report วันนี้
daily-report --yesterday        # report เมื่อวาน
daily-report --format slack     # format สำหรับ Slack
daily-report --format markdown  # format Markdown
daily-report --send-email       # ส่งผ่าน SMTP
```

**ดึงข้อมูลจาก:** `todo` (tasks เสร็จ/ค้าง) + `git log` (commits วันนี้) + `ai-cost` (token usage) + `notes` (notes วันนี้)

---

## Environment Variables

```bash
# ~/.ai-skills.env  หรือ  <project>/.ai-skills.env

AI_PROVIDER=claude            # claude | gemini | openai | ollama | mistral
AI_MODEL=claude-sonnet-4-6   # ชื่อ model ที่ใช้งาน
AI_API_KEY=...                # API key
AI_BASE_URL=...               # สำหรับ Ollama / self-hosted
AI_SKILLS_DATA_DIR=~/.ai-skills-data  # ที่เก็บ data ของ skill
```

---

## Data Directory

Skills ทั้งหมดเก็บข้อมูลที่ `~/.ai-skills-data/` (หรือตาม `AI_SKILLS_DATA_DIR`):

```
~/.ai-skills-data/
├── todos.jsonl
├── notes.jsonl
├── memory.jsonl
├── prompts.json
├── cost-log.jsonl
└── budget.json
```

---

## Compatibility

| Skill | Claude | Gemini | OpenAI | Ollama | Generic |
|---|:---:|:---:|:---:|:---:|:---:|
| time, todo, sync-git | ✅ | ✅ | ✅ | ✅ | ✅ |
| ai-provider | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| ai-cost | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| ai-context | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| ai-model-list | ✅ | ✅ | ✅ | ✅ | ❌ |
| ai-session-log | ✅ | ✅ | ⚠️ | ❌ | ❌ |
| prompt-lib, memory, notes | ✅ | ✅ | ✅ | ✅ | ✅ |
| daily-report, project-brief, git-summary | ✅ | ✅ | ✅ | ✅ | ✅ |
| env-check, token-budget | ✅ | ✅ | ✅ | ✅ | ⚠️ |

✅ Full support | ⚠️ Partial / manual config | ❌ Not applicable
