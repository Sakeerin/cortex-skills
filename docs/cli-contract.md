# Scopes and Machine Output

## Storage Scopes

`todo`, `notes`, `memory`, `prompt-lib`, `ai-cost`, `token-budget`, `daily-report`,
and `ai-data` share these options. Options may appear before or after a subcommand.

```bash
todo add --title "Shared task" --scope global
todo add --title "Project task" --scope project
todo list --scope project --json
notes add "Session note" --scope session --scope-session chat-42
memory list --scope project --scope-project /path/to/project
ai-cost today --scope session --scope-session chat-42 --json
ai-data backup --scope project
ai-data doctor --scope session --scope-session chat-42 --json
```

The default is **global**: existing data files and behavior remain in place.
Project identity is the canonical absolute path of the nearest Git root, or the
current directory outside Git. Subdirectories share their Git project's scope;
different worktrees have different identities. `--scope-project PATH` selects a
different existing project directory without changing the process working directory.
Moving a project changes its identity; explicitly back up and restore into its new scope.

Session identity is the exact session ID **within a project**, not a provider name
or an automatically generated ID. Supply it explicitly or through configuration:

```bash
export AI_SKILLS_SCOPE=session
export AI_SKILLS_PROJECT_DIR=/path/to/project
export AI_SKILLS_SESSION_ID=chat-42
```

CLI flags override these defaults; `--scope global` bypasses configured project/session
selection. `--scope-project` requires a non-global scope; `--scope-session` requires
session scope. Missing session IDs are usage errors, not an implicit "default" session.
The existing `todo --project NAME` remains a task label/filter, **not** a storage selector.

Storage under `AI_SKILLS_DATA_DIR`:

```text
todos.jsonl, notes.jsonl, ...       # legacy global namespace
scopes/p-<project-hash>/...         # project namespace
scopes/p-<project-hash>/s-<session-hash>/...
```

Identifiers are the first 128 bits of SHA-256, avoiding unsafe path characters and
keeping Windows paths short. Namespace directories cannot be symlinks/junctions.
Scopes isolate all reads, writes, deletes, imports, budgets, backups and repairs.
They do not inherit parent data or aggregate child namespaces. Global reports are
**not** all-scope rollups. There is no automatic migration, cross-scope search, or
filesystem access-control boundary between processes running as the same user.

`ai-data --data-dir PATH` overrides the **base root**; scope selection still applies.
Backup/doctor operate on the selected namespace only, not recursively on child
sessions or projects. Restoring an archive into another explicitly selected scope
is supported as an intentional copy. Archives do not reselect their original scope.
Provider configuration, raw `ai-session-log` browsing, Git/BRIEF utilities and
scaffolding are not namespace-backed and reject scope flags. `daily-report` uses
the selected project's Git directory when collecting commits.

## Scoped Usage Import

Global imports retain their existing all-source behavior. Automatic project/session
imports require an absolute `cwd`, `projectDirectory`, or `projectPath` in the recorded
session metadata that resolves to the selected project. Session imports additionally
require an exact session ID match. Unknown ownership and other scopes are skipped;
explicit import reports expose `skipped_scope` counts. Unknown records are not guessed
from filenames or provider-specific encoded directory names.

Some Gemini/older transcripts lack project paths. Use an intentional
`ai-cost import --provider gemini --source FILE --scope project` to attribute those
records to the selected project. Explicit sources never override a **known** different
project or the session filter. Automatic and explicit discovery use separate caches.
The same source imported into separate scopes is independently accounted there;
do not sum namespace totals as though they were disjoint invoices.

In session scope, manual usage automatically records the selected session ID;
a conflicting `log --session-id` is rejected. Session-budget usage includes imported
and manually recorded costs in that session. `token-budget reset session` records a
monetary baseline without deleting usage. Later imports/repricing can change this
estimate. In global/project scope, the existing live session-spend counter is retained
and historical imports do not increment it. Unknown prices remain excluded with warnings.

## JSON Contract

All **16 Python skill CLIs** accept `--json`, including help and error paths.
The [central `cortex` CLI](central-cli.md) uses the same envelope and codes for
administration and forwarded commands, without nesting envelopes.
The shell-only `sync-git` and `time`/`date` retain their existing interfaces.
Stdout contains exactly one UTF-8 JSON document, without banners, progress text,
ANSI escapes or tracebacks. Warnings are included in the envelope, not stderr.

```json
{
  "schema_version": 1,
  "ok": true,
  "exit_code": 0,
  "scope": {"kind": "project", "project": "/work/app", "session": null},
  "data": [],
  "error": null,
  "warnings": []
}
```

`data` contains command-specific records, arrays, or report objects. Empty lists are
successful results. Text-oriented commands (help, Markdown/context rendering) use
`{"text": "..."}` when they do not provide structured records. Errors use
`{"code": "not_found", "message": "..."}`; `data` may still contain a partial
import/doctor/restore report. Interactive editor commands reject `--json` instead of
opening a blocking UI. Put literal option-like positional values after `--`, or use
`--title=--json` for literal option values.

**Compatibility note:** previously `ai-data ... --json` and `ai-cost import --json`
returned bare reports. Those reports now live under `data`; update automation from
`report["backup"]` to `report["data"]["backup"]`, for example. Without `--json`,
human-readable output remains the default. Failed commands now use the shared codes
below instead of collapsing every error into 1.

## Exit Codes

| Code | Error name | Meaning |
|---|---|---|
| 0 | (none) | Success, including empty results, help, and valid budget-status reports |
| 1 | `operation_failed` | Other operation, permission, Git, or internal failure |
| 2 | `invalid_arguments` | Invalid/missing flags, scope, IDs, token counts, or budget values |
| 3 | `not_found` | Requested record or input file is absent |
| 4 | `conflict` | Duplicate record, ambiguous ID, existing backup, or restore overwrite required |
| 5 | `invalid_data` | Invalid JSON/archive, unresolved doctor issues, or incomplete explicit usage import |
| 6 | `unavailable` | Provider check, environment dependency, timeout/lock contention, or external tool failure |

An exceeded budget is report data (`exceeded: true`), not an execution failure.
Lenient legacy JSONL readers may return surviving records with warnings; use
`ai-data doctor --json` for a strict integrity check. Explicit import warnings use
code 5 even if some records were imported. Automatic best-effort import warnings
do not fail an otherwise valid report; inspect `warnings` before trusting totals.

For new Python skills, import `command`, `set_result`, and `CLIError` from `_lib/cli.py`.
Decorate `main` with `@command(scoped=True)` only for namespace-backed data commands,
set structured results in handlers, and use `raise SystemExit(main())` at the entrypoint.
