"""
Storage callbacks for persisting user settings in localStorage
"""

from dash import Input, Output, State, callback_context as ctx, no_update
from webui.utils.storage import DEFAULT_SETTINGS


def _parse_symbols(value):
    if isinstance(value, list):
        return [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]
    return [symbol.strip().upper() for symbol in (value or "").split(",") if symbol.strip()]


def register_storage_callbacks(app):
    """Register storage-related callbacks"""

    # Callback to save settings to localStorage when they change
    @app.callback(
        Output("settings-store", "data"),
        [
            Input("ticker-input", "value"),
            Input("analyst-market", "value"),
            Input("analyst-social", "value"),
            Input("analyst-news", "value"),
            Input("analyst-fundamentals", "value"),
            Input("analyst-macro", "value"),
            Input("research-depth", "value"),
            Input("allow-shorts", "value"),
            Input("loop-interval", "value"),
            Input("market-hours-input", "value"),
            Input("trade-after-analyze", "value"),
            Input("trade-dollar-amount", "value"),
            Input("llm-provider", "value"),
            Input("backend-url", "value"),
            Input("output-language", "value"),
            Input("checkpoint-enabled", "value"),
            Input("quick-llm", "value"),
            Input("deep-llm", "value"),
            Input("quick-llm-custom-model", "value"),
            Input("deep-llm-custom-model", "value"),
            Input("google-thinking-level", "value"),
            Input("anthropic-effort", "value"),
            Input("xai-reasoning-effort", "value"),
        ],
        [
            State("settings-store", "data"),
            State("loop-enabled", "value"),
            State("market-hour-enabled", "value")
        ],
        prevent_initial_call=True
    )
    def save_settings(ticker_symbols, analyst_market, analyst_social, analyst_news,
                     analyst_fundamentals, analyst_macro, research_depth, allow_shorts,
                     loop_interval, market_hours_input,
                     trade_after_analyze, trade_dollar_amount,
                     llm_provider, backend_url, output_language, checkpoint_enabled,
                     quick_llm, deep_llm, quick_llm_custom_model, deep_llm_custom_model,
                     google_thinking_level, anthropic_effort, xai_reasoning_effort,
                     current_settings, loop_enabled, market_hour_enabled):
        """Save settings to localStorage store"""
        
        # Don't save if triggered by initial load
        if not ctx.triggered:
            return no_update
        
        new_settings = {
            "ticker_input": ", ".join(_parse_symbols(ticker_symbols)),
            "analyst_market": analyst_market,
            "analyst_social": analyst_social,
            "analyst_news": analyst_news,
            "analyst_fundamentals": analyst_fundamentals,
            "analyst_macro": analyst_macro,
            "research_depth": research_depth,
            "allow_shorts": allow_shorts,
            "loop_enabled": loop_enabled,
            "loop_interval": loop_interval,
            "market_hour_enabled": market_hour_enabled,
            "market_hours_input": market_hours_input,
            "trade_after_analyze": trade_after_analyze,
            "trade_dollar_amount": trade_dollar_amount,
            "llm_provider": llm_provider,
            "backend_url": backend_url,
            "output_language": output_language,
            "checkpoint_enabled": checkpoint_enabled,
            "quick_llm": quick_llm,
            "deep_llm": deep_llm,
            "quick_llm_custom_model": quick_llm_custom_model or "",
            "deep_llm_custom_model": deep_llm_custom_model or "",
            "google_thinking_level": google_thinking_level or "",
            "anthropic_effort": anthropic_effort or "",
            "xai_reasoning_effort": xai_reasoning_effort or "",
        }
        
        # Check if settings actually changed to prevent circular updates
        if current_settings:
            settings_changed = False
            for key, value in new_settings.items():
                if current_settings.get(key) != value:
                    settings_changed = True
                    break
            
            # If no changes, don't update the store to prevent circular callback.
            # Returning current_settings unchanged still fires downstream
            # Input(settings-store, data) callbacks (Dash doesn't dedupe by
            # value equality) - only no_update actually stops propagation,
            # which matters now that restore_settings() reads this store back
            # into the controls on load.
            if not settings_changed:
                return no_update

        return new_settings

    # Restore settings from localStorage into the actual controls on page
    # load. dcc.Store(storage_type='local') already syncs settings-store's
    # `data` from the browser before callbacks resolve, but nothing
    # previously read it back into the controls themselves - every control
    # kept its hardcoded layout default (e.g. llm-provider="openai") on
    # every refresh, silently discarding whatever the user had picked.
    #
    # quick-llm/deep-llm are deliberately excluded here: they're already
    # Outputs of update_provider_models (control_callbacks.py), which now
    # also consults settings-store directly to restore the persisted model
    # choice. Adding them as Outputs here too would be a Dash duplicate-
    # output conflict.
    @app.callback(
        [
            Output("ticker-input", "value"),
            Output("analyst-market", "value"),
            Output("analyst-social", "value"),
            Output("analyst-news", "value"),
            Output("analyst-fundamentals", "value"),
            Output("analyst-macro", "value"),
            Output("research-depth", "value"),
            Output("allow-shorts", "value"),
            Output("loop-enabled", "value"),
            Output("loop-interval", "value"),
            Output("market-hour-enabled", "value"),
            Output("market-hours-input", "value"),
            Output("trade-after-analyze", "value"),
            Output("trade-dollar-amount", "value"),
            Output("llm-provider", "value"),
            Output("backend-url", "value"),
            Output("output-language", "value"),
            Output("checkpoint-enabled", "value"),
            Output("quick-llm-custom-model", "value"),
            Output("deep-llm-custom-model", "value"),
            Output("google-thinking-level", "value"),
            Output("anthropic-effort", "value"),
            Output("xai-reasoning-effort", "value"),
        ],
        Input("settings-store", "data"),
        prevent_initial_call=False,
    )
    def restore_settings(stored):
        """Push persisted settings into the controls once, on load."""
        merged = {**DEFAULT_SETTINGS, **(stored or {})}
        return (
            merged["ticker_input"],
            merged["analyst_market"],
            merged["analyst_social"],
            merged["analyst_news"],
            merged["analyst_fundamentals"],
            merged["analyst_macro"],
            merged["research_depth"],
            merged["allow_shorts"],
            merged["loop_enabled"],
            merged["loop_interval"],
            merged["market_hour_enabled"],
            merged["market_hours_input"],
            merged["trade_after_analyze"],
            merged["trade_dollar_amount"],
            merged["llm_provider"],
            merged["backend_url"],
            merged["output_language"],
            merged["checkpoint_enabled"],
            merged["quick_llm_custom_model"],
            merged["deep_llm_custom_model"],
            merged["google_thinking_level"],
            merged["anthropic_effort"],
            merged["xai_reasoning_effort"],
        )
