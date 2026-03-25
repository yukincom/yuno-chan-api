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
    return response.text.strip()


# ─────────────────────────────────────────────────────────
# OpenAI互換（Grok / Ollama / OpenRouter）
# ─────────────────────────────────────────────────────────

def _call_openai_compatible(prompt: str, model: str, temperature: float) -> str:
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY", "ollama"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=config.AI_MAX_OUTPUT_TOKENS,
        temperature=temperature,
    )
    text = response.choices[0].message.content.strip()

    # Thinking系モデルの思考プロセスを除去
    for pattern in config.THINKING_STRIP_PATTERNS:
        pattern = pattern.strip()
        if pattern and pattern in text:
            text = text.split(pattern)[-1].strip()
            break

    # マークアップ除去
    text = re.sub(r'^[\s\*\:]+', '', text).strip()
    text = re.sub(r'\*+', '', text).strip()

    return text