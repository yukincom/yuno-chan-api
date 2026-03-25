# llm_client.py
"""LLM呼び出しの差し替え層

AI_PROVIDER = gemini（デフォルト）/ openai互換（grok / ollama / openrouter）

- call()         : 通常会話。AI_PROVIDERで切り替え
- call_search()  : 検索付き応答。Gemini固定
- call_summary() : 要約生成。AI_PROVIDERで切り替え
"""
import os
import re
from dotenv import load_dotenv
from config import config

from google import genai
from google.genai import types

from openai import OpenAI

load_dotenv()
load_dotenv(".env.local", override=True)

# ─────────────────────────────────────────────────────────
# 共通：思考プロセス除去（全プロバイダー適用）
# ─────────────────────────────────────────────────────────
def _strip_thinking(text: str) -> str:
    if not text:
        return ""
    # <think>...</think> タグごと除去（多くのモデルで使われる）
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # THINKING_STRIP_PATTERNS で設定したパターン以降を抽出
    for pattern in config.THINKING_STRIP_PATTERNS:
        pattern = pattern.strip()
        if pattern and pattern in text:
            text = text.split(pattern)[-1].strip()
            break
    # マークアップ残骸除去
    text = re.sub(r'^[\s\*\:]+', '', text).strip()
    text = re.sub(r'\*+', '', text).strip()
    return text or "ごめん、うまく答えられなかった！"

# ─────────────────────────────────────────────────────────
# 外部インターフェース
# ─────────────────────────────────────────────────────────

def call(prompt: str) -> str:
    """通常会話。AI_PROVIDERで切り替え"""
    print(f"[LLM] 💬 chat provider={config.AI_PROVIDER} model={config.AI_CHAT_MODEL}")
    if config.AI_PROVIDER == "gemini":
        return _call_gemini(
            prompt,
            model=config.AI_CHAT_MODEL,
            temperature=config.AI_CHAT_TEMPERATURE,
            use_search=False
        )
    return _call_openai_compatible(
        prompt,
        model=config.AI_CHAT_MODEL,
        temperature=config.AI_CHAT_TEMPERATURE
    )


def call_search(prompt: str) -> str:
    """検索付き応答。Gemini固定"""
    print(f"[LLM] 🔍 search model={config.AI_SEARCH_MODEL}")
    return _call_gemini(
        prompt,
        model=config.AI_SEARCH_MODEL,
        temperature=config.AI_SEARCH_TEMPERATURE,
        use_search=True
    )


def call_summary(prompt: str) -> str:
    """要約生成。AI_PROVIDERで切り替え"""
    print(f"[LLM] 📝 summary provider={config.AI_PROVIDER} model={config.AI_SUMMARY_MODEL}")
    if config.AI_PROVIDER == "gemini":
        return _call_gemini(
            prompt,
            model=config.AI_SUMMARY_MODEL,
            temperature=config.AI_SUMMARY_TEMPERATURE,
            use_search=False
        )
    return _call_openai_compatible(
        prompt,
        model=config.AI_SUMMARY_MODEL,
        temperature=config.AI_SUMMARY_TEMPERATURE
    )


# ─────────────────────────────────────────────────────────
# Gemini
# ─────────────────────────────────────────────────────────

def _call_gemini(prompt: str, model: str, temperature: float, use_search: bool) -> str:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    gen_config = types.GenerateContentConfig(
        max_output_tokens=config.AI_MAX_OUTPUT_TOKENS,
        temperature=temperature,
        tools=[types.Tool(google_search=types.GoogleSearch())] if use_search else None
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=gen_config
    )
    return _strip_thinking(response.text.strip()) 

# ─────────────────────────────────────────────────────────
# OpenAI互換（Grok / Ollama / OpenRouter）
# ─────────────────────────────────────────────────────────

def _call_openai_compatible(prompt: str, model: str, temperature: float) -> str:
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY", "ollama"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    # Qwen3系: /no_think で思考プロセス自体を抑制
    if any(kw in model.lower() for kw in ["qwen3", "qwen-3"]):
        prompt = prompt + "\n/no_think"

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=config.AI_MAX_OUTPUT_TOKENS,
        temperature=temperature,
    )

    content = response.choices[0].message.content
    if not content:
        content = getattr(response.choices[0].message, 'reasoning_content', '') or ''

    return _strip_thinking(content) 