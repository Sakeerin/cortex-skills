# Central Administration CLI

Use the existing Python 3.11+ runtime; no package installation is required:

```bash
python3 /path/to/cortex-skills/cortex.py status --json
```

The installer adds the repository root to PATH for `cortex`. From a checkout use
`bash ./cortex status` on Bash, or `./cortex.cmd status` in Windows PowerShell.
The Windows wrapper prefers the checkout's `.venv/Scripts/python.exe`, falling back
to `python`. Existing per-skill entrypoints and wrappers continue to work.

## Administration

```bash
cortex status --json
cortex status --scope project --json
cortex doctor --json
cortex doctor --repair --scope session --scope-session chat-42 --json
cortex skills list --json
cortex skills validate --all
cortex skills validate todo
cortex models list --json
cortex models validate
```

`status` reports runtime, installation path, selected data directory, detected provider,
active model, registry files/counts, skill count and optional tool availability. It
does not print API key values. `doctor` checks Python, required runtime assets, model
registry, skill structure/Python syntax and data schemas. Both commands are offline:
they do not test provider connectivity, import transcripts, install dependencies,
edit configuration, pull models or update the repository.

`doctor --repair` opts into the existing data doctor's safety-backup and JSONL
quarantine workflow for the **selected namespace only**. It does not repair registry
JSON, overwrite source code, install tools or change provider configuration. Integrity
failures return code 5 with structured details. Reads may create the selected data
directory/lock as documented for the existing data doctor.

Skill listing discovers installed `*/SKILL.md` files; syntax checks parse scripts
without executing them. Missing required scripts or wrappers fail validation.
Missing optional documentation sections are warnings. Skill names cannot escape
the installation directory. `skills validate --all` checks the discovered catalog;
`doctor` additionally checks known Python entrypoints for installation completeness.

## Existing Command Routing

| Central command | Existing entrypoint |
|---|---|
| `cortex provider ...` | `ai-provider ...` |
| `cortex data ...` | `ai-data ...` |
| `cortex cost ...` | `ai-cost ...` |
| `cortex budget ...` | `token-budget ...` |
| `cortex context ...` | `ai-context ...` |
| `cortex usage import ...` | `ai-cost import ...` |
| `cortex run SKILL ...` | One of the 16 bundled Python skill CLIs |

```bash
cortex data backup --scope project --json
cortex usage import --provider claude --dry-run --json
cortex cost breakdown --no-import --scope project --json
cortex budget status --scope session --scope-session chat-42 --json
cortex run todo add --title "Project task" --scope project --json
cortex run ai-model-list --provider ollama --offline --json
cortex run memory get stack --scope project --json
```

Routing invokes the existing handlers under one scope/JSON/exit-code boundary,
without shell evaluation or nested result envelopes. It does not execute arbitrary
paths, shell commands or newly discovered custom skills. `sync-git` and `time` are
not Python routes; use their existing shell interfaces. Provider/context and other
non-data routes require global scope; pass `--scope global` when a project/session
default is configured. Registry definitions are also global; see [model registry](model-registry.md).

Root/global flags may appear before or after a subcommand. Forwarded command options
otherwise remain unchanged. Use `cortex COMMAND --help` or `cortex run SKILL --help`
for details. `--json`, warning handling and exit codes 0-6 follow the existing
[CLI contract](cli-contract.md), including error paths and help. Only explicit live
commands such as `cortex provider test` or `cortex run ai-model-list` without `--offline`
contact provider endpoints; cost reports may import local transcripts under their
existing auto-import settings. The central CLI never commits or pushes on its own.
