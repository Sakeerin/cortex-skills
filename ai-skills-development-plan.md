# AI Skills — Multi-Provider Development Plan

> Universal skill collection for AI Code Agents — รองรับ Claude Code, Gemini CLI, ChatGPT, Ollama และ AI agent อื่นๆ

---

## 1. Vision & Goals

### ปัญหาที่ต้องการแก้

`thaitype/skills` ออกแบบมาสำหรับ Claude Code โดยเฉพาะ ทำให้:
- Skill ที่อิง `~/.claude/projects` ใช้กับ AI อื่นไม่ได้
- ไม่มีระบบ track cost/usage แบบ cross-provider
- ไม่มี prompt management หรือ memory ข้าม session
- ไม่มี skill สำหรับ workflow อย่าง daily standup, project briefing

### เป้าหมาย

สร้าง skill collection ที่:
1. **Provider-agnostic** — ทุก skill ทำงานได้กับ Claude, Gemini, ChatGPT, Ollama, Mistral, ฯลฯ
2. **Zero lock-in** — ไม่ผูกกับ file format หรือ session directory ของ AI ตัวใดตัวหนึ่ง
3. **Composable** — skill ต่อ skill กันได้, รองรับ pipeline
4. **Self-documenting** — ทุก skill มี `--help` และ `SKILL.md` ชัดเจน

---

## 2. Architecture

### โครงสร้าง Repo

```
ai-skills/
├── README.md
├── LICENSE
├── _lib/                        # Shared Python utilities
│   ├── ai_provider.py           # Provider detection & config
│   ├── cost_tracker.py          # Token cost calculation
│   ├── logger.py                # Unified logging format
│   └── env_loader.py            # Load .env / env vars
│
├── _templates/                  # Boilerplate สำหรับ skill ใหม่
│   ├── SKILL.md.template
│   └── main.py.template
│
│── time/                        # Skill: ดึงเวลาปัจจุบัน
├── todo/                        # Skill: Task management
├── sync-git/                    # Skill: Git sync
├── skill-creator/               # Skill: สร้าง skill ใหม่
│
│── ai-provider/                 # NEW: ตรวจจับ & configure AI provider
├── ai-cost/                     # NEW: Track cost ข้าม provider
├── ai-context/                  # NEW: Context window per model
├── ai-model-list/               # NEW: List available models
├── ai-session-log/              # NEW: Unified session log
│
├── prompt-lib/                  # NEW: Personal prompt library
├── memory/                      # NEW: Persistent memory ข้าม session
├── notes/                       # NEW: Quick note-taking
├── daily-report/                # NEW: Daily standup generator
├── project-brief/               # NEW: Project context loader
├── git-summary/                 # NEW: AI-powered git diff summary
├── env-check/                   # NEW: ตรวจสอบ API keys & connectivity
└── token-budget/                # NEW: ตั้ง token budget ต่อ session
```

### Provider Config Standard

ทุก skill อ่าน config จาก environment variable มาตรฐานกลาง:

```bash
# ~/.ai-skills.env  หรือ  <project>/.ai-skills.env

AI_PROVIDER=claude          # claude | gemini | openai | ollama | mistral
AI_MODEL=claude-sonnet-4-6  # ชื่อ model ที่ใช้อยู่
AI_API_KEY=...              # API key (ถ้า provider ต้องการ)
AI_BASE_URL=...             # สำหรับ Ollama / self-hosted
AI_SKILLS_DATA_DIR=~/.ai-skills-data  # ที่เก็บ data ของ skill ต่างๆ
```

---

## 3. Skills ที่สืบทอดมาจาก thaitype/skills (Ported & Improved)

Skills กลุ่มนี้มีอยู่แล้วใน thaitype/skills แต่จะปรับให้ทำงานกับทุก provider

### 3.1 `time`
**ไม่มีการเปลี่ยนแปลง** — เป็น utility ทั่วไป ไม่ผูกกับ AI ใด

---

### 3.2 `todo` (Enhanced)
**เพิ่มจากเดิม:**
- รองรับ priority levels (`low`, `medium`, `high`, `urgent`)
- เพิ่ม tag และ project grouping
- export เป็น Markdown checklist ได้
- integration กับ `daily-report` skill

**Schema (JSONL):**
```json
{
  "id": "uuid",
  "action": "add|update|delete|check",
  "title": "...",
  "priority": "medium",
  "tags": ["backend", "sprint-3"],
  "project": "lms-project",
  "due_date": "2026-04-15",
  "done": false,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

---

### 3.3 `sync-git` (No change)
Provider-agnostic อยู่แล้ว ไม่ต้องแก้

---

### 3.4 `skill-creator` (Enhanced)
เพิ่ม template สำหรับ multi-provider skill structure พร้อม boilerplate `env_loader.py`

---

## 4. Skills ใหม่ทั้งหมด

### 4.1 `ai-provider`
**วัตถุประสงค์:** ตรวจจับว่ากำลังรันอยู่ใน AI agent ตัวไหน และแสดง config ปัจจุบัน

**คำสั่ง:**
```bash
ai-provider status           # แสดง provider/model ที่ active
ai-provider set claude       # ตั้ง provider
ai-provider list             # แสดง provider ที่รองรับทั้งหมด
ai-provider test             # ping API เพื่อตรวจสอบ connectivity
```

**Provider detection priority:**
1. `AI_PROVIDER` env var
2. ตรวจจาก process environment (`CLAUDE_*`, `GOOGLE_*`, `OPENAI_*`)
3. ตรวจจาก tool call context (Claude ใช้ `/.claude/`, Gemini ใช้ `/.gemini/`)
4. Default: `unknown`

**Supported Providers:**

| Provider | CLI Tool | Session Dir | Cost Data Source |
|---|---|---|---|
| Claude Code | `claude` | `~/.claude/projects` | JSONL session files |
| Gemini CLI | `gemini` | `~/.gemini/` | Usage API |
| OpenAI / ChatGPT | `openai` | N/A | API response headers |
| Ollama | `ollama` | Local model server | N/A (free) |
| Mistral | `mistral` | N/A | API response |
| LM Studio | `lmstudio` | Local server | N/A (free) |

---

### 4.2 `ai-cost`
**วัตถุประสงค์:** Track และ visualize token cost ข้าม provider ทุกตัว

**คำสั่ง:**
```bash
ai-cost today                # cost วันนี้ แยก provider
ai-cost week                 # cost สัปดาห์นี้
ai-cost month                # cost เดือนนี้
ai-cost breakdown            # แยก breakdown ต่อ model/provider
ai-cost export --format csv  # export เป็น CSV
ai-cost budget set 10        # ตั้ง daily budget $10
```

**Output ตัวอย่าง:**
```
AI Cost Report — April 2026
─────────────────────────────────────────
Provider     Model                  Tokens      Cost (USD)
─────────────────────────────────────────
Claude       claude-sonnet-4-6      1,234,500   $3.70
OpenAI       gpt-4o                 450,200     $2.25
Gemini       gemini-2.5-pro         890,000     $1.34
Ollama       llama3.3               ∞           $0.00
─────────────────────────────────────────
Total                                            $7.29 / $50.00 budget
```

**Data storage:** `~/.ai-skills-data/cost-log.jsonl`

**Cost table** (อัพเดทจาก config file `cost-rates.json` ที่ pull จาก repo):
```json
{
  "claude-sonnet-4-6": { "input": 3.0, "output": 15.0 },
  "gpt-4o": { "input": 2.5, "output": 10.0 },
  "gemini-2.5-pro": { "input": 1.25, "output": 10.0 }
}
```

---

### 4.3 `ai-context`
**วัตถุประสงค์:** แสดง context window status สำหรับ model ปัจจุบัน — ใช้งานได้ทุก provider

**คำสั่ง:**
```bash
ai-context                   # แสดง context ของ session ล่าสุด
ai-context --model gpt-4o    # แสดง limit ของ model ที่ระบุ
ai-context --all             # แสดง limit ของทุก model ที่รองรับ
```

**Context Limit Table** (built-in):

| Model | Context Window | Notes |
|---|---|---|
| claude-opus-4-6 | 200,000 tokens | |
| claude-sonnet-4-6 | 200,000 tokens | |
| gpt-4o | 128,000 tokens | |
| gemini-2.5-pro | 1,000,000 tokens | |
| gemini-2.5-flash | 1,000,000 tokens | |
| llama3.3 (Ollama) | 128,000 tokens | model-dependent |
| mistral-large | 128,000 tokens | |

**Output:**
```
Context Window — claude-sonnet-4-6
─────────────────────────────────
Max Tokens:     200,000
Used:            45,231  (22.6%)
Free:           154,769  (77.4%)
Autocompact:     20,000  buffer

Last message:   "ช่วยสรุป context window ให้หน่อย"
```

**หมายเหตุ:** สำหรับ Claude Code จะอ่านจาก JSONL เหมือน thaitype/skills สำหรับ provider อื่นจะอ่านจาก API response หรือ manual input

---

### 4.4 `ai-model-list`
**วัตถุประสงค์:** แสดง model ที่ใช้งานได้ของแต่ละ provider พร้อม spec

**คำสั่ง:**
```bash
ai-model-list                      # list จาก provider ปัจจุบัน
ai-model-list --provider openai    # list จาก OpenAI
ai-model-list --provider ollama    # list local Ollama models
ai-model-list --compare            # เปรียบเทียบ spec ทุก provider
ai-model-list --pull llama3.3      # pull Ollama model (ถ้า provider=ollama)
```

**สำหรับ Ollama:** ดึงจาก `http://localhost:11434/api/tags`
**สำหรับ OpenAI/Gemini:** ดึงจาก API `/models` endpoint

---

### 4.5 `ai-session-log`
**วัตถุประสงค์:** Unified session log ที่ทำงานข้าม provider

**คำสั่ง:**
```bash
ai-session-log --latest            # log session ล่าสุด
ai-session-log --provider claude   # log เฉพาะ Claude sessions
ai-session-log --search "keyword"  # ค้นหา session จาก content
ai-session-log --export markdown   # export เป็น Markdown
ai-session-log --stats             # สถิติ session (duration, tokens, turns)
```

**Adapter pattern:**
```
ai-session-log
    ├── adapters/
    │   ├── claude_adapter.py    # อ่านจาก ~/.claude/projects/*.jsonl
    │   ├── gemini_adapter.py    # อ่านจาก ~/.gemini/sessions/
    │   ├── openai_adapter.py    # อ่านจาก OpenAI API history
    │   └── generic_adapter.py  # สำหรับ provider ที่ไม่มี adapter
```

---

### 4.6 `prompt-lib` ⭐ (New Feature ที่ยังไม่มีใน thaitype/skills)
**วัตถุประสงค์:** Personal prompt library — จัดเก็บ, ค้นหา และเรียกใช้ prompt template ได้ทันที

**คำสั่ง:**
```bash
prompt-lib add "code-review" "Review this code for..."  # เพิ่ม prompt
prompt-lib list                                          # แสดงทั้งหมด
prompt-lib search "review"                              # ค้นหา
prompt-lib use "code-review"                            # print prompt ออกมา (copy ได้)
prompt-lib use "code-review" --with "var=value"         # แทน variable
prompt-lib edit "code-review"                           # เปิด editor
prompt-lib delete "code-review"                         # ลบ
prompt-lib export                                       # export เป็น JSON
prompt-lib import prompts.json                          # import
```

**Template syntax:**
```
Review the following {{language}} code and provide feedback on:
- Code quality
- Security issues
- Performance concerns

Code:
{{code}}
```

**Data:** `~/.ai-skills-data/prompts.json`

**Use case:** Agent สามารถ inject prompt template ลง context ได้โดยตรง เช่น "ใช้ prompt `thai-commit-msg` สำหรับ commit message นี้"

---

### 4.7 `memory` ⭐ (New Feature)
**วัตถุประสงค์:** Persistent memory ข้าม session และข้าม provider — แก้ปัญหา AI ไม่จำ context เดิม

**คำสั่ง:**
```bash
memory add "user_pref" "ชอบใช้ TypeScript strict mode"   # บันทึก memory
memory add "project" "ชื่อโปรเจกต์: LMS, stack: Laravel+Vue"
memory list                                               # แสดงทั้งหมด
memory list --tag "project"                               # กรอง tag
memory get "user_pref"                                    # ดึง memory ชิ้นเดียว
memory search "TypeScript"                               # ค้นหา
memory delete "user_pref"                                 # ลบ
memory context                                           # สร้าง context block สำหรับ inject ลง prompt
memory export                                            # export ทั้งหมด
memory clear                                             # ล้างทั้งหมด
```

**`memory context` output (inject ลง system prompt ได้เลย):**
```markdown
## Persistent Memory

- **user_pref**: ชอบใช้ TypeScript strict mode
- **project**: ชื่อโปรเจกต์: LMS, stack: Laravel+Vue
- **coding_style**: ไม่ชอบ callback hell, ชอบ async/await
```

**Data:** `~/.ai-skills-data/memory.jsonl`
**Schema:**
```json
{
  "id": "uuid",
  "key": "user_pref",
  "value": "ชอบใช้ TypeScript strict mode",
  "tags": ["preference"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

---

### 4.8 `notes` (New Feature)
**วัตถุประสงค์:** Quick note-taking ระหว่าง coding session — ไม่ต้องออกจาก terminal

**คำสั่ง:**
```bash
notes add "ต้องเช็ค race condition ใน reservation number"
notes add "idea: เพิ่ม webhook สำหรับ payment callback" --tag idea
notes list                      # แสดงทั้งหมดวันนี้
notes list --all                # แสดงทั้งหมด
notes list --tag idea           # กรองตาม tag
notes search "webhook"          # ค้นหา
notes done 3                    # mark note #3 ว่าทำแล้ว
notes delete 3                  # ลบ note #3
notes export --format markdown  # export เป็น MD
```

**ต่างจาก `todo`:** notes เป็น freeform และ ephemeral กว่า ไม่มี priority/due date — เหมาะสำหรับ "สิ่งที่คิดขึ้นมาตอนนั้น"

---

### 4.9 `daily-report` ⭐ (New Feature)
**วัตถุประสงค์:** Auto-generate daily standup report จากข้อมูลจริงที่มีอยู่

**คำสั่ง:**
```bash
daily-report                    # generate report วันนี้
daily-report --yesterday        # report เมื่อวาน
daily-report --format slack     # format สำหรับ paste ลง Slack
daily-report --format markdown  # format เป็น Markdown
daily-report --send-email       # ส่งผ่าน SMTP (ถ้า configure ไว้)
```

**Data sources ที่ combine:**
- `todo` — tasks ที่ทำเสร็จวันนี้ และ tasks ที่ค้างอยู่
- `git log` — commits วันนี้ (ทุก repo ใน config)
- `ai-cost` — token/cost ที่ใช้วันนี้
- `notes` — notes ที่สร้างวันนี้

**Output ตัวอย่าง (Slack format):**
```
📅 *Daily Report — 12 April 2026*

✅ *Done:*
• ✅ Fix race condition ใน reservation number (laravel-lms)
• ✅ Implement Cloudflare Stream upload endpoint

🔄 *In Progress:*
• 🔄 Omise payment webhook integration

📝 *Commits:*
• `feat: add stream upload endpoint` (lms-backend, 14:32)
• `fix: lockForUpdate on reservation` (lms-backend, 11:05)

💰 *AI Usage:* 1.2M tokens — $3.60 (claude-sonnet-4-6)

🚧 *Blockers:* ไม่มี
```

---

### 4.10 `project-brief` ⭐ (New Feature)
**วัตถุประสงค์:** Load project context เข้า AI agent ได้ทันที — แก้ปัญหา AI ไม่รู้ว่าโปรเจกต์คืออะไร

**คำสั่ง:**
```bash
project-brief init              # สร้าง BRIEF.md template ใน project root
project-brief show              # แสดง brief ปัจจุบัน
project-brief inject            # print brief format ที่ inject ลง system prompt ได้
project-brief edit              # เปิด editor
project-brief validate          # ตรวจว่า brief ครบถ้วน
```

**`BRIEF.md` format:**
```markdown
# Project Brief: LMS for Thai Tutoring

## Stack
- Backend: Laravel 11, PHP 8.3
- Frontend: Vue 3, Inertia.js, Tailwind CSS
- Database: MySQL 8.0
- Storage: Cloudflare R2 + Stream
- Payment: Omise
- Deploy: DigitalOcean + Forge

## Domain Glossary
- นักเรียน = Student (role: student)
- ครู = Teacher (role: teacher)
- สถาบัน = Institute (tenant in multi-tenant setup)
- คาบ = Class session

## Conventions
- Thai status values ใน DB (ยืนยันแล้ว, รอดำเนินการ, ฯลฯ)
- Use service classes, not fat controllers
- All money in Thai Baht (THB), stored as integer satang

## Key Files
- Routes: routes/web.php, routes/api.php
- Models: app/Models/
- Tests: tests/Feature/
```

**ประโยชน์:** เวลาเริ่ม session ใหม่กับ AI ตัวไหนก็ตาม แค่รัน `project-brief inject` แล้ว paste ได้เลย

---

### 4.11 `git-summary` ⭐ (New Feature)
**วัตถุประสงค์:** สร้าง human-readable summary ของ git diff/log โดยไม่ต้องใช้ AI API

**คำสั่ง:**
```bash
git-summary                     # summary ของ changes ที่ยังไม่ commit
git-summary --staged            # summary ของ staged changes
git-summary --last 5            # summary 5 commits ล่าสุด
git-summary --since yesterday   # summary ตั้งแต่เมื่อวาน
git-summary --format prompt     # format ที่ paste ให้ AI สร้าง commit message ได้เลย
git-summary --branch main       # diff กับ branch อื่น
```

**Output (`--format prompt`):**
```
Please write a conventional commit message for these changes:

Files changed (4):
- app/Services/PaymentService.php (+120, -5)
- app/Http/Controllers/PaymentController.php (+45, -12)
- tests/Feature/PaymentTest.php (+89, -0)
- routes/api.php (+3, -0)

Summary of changes:
- Added PaymentService class with Omise integration
- PaymentController now delegates to service layer
- Added feature tests for payment webhook
- Registered new webhook route
```

---

### 4.12 `env-check` (New Feature)
**วัตถุประสงค์:** ตรวจสอบ AI API keys และ connectivity ก่อนเริ่มงาน

**คำสั่ง:**
```bash
env-check                       # ตรวจสอบ provider ปัจจุบัน
env-check --all                 # ตรวจสอบทุก provider
env-check --provider ollama     # ตรวจสอบ Ollama local server
env-check --fix                 # แนะนำวิธีแก้ปัญหา
```

**ตัวอย่าง output:**
```
AI Environment Check
─────────────────────────────────
✅  AI_PROVIDER    = claude
✅  AI_MODEL       = claude-sonnet-4-6
✅  ANTHROPIC_API_KEY  set (sk-ant-...xxxx)
✅  API Ping       200 OK (324ms)
⚠️  AI_SKILLS_DATA_DIR not set (using ~/.ai-skills-data)
❌  OPENAI_API_KEY not set
✅  Ollama         running at localhost:11434
     └─ Models: llama3.3, codellama, phi4
```

---

### 4.13 `token-budget` (New Feature)
**วัตถุประสงค์:** ตั้ง token/cost budget และแจ้งเตือนเมื่อใกล้หมด

**คำสั่ง:**
```bash
token-budget set daily 5.00             # ตั้ง daily budget $5
token-budget set session 1.00           # ตั้ง per-session budget $1
token-budget set monthly 50.00          # ตั้ง monthly budget $50
token-budget status                     # แสดง budget ปัจจุบัน
token-budget reset session              # reset session counter
token-budget alert --threshold 80       # แจ้งเตือนที่ 80% ของ budget
```

**Integration กับ `ai-cost`:** ดึง data จาก cost-log.jsonl แล้วเปรียบเทียบกับ budget ที่ตั้งไว้

---

## 5. Shared Library (`_lib/`)

### `ai_provider.py`
```python
class AIProvider:
    SUPPORTED = ["claude", "gemini", "openai", "ollama", "mistral", "lmstudio"]
    
    def detect() -> str
    def get_model() -> str
    def get_context_limit(model: str) -> int
    def get_session_dir() -> Path | None
    def is_local() -> bool  # True สำหรับ Ollama, LM Studio
```

### `cost_tracker.py`
```python
class CostTracker:
    def log_usage(provider, model, input_tokens, output_tokens)
    def get_daily_cost(date) -> float
    def get_weekly_cost() -> float
    def get_monthly_cost() -> float
    def get_breakdown() -> dict
    def check_budget(budget_type) -> tuple[float, float, bool]  # used, limit, exceeded
```

### `env_loader.py`
```python
def load_env():
    """Load từ ~/.ai-skills.env, .ai-skills.env, .env ตามลำดับ"""
    
def get(key: str, default: str = None) -> str
def require(key: str) -> str  # raise ถ้าไม่มี
```

---

## 6. Installation & Setup

### Quick Install (Single Skill)
```bash
# Install skill เดียว
npx degit your-username/ai-skills/<skill-name> ~/.ai-skills/<skill-name>

# หรือ install ผ่าน install script
curl -sSL https://raw.githubusercontent.com/your-username/ai-skills/main/install.sh | bash
```

### Install Script (`install.sh`)
```bash
#!/bin/bash
# interactive installer — เลือก skill ที่ต้องการ และ configure provider
```

### Config Wizard
```bash
ai-provider setup   # interactive setup: เลือก provider, ใส่ API key, test connection
```

### ติดตั้งกับ AI Agent แต่ละตัว

**Claude Code:**
```bash
# CLAUDE.md หรือ .claude/CLAUDE.md
Skills are in ~/.ai-skills/. Run skill-name to use.
```

**Gemini CLI:**
```bash
# GEMINI.md
Skills are in ~/.ai-skills/. Run skill-name to use.
```

**Custom AI Agent / LLM:**
ใช้ `project-brief inject` เพื่อ inject context เข้า system prompt แทน

---

## 7. Development Phases

### Phase 1 — Foundation (สัปดาห์ที่ 1–2)
**เป้าหมาย:** โครงสร้าง repo, shared lib, และ skill พื้นฐาน

- [x] สร้างโครงสร้าง repo และ `_lib/` directory
- [x] implement `env_loader.py` และ `ai_provider.py`
- [x] port `time` จาก thaitype/skills (ไม่มีการเปลี่ยนแปลง)
- [x] port และ enhance `todo` (เพิ่ม priority, tags, project)
- [x] port `sync-git` (ไม่มีการเปลี่ยนแปลง)
- [x] implement `env-check`
- [x] เขียน README.md หลัก

**Deliverable:** repo พร้อมใช้งานเบื้องต้น

---

### Phase 2 — AI Provider Layer (สัปดาห์ที่ 3–4)
**เป้าหมาย:** Multi-provider support และ context awareness

- [x] implement `ai-provider` (detect, set, list, test)
- [x] implement `ai-context` พร้อม context limit table
- [x] implement `ai-model-list` (Claude, OpenAI, Gemini, Ollama)
- [x] implement `cost_tracker.py` shared lib
- [x] implement `ai-cost` (daily, weekly, monthly, breakdown)
- [x] implement `token-budget`
- [ ] ทดสอบกับ Claude Code, Gemini CLI, Ollama

**Deliverable:** AI providers ทุกตัวทำงานได้

---

### Phase 3 — Productivity Skills (สัปดาห์ที่ 5–6)
**เป้าหมาย:** Skills ที่เพิ่ม developer workflow

- [x] implement `notes`
- [x] implement `prompt-lib` (add, list, search, use, template variables)
- [x] implement `memory` (add, list, get, context, export)
- [x] implement `git-summary` (diff, log, format prompt)
- [x] implement `project-brief` (init, show, inject, validate)

**Deliverable:** Productivity skills ครบชุด

---

### Phase 4 — Reporting & Integration (สัปดาห์ที่ 7–8)
**เป้าหมาย:** Cross-skill integration และ reporting

- [ ] implement `daily-report` (combine todo + git + cost + notes)
- [ ] implement `ai-session-log` พร้อม adapter สำหรับ Claude และ Gemini
- [ ] implement `skill-creator` (enhanced, พร้อม multi-provider template)
- [ ] เขียน install script (`install.sh`) แบบ interactive
- [ ] pipeline test: ทุก skill ทำงานร่วมกันได้

**Deliverable:** ระบบสมบูรณ์พร้อม publish

---

### Phase 5 — Polish & Docs (สัปดาห์ที่ 9–10)
**เป้าหมาย:** Documentation, testing, และ community readiness

- [ ] เขียน `SKILL.md` ครบทุก skill
- [ ] เพิ่ม `--help` ในทุก skill
- [ ] เขียน integration tests (`tests/`)
- [ ] สร้าง GitHub Actions CI pipeline
- [ ] เขียน contribution guide
- [ ] สร้าง demo video / GIF สำหรับ README
- [ ] publish และ announce

**Deliverable:** Public release-ready

---

## 8. Tech Stack

| Component | Technology | เหตุผล |
|---|---|---|
| Language | Python 3.11+ | ทุก OS รองรับ, ง่ายสำหรับ contributor |
| Data format | JSONL | append-only, human-readable, ไม่ต้องใช้ DB |
| Config | `.env` file | universal, รองรับทุก tool |
| Testing | pytest | lightweight, ง่ายต่อการ contribute |
| CI | GitHub Actions | free tier เพียงพอ |
| Distribution | `npx degit` | เหมือน thaitype/skills, zero install overhead |
| Packaging | ไม่ใช้ pip | เพื่อความเรียบง่าย, copy-paste install |

---

## 9. Compatibility Matrix

| Skill | Claude Code | Gemini CLI | OpenAI CLI | Ollama | Generic Agent |
|---|---|---|---|---|---|
| time | ✅ | ✅ | ✅ | ✅ | ✅ |
| todo | ✅ | ✅ | ✅ | ✅ | ✅ |
| sync-git | ✅ | ✅ | ✅ | ✅ | ✅ |
| ai-provider | ✅ | ✅ | ✅ | ✅ | ⚠️ manual |
| ai-cost | ✅ | ✅ | ✅ | ✅ (free) | ⚠️ manual |
| ai-context | ✅ | ✅ | ✅ | ✅ | ⚠️ manual |
| ai-model-list | ✅ | ✅ | ✅ | ✅ | ❌ |
| ai-session-log | ✅ | ✅ | ⚠️ limited | ❌ | ❌ |
| prompt-lib | ✅ | ✅ | ✅ | ✅ | ✅ |
| memory | ✅ | ✅ | ✅ | ✅ | ✅ |
| notes | ✅ | ✅ | ✅ | ✅ | ✅ |
| daily-report | ✅ | ✅ | ✅ | ✅ | ✅ |
| project-brief | ✅ | ✅ | ✅ | ✅ | ✅ |
| git-summary | ✅ | ✅ | ✅ | ✅ | ✅ |
| env-check | ✅ | ✅ | ✅ | ✅ | ⚠️ partial |
| token-budget | ✅ | ✅ | ✅ | ✅ (N/A) | ⚠️ manual |

✅ Full support | ⚠️ Partial / manual config | ❌ Not applicable

---

## 10. Non-Goals

สิ่งที่โปรเจกต์นี้ **ไม่ทำ** เพื่อรักษาความเรียบง่าย:
- ไม่ใช้ database (SQLite, Postgres) — ใช้ JSONL เท่านั้น
- ไม่มี GUI หรือ web interface
- ไม่มี centralized server หรือ cloud sync
- ไม่สร้าง abstraction layer สำหรับ LLM call — skill แต่ละตัวไม่ได้ call AI API (ยกเว้น `git-summary --ai`)
- ไม่รองรับ Windows อย่างเป็นทางการ (ทำงานได้ผ่าน WSL2)

---

## 11. Future Ideas (Post-v1)

- `ai-review` — Code review โดย prompt ที่ระบุ checklist ได้
- `ai-translate` — แปล comment/docstring เป็นภาษาไทย/อังกฤษ
- `standup-slack` — ส่ง daily report ไป Slack channel อัตโนมัติ
- `multi-agent` — รัน task เดียวกันกับหลาย provider พร้อมกัน แล้วเปรียบเทียบ output
- `skill-share` — publish/install skill จาก community registry
- `obsidian-sync` — sync memory และ notes ไป Obsidian vault

---

*แผนพัฒนานี้สร้างเมื่อ April 2026 — ปรับแก้ได้ตามความเหมาะสม*
