# voice_server/cache_manager.py
"""フレーズキャッシュ管理"""
from __future__ import annotations
import os
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

from phrases import build_all_phrases
from voice_server.tts_voicevox import generate_voicevox_wav, VOICEVOX_SPEAKER_ID
from voice_server.tts_kokoro import kokoro_tts, split_text_by_lang, KOKORO_VOICE_YUNO

_ENV_DIR = Path.home() / "env"
load_dotenv(_ENV_DIR / ".env")
load_dotenv(_ENV_DIR / ".env.local", override=True)

VOICE_STORAGE_DIR = os.getenv("VOICE_STORAGE_DIR", "/tmp/voice_gen_store")
CACHE_DIR         = os.path.join(VOICE_STORAGE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

_CACHED_PHRASES = build_all_phrases()
_STATE_PATH     = os.path.join(CACHE_DIR, "phrases_state.json")


def get_cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.wav")


def check_cache(text: str) -> dict | None:
    """キャッシュヒットしたら jsonify 用 dict を返す、なければ None"""
    for key, phrase in _CACHED_PHRASES.items():
        if text == phrase:
            cache_path = get_cache_path(key)
            if os.path.exists(cache_path):
                print(f"[CACHE] ヒット: {key}")
                with open(cache_path, "rb") as f:
                    wav_data = f.read()
                return {
                    "success": True,
                    "voice_id": f"cache_{key}",
                    "size": len(wav_data),
                    "sha256": hashlib.sha256(wav_data).hexdigest(),
                    "download_path": f"/voice/cache_{key}",
                    "settings": {"text": text, "engine": "voicevox_cache"},
                }
    return None


def _load_saved_state() -> dict:
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_state(phrases: dict) -> None:
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(phrases, f, ensure_ascii=False, indent=2)


def warmup_cache() -> None:
    """起動時にフレーズWAVを事前生成する"""
    saved   = _load_saved_state()
    current = _CACHED_PHRASES

    for key, text in current.items():
        path = get_cache_path(key)

        # フレーズ変更検知 → 古いwavを削除
        if saved.get(key) != text and os.path.exists(path):
            os.remove(path)
            print(f"[CACHE] フレーズ変更検知 → 削除: {key}")

        if not os.path.exists(path):
            print(f"[CACHE] 生成中: {key}")
            segments    = split_text_by_lang(text)
            has_english = any(lang == 'en' for lang, _ in segments)
            wav = (
                kokoro_tts(text, voice=KOKORO_VOICE_YUNO)
                if has_english
                else generate_voicevox_wav(text, VOICEVOX_SPEAKER_ID)
            )
            if wav:
                with open(path, "wb") as f:
                    f.write(wav)
                print(f"[CACHE] 保存: {key} ({'Kokoro' if has_english else 'VOICEVOX'})")

    _save_state(current)