# voice_server/tts_kokoro.py
"""Kokoro TTS ロジック（英語・日英分割）"""
from __future__ import annotations
import io
import re
import os
import numpy as np
import soundfile as sf
from pathlib import Path
from dotenv import load_dotenv
from kokoro import KPipeline

_ENV_DIR = Path.home() / "env"
load_dotenv(_ENV_DIR / ".env")
load_dotenv(_ENV_DIR / ".env.local", override=True)

KOKORO_VOICE_YUNO  = os.getenv("KOKORO_VOICE_YUNO", "af_sarah")
KOKORO_VOICE_ANDY  = os.getenv("KOKORO_VOICE_ANDY", "am_adam")
KOKORO_SAMPLE_RATE = 24000

_kokoro_pipeline = None


def _get_kokoro() -> KPipeline:
    """Kokoroパイプラインを取得（初回のみ初期化）"""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        print("[KOKORO] パイプライン初期化中...")
        _kokoro_pipeline = KPipeline(lang_code='a')  # 'a' = American English
        print("[KOKORO] 初期化完了")
    return _kokoro_pipeline


def kokoro_tts(text: str, voice: str | None = None) -> bytes | None:
    """Kokoroで英語テキストをWAVバイト列に変換"""
    if voice is None:
        voice = KOKORO_VOICE_YUNO
    pipeline = _get_kokoro()
    chunks = []
    for _, _, audio in pipeline(text, voice=voice):
        chunks.append(audio)
    if not chunks:
        return None
    audio_data = np.concatenate(chunks)
    buf = io.BytesIO()
    sf.write(buf, audio_data, KOKORO_SAMPLE_RATE, format='WAV', subtype='PCM_16')
    return buf.getvalue()


def split_text_by_lang(text: str) -> list[tuple[str, str]]:
    """テキストを日本語/英語セグメントに分割

    例: 「Let's go!って言ってみて！」
      → [('en', "Let's go!"), ('ja', 'って言ってみて！')]
    """
    pattern = r"([A-Za-z]+(?:[''\-][A-Za-z]+)+[A-Za-z0-9\s'\-,!?.]*|[A-Za-z]+\s+[A-Za-z0-9\s'\-,!?.]{2,}|[A-Za-z]{4,})"
    segments = []
    last_end = 0

    for match in re.finditer(pattern, text):
        if match.start() > last_end:
            ja_part = text[last_end:match.start()].strip()
            if ja_part:
                segments.append(('ja', ja_part))
        en_part = match.group().strip()
        if en_part:
            segments.append(('en', en_part))
        last_end = match.end()

    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            segments.append(('ja', remaining))

    return segments if segments else [('ja', text)]


def concat_wav_bytes(wav_list: list[bytes]) -> bytes:
    """複数のWAVバイト列を結合（サンプルレート違いも吸収）"""
    if len(wav_list) == 1:
        return wav_list[0]

    arrays = []
    base_sr = None
    for wav_bytes in wav_list:
        buf = io.BytesIO(wav_bytes)
        data, sr = sf.read(buf, dtype='float32')
        if base_sr is None:
            base_sr = sr
        elif sr != base_sr:
            new_len = int(len(data) * base_sr / sr)
            data = np.interp(
                np.linspace(0, len(data), new_len),
                np.arange(len(data)),
                data,
            )
        arrays.append(data)

    combined = np.concatenate(arrays)
    out_buf = io.BytesIO()
    sf.write(out_buf, combined, base_sr, format='WAV', subtype='PCM_16')
    return out_buf.getvalue()