# -*- coding: utf-8 -*-
"""
common/openai_utils.py
OpenAI API呼び出しユーティリティ
S24（初版文章生成）で使用

対応モデル（2026年5月現在）：
  gpt-5.5-2026-04-23 : 最新・最高品質 ★最推奨（API利用可）
  o3-pro             : 最高推論品質（組織認証が必要）
  o3                 : 高品質Thinkingモデル（API利用可）
  o4-mini            : 高速・コスト低（API利用可）
  gpt-4o             : 標準・高速（非推論系）

config.yaml 対応パラメータ:
  api_keys:
    openai_api_key: "sk-..."
  openai:
    model: "gpt-5.5-2026-04-23"
    reasoning_effort: "high"   # none/low=Instant / medium=デフォルト / high/xhigh=Thinking
    max_tokens: 4000
    timeout: 300
"""

import os
import json
from pathlib import Path
from typing import Optional


def load_openai_config() -> dict:
    """config.yamlからOpenAI設定を読み込む"""
    try:
        from common.utils import load_config
        config = load_config()
        api_key = (config.get("api_keys", {}).get("openai_api_key", "")
                or config.get("api_keys", {}).get("openai", ""))
        openai_cfg = config.get("openai", {})
        models_cfg = config.get("models", {})
        return {
            "api_key":        api_key or os.environ.get("OPENAI_API_KEY", ""),
            "model":          (openai_cfg.get("model")
                               or models_cfg.get("chatgpt_think")
                               or "gpt-5.5-2026-04-23"),
            "reasoning_effort": openai_cfg.get("reasoning_effort", "high"),
            "max_tokens":     int(openai_cfg.get("max_tokens", 4000)),
            "timeout":        int(openai_cfg.get("timeout", 300)),
        }
    except Exception as e:
        return {
            "api_key":   os.environ.get("OPENAI_API_KEY", ""),
            "model":     "o1",
            "max_tokens": 4000,
            "timeout":   120,
        }


def call_openai_thinking(prompt: str,
                         model: Optional[str] = None,
                         max_tokens: Optional[int] = None,
                         reasoning_effort: Optional[str] = None,
                         config: Optional[dict] = None) -> str:
    """
    OpenAI o1/o3/gpt-4o を呼び出す。
    
    Parameters
    ----------
    prompt : str
        送信するプロンプト
    model : str, optional
        使用するモデル（省略時はconfig.yamlの設定）
    max_tokens : int, optional
        最大トークン数（省略時はconfig.yamlの設定）
    config : dict, optional
        設定辞書（省略時はconfig.yamlから読み込み）
    
    Returns
    -------
    str
        生成されたテキスト
    """
    try:
        import openai
    except ImportError:
        raise ImportError(
            "openai パッケージがインストールされていません。\n"
            "以下を実行してください：pip install openai"
        )

    cfg = load_openai_config()
    if config:
        cfg.update(config)

    api_key   = cfg["api_key"]
    _model          = model or cfg["model"]
    _max_tok        = max_tokens or cfg["max_tokens"]
    _reasoning_eff  = reasoning_effort or cfg.get("reasoning_effort", "high")

    if not api_key:
        raise ValueError(
            "OpenAI APIキーが設定されていません。\n"
            "config.yaml の api_keys.openai_api_key に設定するか、\n"
            "環境変数 OPENAI_API_KEY を設定してください。"
        )

    client = openai.OpenAI(api_key=api_key)

    # o1/o3 系はシステムメッセージ非対応・temperatureパラメータ不要
    is_reasoning = (_model.startswith("o1") or _model.startswith("o3")
                    or _model.startswith("o4"))

    messages = [{"role": "user", "content": prompt}]

    try:
        is_gpt55 = _model.startswith("gpt-5.5")

        if is_gpt55:
            # GPT-5.5: reasoning_effortでInstant/Thinkingを切り替え
            mode_label = "Thinking" if _reasoning_eff in ("high", "xhigh") else "Instant"
            print(f"    モード: {mode_label}（reasoning_effort={_reasoning_eff}）")
            response = client.chat.completions.create(
                model=_model,
                messages=messages,
                max_completion_tokens=_max_tok,
                reasoning_effort=_reasoning_eff,
            )
        elif is_reasoning:
            # o1/o3/o4: reasoning モデル
            response = client.chat.completions.create(
                model=_model,
                messages=messages,
                max_completion_tokens=_max_tok,
            )
        else:
            # gpt-4o 等: 通常の呼び出し
            response = client.chat.completions.create(
                model=_model,
                messages=messages,
                max_tokens=_max_tok,
                temperature=0.85,
            )

        return response.choices[0].message.content or ""

    except openai.AuthenticationError:
        raise ValueError("OpenAI APIキーが無効です。config.yamlを確認してください。")
    except openai.RateLimitError:
        raise RuntimeError("OpenAI APIのレート制限に達しました。しばらく待ってから再実行してください。")
    except openai.APITimeoutError:
        raise RuntimeError(f"OpenAI APIがタイムアウトしました（{cfg['timeout']}秒）。")
    except openai.NotFoundError as e:
        if "must be verified" in str(e):
            raise RuntimeError(
                f"モデル {_model} は組織認証が必要です。"
                f" --openai-model o3 に変更するか組織認証を完了してください。"
            )
        raise RuntimeError(f"OpenAI API error: {e}")
    except Exception as e:
        raise RuntimeError(f"OpenAI API呼び出しエラー: {e}")


def get_available_models() -> list:
    """利用可能なモデル一覧を返す（2026年5月時点）"""
    return ["gpt-5.5-2026-04-23", "o3-pro", "o3", "o4-mini", "gpt-4o"]
