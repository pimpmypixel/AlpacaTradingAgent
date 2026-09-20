#!/usr/bin/env python3
"""Headless daily analysis run, intended to be driven by cron.

Runs the same TradingAgentsGraph pipeline as the WebUI/CLI for a fixed list
of symbols, one at a time, and writes the day's operations report. Trade
execution is opt-in (--execute / TRADINGAGENTS_CRON_AUTOTRADE=true) and
always goes through the existing safety layer
(tradingagents.safety.guardrails) — nothing here bypasses it.

Symbols and behavior are configured via environment variables (so cron's
crontab line can stay a one-liner) or CLI flags, which take precedence:

  TRADINGAGENTS_CRON_SYMBOLS       comma-separated tickers (default: a small
                                    example watchlist — edit this)
  TRADINGAGENTS_CRON_AUTOTRADE     "true" to place paper orders (default: false)
  TRADINGAGENTS_CRON_TRADE_AMOUNT  dollar amount per trade (default: 1000)
  TRADINGAGENTS_CRON_ALLOW_SHORTS  "true" for trading mode LONG/NEUTRAL/SHORT
                                    (default: false -> investment mode BUY/HOLD/SELL)
  TRADINGAGENTS_CRON_RESEARCH_DEPTH debate/risk-discuss rounds (default: 2,
                                    lighter than the interactive default of 4,
                                    to keep unattended LLM cost predictable)
  TRADINGAGENTS_CRON_QUICK_LLM      quick-thinker model id
  TRADINGAGENTS_CRON_DEEP_LLM       deep-thinker model id
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

DEFAULT_SYMBOLS = ["NVDA", "AAPL", "MSFT"]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def build_config():
    from tradingagents.default_config import DEFAULT_CONFIG

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = os.getenv("LLM_PROVIDER", config["llm_provider"])
    # OpenRouter has no built-in catalog and needs a vendor-prefixed slug -
    # default_config.py's bare "gpt-5.4-nano"/"gpt-5.4-mini" (the app's
    # normal OpenAI-provider defaults) need an "openai/" prefix to resolve
    # on OpenRouter. Confirmed working end-to-end (real tool calls, grounded
    # reports) as of this writing; re-verify against OpenRouter's current
    # catalog (https://openrouter.ai/models) if this stops working.
    quick_default = config["quick_think_llm"]
    deep_default = config["deep_think_llm"]
    if config["llm_provider"] == "openrouter":
        quick_default = f"openai/{quick_default}"
        deep_default = f"openai/{deep_default}"
    config["quick_think_llm"] = os.getenv("TRADINGAGENTS_CRON_QUICK_LLM", quick_default)
    config["deep_think_llm"] = os.getenv("TRADINGAGENTS_CRON_DEEP_LLM", deep_default)

    # OpenAI Responses-API-only fields (reasoning_effort, text_verbosity, ...)
    # break non-OpenAI providers if sent through; mirrors the same guard the
    # WebUI applies in webui/callbacks/control_callbacks.py.
    if config["llm_provider"] not in ("openai", "local_openai"):
        config["quick_llm_params"] = {}
        config["deep_llm_params"] = {}
    depth = int(os.getenv("TRADINGAGENTS_CRON_RESEARCH_DEPTH", "2"))
    config["max_debate_rounds"] = depth
    config["max_risk_discuss_rounds"] = depth
    config["parallel_analysts"] = True
    config["allow_shorts"] = _env_bool("TRADINGAGENTS_CRON_ALLOW_SHORTS", False)
    config["trading_mode"] = "trading" if config["allow_shorts"] else "investment"
    return config


def run_symbol(symbol: str, config: dict, *, execute: bool, trade_amount: float) -> None:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.dataflows.alpaca_utils import AlpacaUtils

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n--- {symbol} ({today}) ---")

    try:
        graph = TradingAgentsGraph(config=config, debug=False)
        _, final_signal = graph.propagate(symbol, today)
    except Exception:
        print(f"[{symbol}] analysis failed:")
        traceback.print_exc()
        return

    print(f"[{symbol}] signal: {final_signal}")

    if not execute:
        return

    try:
        current_position = AlpacaUtils.get_current_position_state(symbol, strict=True)
        result = AlpacaUtils.execute_trading_action(
            symbol,
            current_position,
            final_signal,
            trade_amount,
            allow_shorts=config.get("allow_shorts", False),
        )
        print(f"[{symbol}] execution result: {result}")
    except Exception:
        print(f"[{symbol}] execution failed:")
        traceback.print_exc()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default=os.getenv("TRADINGAGENTS_CRON_SYMBOLS", ",".join(DEFAULT_SYMBOLS)),
        help="Comma-separated ticker list (stocks and/or CRYPTO/USD pairs).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=_env_bool("TRADINGAGENTS_CRON_AUTOTRADE", False),
        help="Place paper orders based on the decision (default: analysis only).",
    )
    parser.add_argument(
        "--trade-amount",
        type=float,
        default=float(os.getenv("TRADINGAGENTS_CRON_TRADE_AMOUNT", "1000")),
    )
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("No symbols configured (TRADINGAGENTS_CRON_SYMBOLS / --symbols); nothing to do.")
        return 0

    if os.getenv("ALPACA_USE_PAPER", "True").strip().lower() != "true":
        print("Refusing to run: ALPACA_USE_PAPER is not 'True'. This script is for paper trading only.")
        return 1

    config = build_config()

    print(f"=== Cron analysis run {datetime.now().isoformat()} ===")
    print(f"Symbols: {symbols}")
    print(f"Provider/models: {config['llm_provider']} / quick={config['quick_think_llm']} deep={config['deep_think_llm']}")
    print(f"Auto-execute: {args.execute} (trade_amount=${args.trade_amount:.2f})")

    for symbol in symbols:
        run_symbol(symbol, config, execute=args.execute, trade_amount=args.trade_amount)

    try:
        from tradingagents.daily_report import write_daily_report

        md_path, html_path = write_daily_report()
        print(f"\nDaily report written: {md_path}")
    except Exception:
        print("\nFailed to write daily report:")
        traceback.print_exc()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
