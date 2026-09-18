# AGENTS.md

## Project layout

- `uv` workspace, two packages, one shared venv at repo root `.venv` (Python 3.14, see `.python-version`):
  - `companion` (root, `src/companion/`) — the aiogram Telegram bot.
  - `companion-core` (`companion-core/src/companion_core/`) — framework-agnostic primitives, imported as `companion_core`. Wired in via `[tool.uv.sources] companion-core = { workspace = true }`, not a published dep.
- `companion-core/pyproject.toml` pins `[tool.ty.environment] python = "../.venv"`, so never create a nested venv there.
- Entry point is `companion = "companion:main"` (i.e. `src/companion/__init__.py:main`). There is **no** `src/companion/__main__.py`, so `python -m companion` fails — use `uv run companion` or `python -m companion.main`.

## Commands

- Install/sync: `uv sync` (CI: `uv sync --locked`).
- Type check: `uv run ty check` from the repo root. **Use the bare form, not `ty check src`**: `src` only covers the `companion` package, and errors in `companion-core/src` are silently missed (verified). CI runs the narrow `ty check src`, so `companion-core` is effectively untype-checked in CI.
- Lint: `uv run ruff check`. Format: `uv run ruff format --check` (fix with `uv run ruff format`). No ruff config overrides in `pyproject.toml`; defaults apply.
- **CI gotcha**: the "Run ruff" step in `.github/workflows/ty.yml` actually runs `uv run ty check src` again (copy-paste bug). Ruff is *not* enforced in CI — run lint/format locally before committing.
- No test suite exists yet.
- Run the bot: `uv run companion`. Requires `config.json` in the **current working directory** (hardcoded `CONFIG_FILEPATH` in `bot/main.py`) matching `AgentConfig` in `src/companion/bot/config.py`.

## Architecture

Request flow: aiogram `Message` -> `amc_view` -> `amc` -> `agents.Runner.run_streamed` -> `aa_view`.

- `bot/main.py` builds everything and passes deps as `Dispatcher(...)` kwargs (`run_config`, `amc`, `amc_view`, `agent`, `session_factory`). Handlers receive them via aiogram DI by parameter name — to add a handler dependency you must also add it to that `Dispatcher(...)` call.
- `amc/` (Agent Message Composer) — aiogram `Message` -> `companion_core` message; handles STT, images, stickers. Yields `MessageComposeEvent`s.
- `amc_view/` — consumes those events to render progress ("Transcribing...") into Telegram, returns the final composed message.
- `aa_view/` — streams `RunResultStreaming` back to Telegram (`telegramify.py` / `telegramify_rich.py`).
- `tools_provider.py` — MCP tools are **not** passed directly to the agent. All MCP tools are collected, name-prefixed `<server>.<tool>`, and hidden behind exactly 3 metatools (`search_tools` / `get_tool_schema` / `exec_tool`) with BM25 ranking. Only `FunctionTool`/`CustomTool` can be proxied; hosted tools must be passed to `Agent(tools=...)` directly.
- Each subpackage follows an `abc.py` (interface) + concrete implementation pattern — add a new implementation of the ABC rather than special-casing an existing one.

### Two different `Agent` classes

The bot's runtime agent is `agents.Agent` from the **openai-agents** library. `companion_core.Agent` / `companion_core.LLM` are a separate, parallel implementation that the bot does **not** use. The bot consumes `companion_core` only for its pydantic message types (`Message`, `AnyMessage`, etc.). Check which one an import refers to before editing.

### Dead / unwired code (don't assume it runs)

- `middlewares.UpdateAccumulatorMiddleware` is never registered on any router or dispatcher.
- `turns_accumulator.py`, `turn_composer.py`, `message_storage.py` are never instantiated outside their own modules.
- So despite their docstrings, rapid-fire user messages are **not** currently debounced or batched into turns; each message hits the agent handler directly.

### Known live bugs (verify before "fixing" surrounding code)

- `handlers/settings.py:set_think_level` requires a `config: AgentConfig` DI param that `bot/main.py` never puts into the dispatcher.
- Even if injected, mutating `config.llm.reasoning_effort` has no effect: `run_config` is built once at startup from that value.
- `bot/main.py` calls `router.message.filter(...)` once per owner in a loop; aiogram ANDs filters on the same router, so more than one `owner_ids` entry blocks all messages.

## Config & secrets

- `config.json`, `secrets/`, `data/`, `.env` are gitignored — never commit them and don't assume they exist in a fresh checkout.
- Sensitive fields use pydantic `SecretStr` / `Secret[T]`; call `.get_secret_value()` (see `bot/main.py`).
- Conversation history is an `AsyncSQLiteSession` at `config.db.db_path` (defaults to `:memory:`).

## Code style

- Python 3.14. Use PEP 695 `type X = Y` aliases (e.g. `type STTConfig = WhisperSTTConfig`), not `TypeAlias`.
- `ty` (Astral) is the typing source of truth, not mypy/pyright. Suppress false positives inline with `# ty: ignore[<rule>]` (see `bot/utils.py`).
- Commit subjects use gitmoji + conventional commits with an optional scope and a capitalized message, e.g. `✨ feat(bot): Add turns accumulator`, `🐛 fix: Fix dev dependencies for GitHub workflows`.
</content>
