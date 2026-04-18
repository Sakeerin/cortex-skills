# Ollama Setup Guide

ใช้ AI model แบบ offline บนเครื่องตัวเอง — ไม่มีค่า API, ไม่ส่ง data ออกนอก

---

## ทำไมต้องใช้ Ollama?

| ข้อดี | รายละเอียด |
|---|---|
| ฟรี 100% | ไม่มีค่า API ไม่ว่าจะใช้มากแค่ไหน |
| Privacy | ข้อมูลไม่ออกจากเครื่อง |
| Offline | ทำงานได้โดยไม่มีอินเทอร์เน็ต |
| Context | บาง model รองรับ 128K+ tokens |
| ยืดหยุ่น | เปลี่ยน model ได้ตามงาน |

---

## 1. ติดตั้ง Ollama

### macOS

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

หรือ Homebrew:
```bash
brew install ollama
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Auto-starts เป็น systemd service:
```bash
sudo systemctl enable --now ollama
```

### Windows

ดาวน์โหลด installer จาก [ollama.com/download](https://ollama.com/download)

ติดตั้งแล้ว Ollama จะรันเป็น Windows service อัตโนมัติ

### Docker

```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

GPU (NVIDIA):
```bash
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
```

---

## 2. เริ่ม Ollama server

```bash
ollama serve   # รันใน background อัตโนมัติหลังติดตั้ง
```

ตรวจสอบ:
```bash
curl http://localhost:11434/api/tags   # ควรตอบกลับ JSON
```

---

## 3. ดาวน์โหลด Model

### General Purpose

```bash
ollama pull llama3.3          # Meta Llama 3.3 70B — best quality
ollama pull llama3.2          # Llama 3.2 3B — เร็ว, ใช้ RAM น้อย
ollama pull llama3.2:1b       # Llama 3.2 1B — เร็วมาก, เครื่องอ่อน
ollama pull mistral           # Mistral 7B — balanced
ollama pull gemma3            # Google Gemma 3 — compact, good quality
```

### Code-Focused

```bash
ollama pull qwen2.5-coder     # Alibaba Qwen 2.5 Coder 7B — แนะนำสำหรับ code
ollama pull codellama         # Meta CodeLlama 7B
ollama pull deepseek-coder-v2 # DeepSeek Coder V2 — ดี
```

### Reasoning

```bash
ollama pull deepseek-r1       # DeepSeek R1 — chain-of-thought reasoning
ollama pull qwq               # QwQ 32B — reasoning
```

### Thai Language (รองรับภาษาไทย)

```bash
ollama pull typhoon2         # SCBX Typhoon2 — Thai-English bilingual
ollama pull llama3.3         # รองรับภาษาไทยได้ดีพอสมควร
ollama pull qwen2.5          # Qwen 2.5 — รองรับ multilingual รวมไทย
```

---

## 4. ตัวเลือก Model ตาม RAM

| RAM เครื่อง | แนะนำ | หมายเหตุ |
|---|---|---|
| 4 GB | `llama3.2:1b`, `tinyllama` | จำกัดมาก |
| 8 GB | `llama3.2`, `gemma2:2b`, `mistral` | พอใช้ได้ |
| 16 GB | `llama3.3`, `qwen2.5-coder:7b`, `deepseek-r1:7b` | ดี |
| 32 GB | `llama3.3:70b`, `qwq:32b`, `deepseek-r1:32b` | ยอดเยี่ยม |
| 64 GB+ | `llama3.3:70b` (full), `qwen2.5:72b` | สูงสุด |

---

## 5. ตั้งค่า cortex-skills

```bash
cat > ~/.ai-skills.env << 'EOF'
AI_PROVIDER=ollama
AI_MODEL=llama3.3
AI_BASE_URL=http://localhost:11434
AI_SKILLS_DATA_DIR=~/.ai-skills-data
EOF
```

---

## 6. ตรวจสอบ

```bash
python3 ~/.ai-skills/env-check/scripts/env_check.py --provider ollama
```

ผลลัพธ์ที่คาดหวัง:
```
✅  AI_PROVIDER                    = ollama
✅  Ollama server                  reachable (localhost:11434)
✅  AI_MODEL                       = llama3.3
✅  AI_SKILLS_DATA_DIR             = /home/user/.ai-skills-data
```

---

## 7. จัดการ Models

```bash
# แสดง models ที่ดาวน์โหลดแล้ว
ollama list

# ดาวน์โหลด model
ollama pull qwen2.5-coder

# ลบ model
ollama rm llama3.2

# ข้อมูล model
ollama show llama3.3

# รัน model แบบ interactive chat
ollama run llama3.3
```

---

## 8. เปลี่ยน Model ตามงาน

แก้ `AI_MODEL` ใน `~/.ai-skills.env` หรือ override ต่อ session:

```bash
AI_MODEL=qwen2.5-coder python3 ~/.ai-skills/git-summary/scripts/git_summary.py --staged --format prompt
AI_MODEL=llama3.3 python3 ~/.ai-skills/daily-report/scripts/daily_report.py
```

---

## 9. Custom Modelfile (Advanced)

สร้าง model ที่มี system prompt ของตัวเอง:

```Dockerfile
# ~/.ai-skills/Modelfile
FROM llama3.3

SYSTEM """
You are a helpful coding assistant.
Project: {{ project name }}
Stack: Python 3.12, FastAPI
Conventions: snake_case, type hints required
"""

PARAMETER temperature 0.3
PARAMETER num_ctx 32768
```

```bash
ollama create my-assistant -f ~/.ai-skills/Modelfile
```

แล้วใช้:
```bash
# ~/.ai-skills.env
AI_MODEL=my-assistant
```

---

## 10. Remote Ollama Server

ถ้า Ollama รันบนเครื่องอื่น (เช่น home server, GPU workstation):

```bash
# ~/.ai-skills.env
AI_PROVIDER=ollama
AI_MODEL=llama3.3
AI_BASE_URL=http://192.168.1.100:11434
```

เปิด port บน server:
```bash
# ให้ Ollama bind กับทุก interface
OLLAMA_HOST=0.0.0.0 ollama serve
```

---

## GPU Acceleration

### NVIDIA (Linux/Windows)

ติดตั้ง CUDA Toolkit แล้ว Ollama detect GPU อัตโนมัติ:

```bash
# ตรวจสอบ GPU usage
nvidia-smi
ollama run llama3.3  # ควรใช้ VRAM แทน RAM
```

### Apple Silicon (M1/M2/M3)

Ollama ใช้ Metal acceleration อัตโนมัติ — ไม่ต้องตั้งค่า

```bash
# ดู metal usage
sudo powermetrics --samplers gpu_power
```

### AMD GPU (Linux)

ใช้ ROCm:
```bash
# ติดตั้ง ROCm ก่อน จากนั้น
OLLAMA_CUDA_DEVICE_FILTER=0 ollama serve
```

---

## Troubleshooting

**`connection refused` เมื่อ run env-check**

```bash
# ตรวจสอบว่า Ollama รันอยู่
curl http://localhost:11434
# ถ้าไม่รัน:
ollama serve &
```

**Model ช้ามากหรือ hang**

Model ใหญ่เกินกว่า RAM:
```bash
ollama list  # ดูขนาด
# เปลี่ยนเป็น model เล็กกว่า
ollama pull llama3.2  # 3B แทน 70B
```

**Out of memory**

```bash
# ใช้ quantized version (ใช้ RAM น้อยกว่า)
ollama pull llama3.3:70b-instruct-q4_K_M   # Q4 quantization ~40GB
ollama pull llama3.3:70b-instruct-q2_K     # Q2 quantization ~26GB
```

**Model ไม่รองรับภาษาไทยดีพอ**

```bash
ollama pull typhoon2   # ออกแบบมาสำหรับภาษาไทยโดยเฉพาะ
```
