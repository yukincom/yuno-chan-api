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

from huggingface_hub import try_to_load_from_cache, _CACHED_NO_EXIST
import threading

load_dotenv()
load_dotenv(".env.local", override=True)

# ─────────────────────────────────────────────────────────
# 共通：思考プロセス除去（全プロバイダー適用）
# ─────────────────────────────────────────────────────────
def _strip_thinking(text: str) -> str:
    if not text:
        return ""
    # <think>...</think> タグごと除去（Qwen3系）
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()    
    # <tool_call>...<tool_call> タグごと除去
    text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL).strip()
    # THINKING_STRIP_PATTERNS で設定したパターン以降を抽出
    for pattern in config.THINKING_STRIP_PATTERNS:
        pattern = pattern.strip()
        if pattern and pattern in text:
            text = text.split(pattern)[-1].strip()
            break
    # マークアップ残骸除去
    text = re.sub(r'^[\s\*\:]+', '', text).strip()
    text = re.sub(r'\*+', '', text).strip()
    return text or "ごめん、僕にはよくわからないや！"

# ─────────────────────────────────────────────────────────
# 外部インターフェース
# ─────────────────────────────────────────────────────────

def call(prompt: str) -> str:
    print(f"[LLM] 💬 chat provider={config.AI_PROVIDER} model={config.AI_CHAT_MODEL}")
    if config.AI_PROVIDER == "gemini":
        return _call_gemini(prompt, model=config.AI_CHAT_MODEL, temperature=config.AI_CHAT_TEMPERATURE, use_search=False)
    if config.AI_PROVIDER == "mlx":
        return _call_mlx(prompt, model=config.AI_CHAT_MODEL, temperature=config.AI_CHAT_TEMPERATURE)
    return _call_openai_compatible(prompt, model=config.AI_CHAT_MODEL, temperature=config.AI_CHAT_TEMPERATURE)

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
    """要約生成。AI_SUMMARY_PROVIDERで切り替え（デフォルトはgemini）"""
    print(f"[LLM] 📝 summary provider={config.AI_SUMMARY_PROVIDER} model={config.AI_SUMMARY_MODEL}")
    if config.AI_SUMMARY_PROVIDER == "gemini":
        return _call_gemini(
            prompt,
            model=config.AI_SUMMARY_MODEL,
            temperature=config.AI_SUMMARY_TEMPERATURE,
            use_search=False
        )
    if config.AI_SUMMARY_PROVIDER == "mlx":
        return _call_mlx(prompt, model=config.AI_SUMMARY_MODEL, temperature=config.AI_SUMMARY_TEMPERATURE)
    return _call_openai_compatible(
        prompt,
        model=config.AI_SUMMARY_MODEL,
        temperature=config.AI_SUMMARY_TEMPERATURE
    )

# ─────────────────────────────────────────────────────────
# Gemini SDK
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
# ─────────────────────────────────────────────────────────
# MLX-VLM（Apple Silicon直接推論・最速・画像対応）
# ─────────────────────────────────────────────────────────

_mlx_model = None
_mlx_processor = None
_mlx_loaded_model_name = None
_mlx_loading_lock = threading.Lock()  

def _call_mlx(prompt: str, model: str, temperature: float, image_path: str = None) -> str:
    """振り分け関数"""
    
    if not image_path:
        return _call_mlx_text(prompt, model, temperature)
    else:
        return _call_mlx_vlm(prompt, model, temperature, image_path)


def _call_mlx_text(prompt: str, model: str, temperature: float) -> str:
    """テキスト専用（ユノ用）mlx_lm使用"""
    from mlx_lm import load, generate
    from mlx_lm.sample_utils import make_sampler

    global _mlx_model, _mlx_processor, _mlx_loaded_model_name

    cache_check = try_to_load_from_cache(model, "config.json")
    if cache_check is None or cache_check is _CACHED_NO_EXIST:
        print(f"[LLM] ❌ モデル未DL: {model}")
        return "モデルがまだダウンロードされていないよ！先にdownload_model.pyを実行してね。"

    with _mlx_loading_lock:
        if _mlx_loaded_model_name != model:
            print(f"[LLM] 🍎 MLXモデルロード中: {model}")
            _mlx_model, _mlx_processor = load(model)
            _mlx_loaded_model_name = model

    messages = [{"role": "user", "content": prompt}]
    formatted = _mlx_processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    response = generate(
        _mlx_model, _mlx_processor,
        prompt=formatted,
        max_tokens=config.AI_MAX_OUTPUT_TOKENS,
        sampler=make_sampler(temperature), 
        verbose=False
    )
    return _strip_thinking(response)


def _call_mlx_vlm(prompt: str, model: str, temperature: float, image_path: str) -> str:
    """画像対応（コマ用）mlx_vlm使用・未実装"""
    # TODO: コマ用に実装予定
    from mlx_vlm import load, generate 
    raise NotImplementedError("VLM機能はコマ用に実装予定です")


def preload_mlx_model():
    """AI_PROVIDER=mlx の時、起動時にモデルをロード"""
    if config.AI_PROVIDER != "mlx":
        return
    model = config.AI_CHAT_MODEL
    if not model:
        return
    from mlx_lm import load
    global _mlx_model, _mlx_processor, _mlx_loaded_model_name
    with _mlx_loading_lock:
        if _mlx_loaded_model_name != model:
            print(f"[LLM] 🍎 起動時MLXモデルプリロード: {model}")
            _mlx_model, _mlx_processor = load(model)
            _mlx_loaded_model_name = model
            print(f"[LLM] ✅ プリロード完了: {model}")