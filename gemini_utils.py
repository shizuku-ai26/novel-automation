# -*- coding: utf-8 -*-
"""
common/gemini_utils.py
Gemini API utility for S26 (Google gen-ai SDK)
"""
import os
from typing import Optional


def load_gemini_config() -> dict:
    try:
        from common.utils import load_config
        config = load_config()
        api_key    = config.get("api_keys", {}).get("gemini", "")
        gemini_cfg = config.get("gemini", {})
        return {
            "api_key":    api_key or os.environ.get("GEMINI_API_KEY", ""),
            "model":      gemini_cfg.get("model", "gemini-2.5-flash"),
            "max_tokens": int(gemini_cfg.get("max_tokens", 8000)),
            "timeout":    int(gemini_cfg.get("timeout", 120)),
        }
    except Exception:
        return {
            "api_key":    os.environ.get("GEMINI_API_KEY", ""),
            "model":      "gemini-2.5-flash",
            "max_tokens": 8000,
            "timeout":    120,
        }


def call_gemini_thinking(prompt: str,
                         model: Optional[str] = None,
                         max_tokens: Optional[int] = None,
                         config: Optional[dict] = None) -> str:
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ImportError(
            "google-genai is not installed.\n"
            "Run: pip install google-genai"
        )

    cfg = load_gemini_config()
    if config:
        api_key = (config.get("api_keys", {}).get("gemini", "")
                   or config.get("gemini_api_key", ""))
        if api_key:
            cfg["api_key"] = api_key

    api_key  = cfg["api_key"]
    _model   = model or cfg["model"]
    _max_tok = max_tokens or cfg["max_tokens"]

    if not api_key:
        raise ValueError("Gemini API key is not set in config.yaml (api_keys.gemini).")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=_max_tok,
                temperature=0.85,
            ),
        )
        return response.text or ""
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


def get_available_models() -> list:
    return [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash-thinking-exp",
    ]
