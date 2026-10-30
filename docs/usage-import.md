# Local Usage Import

Run `ai-cost today` to import recorded usage and report the total, or preview with
`ai-cost import --dry-run`. Use `ai-cost import --provider claude --source PATH`
for a specific transcript or directory. All reports work without a network connection.

| Provider | Default source | Supported records |
|---|---|---|
| Claude | `~/.claude/projects/**/*.jsonl` | Assistant records with `message.id`, `message.model`, `message.usage`, `sessionId`, and `timestamp`; flat usage records are also accepted |
| Gemini | `~/.gemini/tmp/**/session-*.json` and `.jsonl` | JSON documents containing `sessionId` and `messages`, JSONL metadata plus `type: gemini` messages with `tokens`, and legacy `usageMetadata` |

Set `AI_CLAUDE_SESSION_DIR` / `AI_GEMINI_SESSION_DIR` to change source directories.
Explicit Gemini source directories accept `.json` / `.jsonl`; automatic discovery uses
only `session-*` files and never reads OAuth credential files. Source files are never modified.

## Identity and Updates

The importer stores a stable hash of provider, session ID, and message ID in `cost-log.jsonl`.
If no message ID exists, timestamp and model identify the request. Copied transcripts do not
add another request. Repeated streaming records use the highest recorded token counts.
Newly recorded usage for an existing request updates it in place. Interrupted imports can
be repeated: the cost log is the identity ledger, not a separately maintained counter.

`usage-import-state.json` caches unchanged file signatures. Changing the log or registry sources
invalidates this cache. The cache is included in backups; deleting it only triggers a rescan.
Malformed/incomplete source lines are reported and retried. Other valid requests still import.
An invalid existing cost log blocks import; inspect it with `ai-data doctor` first.

## Pricing and Scope

Input/output counts are retained with recorded timestamp, model, provider, and session.
Claude cached reads and writes are added to input token totals and retained separately.
Gemini cached input is a subset of prompt input; thoughts are included in output.
Cache rates are used only when explicitly present as per-million `cache_read` / `cache_write`
fields in the shared [model registry](model-registry.md) (including user/legacy overrides).
Unknown model/cache/tool pricing remains `null` and is excluded
from monetary totals with a visible warning. Totals with unpriced records are incomplete.
Claude `server_tool_use` request counts are retained separately and make the request's price
unknown until server-tool pricing is supported; they are not silently counted as token-only charges.
Source logs and configured rates determine accuracy; provider subscriptions are not billed
by these estimates. Historical imports do not increment the legacy live session budget
counter in global/project scope. Session-scope budgets include that session's imported costs.

Use `AI_USAGE_AUTO_IMPORT=0` or `--no-import` on `ai-cost` reports to keep reporting read-only.
`token-budget status` and the AI usage section of `daily-report` also synchronize local usage;
use `AI_USAGE_AUTO_IMPORT=0` to disable synchronization for these commands.
The default global scope includes all sessions found under the configured directories.
Use `--scope project` or `--scope session --scope-session ID` to isolate data and
conservatively filter project/session provenance. Missing project metadata requires
explicit `--source` attribution; known different projects are never reassigned.
See [scope and JSON contract](cli-contract.md) for storage isolation and exit codes.
Changed logs are backed up before import. Neither source prompt text nor credentials are archived.
Backups contain personal skill data and are not encrypted. There is no background scheduler.

## Format References

- [Gemini recording types](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingTypes.ts)
- [Gemini recording implementation](https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/services/chatRecordingService.ts)
- [Claude transcript usage example in the upstream issue tracker](https://github.com/anthropics/claude-code/issues/25941)
- [Claude server-tool usage accounting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)

Provider formats can change. Files without per-request model, usage, and timezone-aware
timestamps cannot be priced/imported reliably and are skipped with diagnostics when usage is present.
