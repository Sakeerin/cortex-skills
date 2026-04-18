# Windows Setup Guide

cortex-skills รองรับ Windows ผ่าน 3 วิธี:

| วิธี | Python scripts | Shell wrappers | แนะนำสำหรับ |
|---|:---:|:---:|---|
| **Git Bash** | ✅ | ✅ | ผู้ใช้ทั่วไป |
| **WSL 2** | ✅ | ✅ | Developer ที่ใช้ Linux workflow |
| **PowerShell / CMD** | ✅ | ❌ | ใช้ Python โดยตรงเท่านั้น |

---

## Option A — Git Bash (แนะนำ)

Git Bash มาพร้อม Git for Windows และรัน shell wrappers ได้เต็มรูปแบบ

### 1. ติดตั้ง Git for Windows

ดาวน์โหลดจาก [git-scm.com](https://git-scm.com/download/win)
ระหว่างติดตั้ง เลือก **"Git Bash Here"** และ **"Use Git from command line and also from 3rd-party software"**

### 2. ติดตั้ง Python

ดาวน์โหลด Python 3.11+ จาก [python.org](https://www.python.org/downloads/)

> ✅ ติ๊ก **"Add Python to PATH"** ระหว่างติดตั้ง

ตรวจสอบ:
```bash
python3 --version   # Git Bash
python --version    # CMD / PowerShell
```

### 3. Clone repo

```bash
# ใน Git Bash
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
```

### 4. ตั้งค่า provider

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

### 5. เพิ่ม PATH (Git Bash)

เพิ่มใน `~/.bashrc` หรือ `~/.bash_profile`:

```bash
for d in "$HOME/.ai-skills"/*/; do
  export PATH="$d:$PATH"
done
```

Reload:
```bash
source ~/.bashrc
```

ตรวจสอบ:
```bash
which todo    # ควรแสดง ~/.ai-skills/todo/todo
todo --help
```

---

## Option B — WSL 2

WSL 2 รัน Linux จริงๆ บน Windows — แนะนำสำหรับ developer

### 1. ติดตั้ง WSL 2

```powershell
# PowerShell (Admin)
wsl --install
```

Restart เครื่อง จากนั้นเปิด Ubuntu จาก Start Menu

### 2. ติดตั้ง Python ใน WSL

```bash
sudo apt update && sudo apt install python3.12 python3.12-venv git
```

### 3. Clone และตั้งค่า (ใน WSL terminal)

```bash
git clone https://github.com/your-username/cortex-skills ~/.ai-skills
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
EOF
```

### 4. PATH setup

```bash
echo 'for d in "$HOME/.ai-skills"/*/; do export PATH="$d:$PATH"; done' >> ~/.bashrc
source ~/.bashrc
```

> **Note:** WSL filesystem (`~/`) และ Windows filesystem (`/mnt/c/Users/...`) แยกกัน
> Data ของ skills จะอยู่ใน WSL home: `~/.ai-skills-data`

---

## Option C — PowerShell / CMD (Python only)

ใช้ Python scripts โดยตรง โดยไม่ต้องใช้ shell wrappers

### 1. ติดตั้ง Python

ดาวน์โหลดจาก [python.org](https://www.python.org/downloads/) — ติ๊ก "Add to PATH"

### 2. Clone repo

```powershell
git clone https://github.com/your-username/cortex-skills $env:USERPROFILE\.ai-skills
```

### 3. ตั้งค่า

สร้างไฟล์ `%USERPROFILE%\.ai-skills.env`:

```ini
AI_PROVIDER=claude
AI_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
AI_SKILLS_DATA_DIR=%USERPROFILE%\.ai-skills-data
```

> **Note:** `~` ไม่ทำงานใน Windows env files — ใช้ `%USERPROFILE%` หรือ path เต็ม

### 4. เรียกใช้ skills

```powershell
python $env:USERPROFILE\.ai-skills\todo\scripts\tasks.py list
python $env:USERPROFILE\.ai-skills\notes\scripts\notes.py add "Remember to deploy"
python $env:USERPROFILE\.ai-skills\memory\scripts\memory.py context
```

### 5. เพิ่ม PATH (optional, PowerShell)

เพิ่มใน `$PROFILE` (`notepad $PROFILE`):

```powershell
# เพิ่ม Python scripts directory ลง PATH
$skillsDir = "$env:USERPROFILE\.ai-skills"
Get-ChildItem $skillsDir -Directory | ForEach-Object {
    $env:PATH = "$($_.FullName);$env:PATH"
}
```

> Shell wrappers (เช่น `todo`, `notes`) จะใช้งานไม่ได้ใน PowerShell/CMD
> เปิด Git Bash หรือ WSL เพื่อใช้งาน wrappers

---

## Windows-Specific Notes

### UTF-8 / Emoji

scripts ทั้งหมดมี `sys.stdout.reconfigure(encoding="utf-8")` แล้ว แต่ถ้า terminal แสดง emoji เป็น `?`:

```powershell
# ตั้ง code page เป็น UTF-8
chcp 65001

# หรือตั้งใน Windows Terminal Settings
# "profiles.defaults.colorScheme" + font ที่รองรับ emoji
```

### Windows Terminal (แนะนำ)

ใช้ **Windows Terminal** แทน Command Prompt เก่า:
- รองรับ UTF-8 และ emoji เต็มรูปแบบ
- สามารถเปิด Git Bash, WSL, PowerShell ใน tab เดียวกัน
- ดาวน์โหลดจาก Microsoft Store: "Windows Terminal"

### Path Separator

Python ใน Windows ใช้ `\` แต่ `pathlib.Path` จัดการให้อัตโนมัติ
ห้ามใส่ path แบบ hardcode ด้วย `/` — ใช้ `Path(...)` เสมอ (ทำอยู่แล้วในทุก script)

### Ollama บน Windows

Ollama มี native Windows installer ที่ [ollama.com/download](https://ollama.com/download)
หลังติดตั้ง Ollama server จะรันเป็น Windows service อัตโนมัติ

```powershell
ollama pull llama3.2
python $env:USERPROFILE\.ai-skills\env-check\scripts\env_check.py --provider ollama
```

---

## Verification

```bash
# Git Bash หรือ WSL
python3 ~/.ai-skills/env-check/scripts/env_check.py --fix
```

```powershell
# PowerShell
python $env:USERPROFILE\.ai-skills\env-check\scripts\env_check.py --fix
```

ผลลัพธ์ที่คาดหวัง:
```
✅  AI_PROVIDER                    = claude
✅  ANTHROPIC_API_KEY              = sk-ant-api0...
✅  Claude API                     reachable
✅  AI_SKILLS_DATA_DIR             = C:\Users\..\.ai-skills-data
```
