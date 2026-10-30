# Central Model Registry

Model IDs, providers, aliases, context windows, suffix matching and estimated token
rates are maintained by `_lib/model_registry.py`. Context reporting, offline model
lists, provider model discovery, manual cost logging and usage imports share it.
It has no SDK or third-party Python dependency and never makes network requests.

## Sources and Precedence

1. `model-registry.json` is the versioned, bundled catalog.
2. `cost-rates.json` is a backwards-compatible, price-only overlay. It is now empty
   in a fresh checkout because its previous defaults moved to the bundled catalog.
   Existing custom price entries remain supported; they do not register context/provider metadata.
3. `AI_SKILLS_DATA_DIR/model-overrides.json` contains complete user model definitions
   and overrides. `AI_MODEL_REGISTRY=/path/to/custom.json` selects another user file.
   User definitions take precedence, including explicitly unknown (`null`) prices.

The user registry is **global**, not inside project/session namespaces. Changing it
affects future estimates in every scope. Mutating CLI commands require global scope:
use `--scope global` if `AI_SKILLS_SCOPE` is configured for a project/session.
Bundled and legacy-price files cannot be selected as the writable user registry.
No startup files are created merely by reading the catalog.

The initial catalog preserves the repository's existing configured limits and prices.
It is an offline snapshot, **not a claim of current provider prices, model availability,
or a provider invoice**. Maintain these estimates intentionally; there is no automatic
web download or silent live-provider overwrite of local metadata.

## Commands

```bash
cortex models list --provider openai --json
cortex models list --query mini
cortex models show gpt-4o-mini --provider openai
cortex models validate --json
cortex models set team-model --provider openai --context 64000 --input 1 --output 2 --alias team
cortex models set team-model --provider openai --exact
cortex models set team-model --provider openai --unpriced
cortex models remove team-model --provider openai
cortex models export --output ./registry-snapshot.json
cortex models export --overrides-only --output ./user-models.json
```

`set` upserts a user entry. Unspecified metadata is preserved for existing models;
new models start with context 0, no aliases and unknown rates. Rate options require
both `--input` and `--output`; optional `--cache-read`/`--cache-write` use the same
USD-per-million-token units. Setting rates replaces the entire rate object.
`--alias` replaces the alias array, while `--clear-aliases` empties it.
`--exact` disables snapshot/tag suffix matching; `--allow-suffix` enables it again.

`remove` only removes user definitions. Removing an override reveals the bundled
definition again; deleting a bundled model itself is not supported. `export` defaults
to the effective catalog, while `--overrides-only` exports only the user document.
Exports refuse to overwrite existing files. JSON stdout uses the common envelope;
`--output` writes the versioned document itself, not an envelope.

Default user definitions are included in `ai-data backup --scope global` and validated
by data doctor. An `AI_MODEL_REGISTRY` file at a custom location is outside that backup
allowlist; export/back it up explicitly. Project/session backups do not include the
global registry. Restore of `model-overrides.json` follows normal overwrite safeguards.
`cortex doctor` validates both effective registry metadata and selected-scope data.
It never automatically repairs or resets invalid registry JSON.

## Document Schema

```json
{
  "version": 1,
  "models": [
    {
      "provider": "openai",
      "id": "team-model",
      "context_window": 64000,
      "aliases": ["team"],
      "match_suffix": false,
      "rates": {"input": 1.0, "output": 2.0}
    }
  ]
}
```

Supported providers: `claude`, `gemini`, `openai`, `ollama`, `mistral`, `lmstudio`.
Every model requires all six fields shown above. Unknown fields, invalid types,
non-finite/negative prices and duplicate IDs/aliases within a provider are rejected.
`context_window: 0` means unknown. `rates: null` means unpriced; missing cache prices
are not inferred. Local-provider token rates must be zero (or unknown in metadata);
runtime estimates for configured Ollama/LM Studio usage are zero-token-price estimates,
not infrastructure-cost estimates. A remote model named `llama-*` is not automatically free.

IDs and aliases match case-insensitively. Exact matches take precedence; otherwise
only an enabled `match_suffix` followed by `-` or `:` matches, using the longest
matching ID/alias. Thus `gpt-4o-mini-2024-07-18` uses mini metadata rather than the
shorter `gpt-4o` entry. Unknown families do not inherit arbitrary context windows.
The same ID may exist across providers; ambiguous lookups require `--provider`
and return conflict code 4 instead of guessing. The bundled-only `provider_prefixes`
map supplies provider detection hints, never context windows or prices.

Writes validate both the proposed file and its merged catalog before atomic replacement,
under the shared cross-process lock. Cached readers detect catalog, legacy-rate and
override file changes. Imported usage rechecks all three sources: changing prices or
aliases invalidates import caches and reprices affected recorded requests on the next
import, with a safety backup. Manually logged historical entries keep their recorded
estimates; they are not retroactively repriced. Registry corruption raises data-error
code 5, not a silent fallback to stale defaults. Stored-cost reporting with `--no-import`
can still read historical estimates without loading the registry.
