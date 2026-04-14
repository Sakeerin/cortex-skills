---
name: project-brief
description: Load project context into any AI agent — solves the "AI doesn't know my project" problem
providers: claude, gemini, openai, ollama, generic
---

# project-brief

> Maintain a `BRIEF.md` file describing your project. Use `inject` to paste it into any AI agent's system prompt so it understands your stack, conventions, and domain instantly.

## When to Use

Activate when the user:
- Starts a new AI session and wants to give context
- Says "load the project context", "inject the brief"
- Asks to create or edit the project brief
- Wants to validate the brief is complete

## Usage

```bash
python3 ~/.ai-skills/project-brief/scripts/project_brief.py <command>
# or via wrapper:
project-brief <command>
```

### Setup (once per project)

```bash
cd my-project/
project-brief init      # creates BRIEF.md template
project-brief edit      # fill in the details
project-brief validate  # check completeness
```

### Use in an AI session

```bash
project-brief inject    # prints the context block
```

Copy the output and paste it into your AI's system prompt or first message.

### View / Update

```bash
project-brief show      # read current brief
project-brief edit      # open in $EDITOR
project-brief validate  # check for missing sections
```

## BRIEF.md Format

```markdown
# Project Brief: My App

## Stack
- Backend: Laravel 11, PHP 8.3
- Frontend: Vue 3, Inertia.js, Tailwind CSS
- Database: MySQL 8.0
- Infrastructure: DigitalOcean + Forge

## Domain Glossary
- นักเรียน = Student (role: student)
- ครู = Teacher (role: teacher)
- คาบ = Class session

## Conventions
- Thai status values in DB (ยืนยันแล้ว, รอดำเนินการ)
- Use service classes, not fat controllers
- Money stored as integer satang (THB)

## Key Files
- Routes: routes/web.php, routes/api.php
- Models: app/Models/
- Tests: tests/Feature/

## Out of Scope
- Do not modify authentication code in app/Auth/
```

## File Discovery

`project-brief` searches for `BRIEF.md` starting from the current directory upward to the git root. So you can run it from any subdirectory of your project.

## Notes

- Requires Python 3.11+
- `init` creates `BRIEF.md` in the **current directory**
- Edit command uses `$EDITOR` env var (defaults to `nano` / `notepad`)
- `validate` checks for required sections: Stack, Domain Glossary, Conventions, Key Files
- No AI API calls — purely reads/writes a local Markdown file
