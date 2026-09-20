# Updates

Running log of operational changes to this deployment (Raspberry Pi `master`), separate from the git commit history — this is the "what changed and why for this specific setup" log, not a generic changelog.

## 2026-09-20 — Initial setup, tool-calling fix, cron automation

### Environment
- Python venv created, dependencies installed, `.env` configured with Alpaca (paper), Finnhub, FRED, and OpenRouter as the LLM provider.
- WebUI running at `http://192.168.1.161:7860` (background process, restart with `scripts/run_cron_analysis.sh`'s sibling `run_webui_dash.py`).

### Bugs found and fixed (pushed to `main`)
1. **`6cd9798`** — Every analyst's tool-call loop only checked `additional_kwargs["tool_calls"]`, a shape only the OpenAI/local_openai Responses-API wrapper populates. Every other provider (OpenRouter, Anthropic, Google, xAI, etc.) puts tool calls in the standard LangChain `.tool_calls` attribute instead, so **analysts silently skipped every tool call and fabricated ungrounded reports** on any non-OpenAI provider. Added `tradingagents/agents/utils/tool_call_compat.py` to normalize both shapes; fixed the replay-message construction to use `AIMessage(tool_calls=...)` instead of a raw `additional_kwargs` passthrough that produced invalid OpenAI wire-format requests.
2. **`0436b56`** — WebUI settings (`llm-provider`, model choice, etc.) were saved to browser localStorage correctly but never read back into the controls on page refresh — every reload silently reverted to hardcoded defaults (`llm-provider="openai"`). Added a restore-on-load callback; fixed a resulting save/restore ping-pong risk (`no_update` vs returning an unchanged dict).
3. **`0fb6413`** — The OpenAI web-search tools (`get_stock_news_openai`, `get_fundamentals_openai`, `get_global_news_openai`/`get_macro_news_openai`) always hit `api.openai.com` directly regardless of provider config, and use `OPENAI_API_KEY` specifically. Once that key held an OpenRouter key (for the embeddings fix below), these calls started failing with an auth error. Added `get_web_search_client_and_tools()` — when `OPENAI_USE_LOCAL` points `OPENAI_BASE_URL` at OpenRouter, these tools now use OpenRouter's own `openrouter:web_search` chat-completions tool instead, restoring real grounded web search.

### Embeddings / reflection memory
- Self-learning per-agent memory (ChromaDB) requires OpenAI-shape embeddings; the app has no way to route embeddings through a different provider's native API, only through the `OPENAI_USE_LOCAL` + `OPENAI_BASE_URL` local-endpoint mechanism.
- Repointed embeddings at OpenRouter: `OPENAI_USE_LOCAL=true`, `OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_API_KEY=<the OpenRouter key>`, `OPENAI_EMBEDDING_MODEL=qwen/qwen3-embedding-8b`. Verified with a real store/query round-trip through ChromaDB.
- Reflection memory only populates once a decision **resolves** (same symbol re-analyzed on a later date, realized return computed) — expect it to stay empty for the first few days of cron runs.

### Cron automation
- `scripts/cron_daily_analysis.py` — headless runner (no WebUI/Dash dependency): runs the TradingAgentsGraph pipeline for a fixed symbol list, writes the daily ops report (`reports/YYYY-MM-DD.{md,html}`). Trade execution is opt-in (`TRADINGAGENTS_CRON_AUTOTRADE`) and goes through the existing safety layer (kill switch, notional caps, circuit breakers) regardless.
- `scripts/run_cron_analysis.sh` — cron-facing wrapper: activates the venv, logs to `logs/cron_YYYY-MM-DD.log`.
- **Installed in crontab**: `0 14 * * 1-5` (14:00 Europe/Copenhagen local time ≈ 8am US/Eastern, before market open, weekdays only).
- **Watchlist** (`TRADINGAGENTS_CRON_SYMBOLS` in `.env`): `NVDA, LUNR, RDW, ZENA, ATCH, DVLT` — all confirmed tradable on Alpaca paper.
- **Mode**: analysis + report only (`TRADINGAGENTS_CRON_AUTOTRADE=false`). Plan agreed with the user: run analysis-only for **one week** to let the decision log accumulate resolved outcomes and the reflection memory start learning, then revisit enabling auto-execution (still paper trading — live trading is a separate, later, deliberate decision per `ALPACA_USE_PAPER`).

### Next steps / open items
- **~2026-09-27**: revisit flipping `TRADINGAGENTS_CRON_AUTOTRADE=true` once a week of resolved decisions has accumulated.
- Models: cron currently uses the app's own defaults (`gpt-5.4-nano` / `gpt-5.4-mini`, vendor-prefixed for OpenRouter). Verified working end-to-end.
- `run_cron_analysis.sh` currently fully buffers Python's stdout when logging to a file (nothing appears in the log until the process exits) — worth switching to `python -u` for real-time log visibility.
