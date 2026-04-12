# voice_server/tts_voicevox.py
"""VOICEVOX TTS ロジック"""
from __future__ import annotations
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

_ENV_DIR = Path.home() / "env"
load_dotenv(_ENV_DIR / ".env")
load_dotenv(_ENV_DIR / ".env.local", override=True)

# voice_server/ の親 = AI_assistant/ ルート
_BASE = Path(__file__).parent.parent

VOICEVOX_URL             = os.getenv("VOICEVOX_URL", "http://localhost:50021")
VOICEVOX_SPEAKER_ID      = int(os.getenv("VOICEVOX_SPEAKER_ID", "2"))
VOICEVOX_SPEAKER_KOMA_ID = int(os.getenv("VOICEVOX_SPEAKER_KOMA_ID", "13"))

READING_MAP = json.loads((_BASE / "reading_map.json").read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    """VOICEVOXに渡す前にテキストを正規化"""
    for word, reading in READING_MAP.items():
        text = text.replace(word, reading)
    return text


def generate_voicevox_wav(text: str, speaker_id: int | None = None) -> bytes | None:
    """VOICEVOXでテキストをWAVに変換する"""
    sid = speaker_id if speaker_id is not None else VOICEVOX_SPEAKER_ID

    print(f"[1/2] audio_query生成中... speaker={sid}")
    query_response = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": sid},
        timeout=10,
    )
    query_response.raise_for_status()
    audio_query = query_response.json()
    print(f"  outputSamplingRate: {audio_query.get('outputSamplingRate')} Hz")

    print("[2/2] WAV合成中...")
    synthesis_response = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": sid},
        json=audio_query,
        timeout=30,
    )
    synthesis_response.raise_for_status()
    return synthesis_response.content