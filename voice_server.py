# voice_server.py
from __future__ import annotations

import hashlib
import re
import io
import os
import time
import uuid
import json

from pathlib import Path
from dotenv import load_dotenv
import requests
import numpy as np
import soundfile as sf

from flask import Flask, jsonify, request, send_file
from kokoro import KPipeline

from phrases import build_all_phrases

_BASE = Path(__file__).parent
_ENV_DIR = Path.home() / "env"
load_dotenv(_ENV_DIR / ".env")
load_dotenv(_ENV_DIR / ".env.local", override=True)

app = Flask(__name__)

# 辞書
READING_MAP = json.loads((_BASE / "reading_map.json").read_text(encoding="utf-8"))

# VOICEVOX設定
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021")
VOICEVOX_SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "2"))  # 四国めたん ノーマル

# 音声ファイル保存先
VOICE_STORAGE_DIR = os.getenv("VOICE_STORAGE_DIR", "/tmp/voice_gen_store")
os.makedirs(VOICE_STORAGE_DIR, exist_ok=True)

# songs ディレクトリの設定
SONGS_DIR = os.path.join(os.path.dirname(__file__), "songs")


# Kokoro設定
KOKORO_VOICE_YUNO  = os.getenv("KOKORO_VOICE_YUNO",  "af_sarah")  # ユノの英語声
KOKORO_VOICE_ANDY  = os.getenv("KOKORO_VOICE_ANDY",  "am_adam")   # アンディ用（将来）
KOKORO_SAMPLE_RATE = 24000

# Kokoroパイプライン（遅延初期化）
_kokoro_pipeline = None

CACHE_DIR = os.path.join(VOICE_STORAGE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
_CACHED_PHRASES = build_all_phrases() 

def _get_cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.wav")

def _check_cache(text: str) -> dict | None:
    """キャッシュヒットしたらjsonify用dictを返す、なければNone"""
    for key, phrase in _CACHED_PHRASES.items():
        if text == phrase:
            cache_path = _get_cache_path(key)
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

_STATE_PATH = os.path.join(CACHE_DIR, "phrases_state.json")

def _load_saved_state() -> dict:
    """前回起動時のフレーズ内容を読み込む"""
    if os.path.exists(_STATE_PATH):
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_state(phrases: dict):
    """現在のフレーズ内容を保存"""
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(phrases, f, ensure_ascii=False, indent=2)

def warmup_cache():
    saved = _load_saved_state()
    current = _CACHED_PHRASES

    for key, text in current.items():
        path = _get_cache_path(key)
        # フレーズが変わっていたら古いwavを削除
        if saved.get(key) != text and os.path.exists(path):
            os.remove(path)
            print(f"[CACHE] フレーズ変更検知 → 削除: {key}")

        # wavがなければ生成（新規 or 変更後）
        if not os.path.exists(path):
            print(f"[CACHE] 生成中: {key}")
            segments = _split_text_by_lang(text)
            has_english = any(lang == 'en' for lang, _ in segments)
            if has_english:
                wav = _kokoro_tts(text, voice=KOKORO_VOICE_YUNO)
            else:
                wav = generate_voicevox_wav(text, VOICEVOX_SPEAKER_ID)
            if wav:
                with open(path, "wb") as f:
                    f.write(wav)
                print(f"[CACHE] 保存: {key} ({'Kokoro' if has_english else 'VOICEVOX'})")

    # 現在の状態を保存（次回比較用）
    _save_state(current)

def _get_kokoro():
    """Kokoroパイプラインを取得（初回のみ初期化）"""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        print("[KOKORO] パイプライン初期化中...")
        _kokoro_pipeline = KPipeline(lang_code='a')  # 'a' = American English
        print("[KOKORO] 初期化完了")
    return _kokoro_pipeline

def _kokoro_tts(text, voice=None):
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

def _split_text_by_lang(text):
    """テキストを日本語/英語セグメントに分割
    
    例: 「Let's go!って言ってみて！」
      → [('en', "Let's go!"), ('ja', 'って言ってみて！')]
    """
    # 英語部分：アルファベット・スペース・基本的な記号
    pattern = r"([A-Za-z]+(?:[''\-][A-Za-z]+)+[A-Za-z0-9\s'\-,!?.]*|[A-Za-z]+\s+[A-Za-z0-9\s'\-,!?.]{2,}|[A-Za-z]{4,})"
    
    segments = []
    last_end = 0


    for match in re.finditer(pattern, text):
        # 英語の前の日本語部分
        if match.start() > last_end:
            ja_part = text[last_end:match.start()].strip()
            if ja_part:
                segments.append(('ja', ja_part))
        # 英語部分
        en_part = match.group().strip()
        if en_part:
            segments.append(('en', en_part))
        last_end = match.end()

    # 末尾の日本語
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            segments.append(('ja', remaining))

    return segments if segments else [('ja', text)]

def _concat_wav_bytes(wav_list):
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
            # 線形補間でリサンプル（scipy不要）
            new_len = int(len(data) * base_sr / sr)
            data = np.interp(
                np.linspace(0, len(data), new_len),
                np.arange(len(data)),
                data
            )
        arrays.append(data)

    combined = np.concatenate(arrays)
    out_buf = io.BytesIO()
    sf.write(out_buf, combined, base_sr, format='WAV', subtype='PCM_16')
    return out_buf.getvalue()


def generate_voicevox_wav(text, speaker_id=None):
    """VOICEVOXでテキストをWAVに変換する。

    Args:
        text: 読み上げるテキスト
        speaker_id: 話者ID（Noneの場合はデフォルト使用）

    Returns:
        bytes: WAVデータ、失敗時はNone
    """
    sid = speaker_id if speaker_id is not None else VOICEVOX_SPEAKER_ID

    # Step 1: audio_query生成
    print(f"[1/2] audio_query生成中... speaker={sid}")
    query_response = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": sid},
        timeout=10,
    )
    query_response.raise_for_status()
    audio_query = query_response.json()

    # 音声パラメータをログ出力
    print(f"  outputSamplingRate: {audio_query.get('outputSamplingRate')} Hz")

    # Step 2: WAV合成
    print(f"[2/2] WAV合成中...")
    synthesis_response = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": sid},
        json=audio_query,
        timeout=30,
    )
    synthesis_response.raise_for_status()
    return synthesis_response.content


@app.route("/health", methods=["GET"])
def health():
    """ヘルスチェック"""
    # VOICEVOXの死活確認も合わせて行う
    try:
        r = requests.get(f"{VOICEVOX_URL}/version", timeout=3)
        voicevox_ok = r.status_code == 200
        voicevox_version = r.text.strip('"') if voicevox_ok else "unreachable"
    except Exception:
        voicevox_ok = False
        voicevox_version = "unreachable"

    return jsonify({
        "status": "ok",
        "service": "voice_generator_voicevox",
        "storage": VOICE_STORAGE_DIR,
        "voicevox_url": VOICEVOX_URL,
        "voicevox_status": "ok" if voicevox_ok else "error",
        "voicevox_version": voicevox_version,
        "speaker_id": VOICEVOX_SPEAKER_ID,
    })

def normalize_text(text: str) -> str:
    """VOICEVOXに渡す前にテキストを正規化"""
    for word, reading in READING_MAP.items():
        text = text.replace(word, reading)
    return text

@app.route("/generate", methods=["POST"])
def generate():
    """音声生成エンドポイント"""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "").strip()
        speaker_id = int(data.get("speaker_id", VOICEVOX_SPEAKER_ID))

        if not text:
            return jsonify({"success": False, "error": "text is required"}), 400
        cached = _check_cache(text)
        if cached:
            return jsonify(cached)

        # ── キャッシュミス → 通常合成
        def clip_at_sentence(text, max_chars=500):
            if len(text) <= max_chars:
                return text
            for i in range(max_chars, 0, -1):
                if text[i] in ['。', '！', '？', '!', '?']:
                    return text[:i+1]
            return text[:max_chars]

        clipped = clip_at_sentence(text, 500)
        clipped = normalize_text(clipped)

        print(f"\n{'='*60}")
        print(f"[VOICE] 音声生成開始 (VOICEVOX)")
        print(f"  text({len(clipped)}文字): {clipped}")
        print(f"  speaker_id: {speaker_id}")

        voice_id = f"{int(time.time())}_{uuid.uuid4().hex}"
        final_wav = os.path.join(VOICE_STORAGE_DIR, f"{voice_id}.wav")

        wav_data = generate_voicevox_wav(clipped, speaker_id)
        if not wav_data:
            return jsonify({"success": False, "error": "VOICEVOX synthesis failed"}), 500

        sha256_hash = hashlib.sha256(wav_data).hexdigest()
        with open(final_wav, "wb") as f:
            f.write(wav_data)

        file_size = len(wav_data)
        print(f"[完了] voice_id: {voice_id}")
        print(f"  size: {file_size:,} bytes")
        print(f"  sha256: {sha256_hash[:16]}...")
        print(f"{'='*60}\n")

        return jsonify({
            "success": True,
            "voice_id": voice_id,
            "size": file_size,
            "sha256": sha256_hash,
            "download_path": f"/voice/{voice_id}",
            "settings": {
                "text": clipped,
                "speaker_id": speaker_id,
                "engine": "voicevox",
            },
        })

    except requests.exceptions.ConnectionError:
        print(f"[VOICE] ❌ VOICEVOXに接続できません: {VOICEVOX_URL}")
        return jsonify({"success": False, "error": f"VOICEVOX unreachable: {VOICEVOX_URL}"}), 503

    except Exception as e:
        print(f"[VOICE] ❌ error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/voice/<voice_id>", methods=["GET"])
def get_voice(voice_id):
    """生成済み音声ファイルを返す"""
    # キャッシュファイルを先にチェック
    cache_path = os.path.join(CACHE_DIR, f"{voice_id.replace('cache_', '')}.wav")
    if voice_id.startswith("cache_") and os.path.exists(cache_path):
        return send_file(cache_path, mimetype="audio/wav", as_attachment=True, download_name="voice.wav")
    
    wav_path = os.path.join(VOICE_STORAGE_DIR, f"{voice_id}.wav")
    if not os.path.exists(wav_path):
        return jsonify({"success": False, "error": "voice not found"}), 404

    print(f"[📤] 音声配信: {voice_id}")
    return send_file(wav_path, mimetype="audio/wav", as_attachment=True, download_name="voice.wav")


@app.route("/speakers", methods=["GET"])
def list_speakers():
    """VOICEVOXの話者一覧を返す"""
    try:
        r = requests.get(f"{VOICEVOX_URL}/speakers", timeout=5)
        r.raise_for_status()
        return jsonify({"success": True, "speakers": r.json()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/song/<song_name>", methods=["GET"])
def get_song(song_name):
    """曲ファイルを返す"""
    wav_path = os.path.join(SONGS_DIR, f"{song_name}.wav")
    if not os.path.exists(wav_path):
        return jsonify({"success": False, "error": "song not found"}), 404
    print(f"[🎵] 曲配信: {song_name}")
    return send_file(wav_path, mimetype="audio/wav", as_attachment=True, download_name=f"{song_name}.wav")

@app.route("/cleanup", methods=["POST"])
def cleanup():
    """古い音声ファイルを削除する"""
    payload = request.get_json(silent=True) or {}
    max_age_seconds = int(payload.get("max_age_seconds", 3600))
    keep_latest = bool(payload.get("keep_latest", True))

    files = []
    for filename in os.listdir(VOICE_STORAGE_DIR):
        if filename.endswith(".wav"):
            path = os.path.join(VOICE_STORAGE_DIR, filename)
            files.append((path, os.path.getmtime(path)))

    files.sort(key=lambda x: x[1], reverse=True)
    now = time.time()
    deleted = 0

    for idx, (path, mtime) in enumerate(files):
        if keep_latest and idx == 0:
            continue
        if now - mtime > max_age_seconds:
            os.remove(path)
            deleted += 1

    if deleted > 0:
        print(f"[🗑️] クリーンアップ: {deleted}件削除")
    return jsonify({"success": True, "deleted": deleted})


@app.route("/generate_en", methods=["POST"])
def generate_en():
    """英語TTS（Kokoro）エンドポイント
    
    リクエスト: {"text": "Hello!", "voice": "af_sarah"}
    """
    try:
        data       = request.get_json(silent=True) or {}
        text       = data.get("text", "").strip()
        voice      = data.get("voice", KOKORO_VOICE_YUNO)

        if not text:
            return jsonify({"success": False, "error": "text is required"}), 400

        clipped = text[:300]
        print(f"\n[KOKORO] 英語TTS開始: {clipped[:50]} (voice={voice})")

        wav_data = _kokoro_tts(clipped, voice=voice)
        if not wav_data:
            return jsonify({"success": False, "error": "Kokoro synthesis failed"}), 500

        voice_id  = f"en_{int(time.time())}_{uuid.uuid4().hex}"
        wav_path  = os.path.join(VOICE_STORAGE_DIR, f"{voice_id}.wav")
        sha256    = hashlib.sha256(wav_data).hexdigest()

        with open(wav_path, "wb") as f:
            f.write(wav_data)

        print(f"[KOKORO] 完了: {voice_id} ({len(wav_data):,} bytes)")

        return jsonify({
            "success":       True,
            "voice_id":      voice_id,
            "size":          len(wav_data),
            "sha256":        sha256,
            "download_path": f"/voice/{voice_id}",
            "settings": {
                "text":   clipped,
                "voice":  voice,
                "engine": "kokoro",
            },
        })

    except Exception as e:
        print(f"[KOKORO] ❌ error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/generate_mixed", methods=["POST"])
def generate_mixed():
    """日英混合TTS（VOICEVOX + Kokoro）エンドポイント
    
    日本語部分はVOICEVOX、英語部分はKokoroで生成してWAVを結合。
    英語が含まれない場合はVOICEVOXのみで生成。
    
    リクエスト: {"text": "Let's go!って言ってみよう！", "speaker_id": 2, "voice": "af_sarah"}
    """
    try:
        data       = request.get_json(silent=True) or {}
        text       = data.get("text", "").strip()
        speaker_id = int(data.get("speaker_id", VOICEVOX_SPEAKER_ID))
        voice      = data.get("voice", KOKORO_VOICE_YUNO)

        if not text:
            return jsonify({"success": False, "error": "text is required"}), 400
        cached = _check_cache(text)
        if cached:
            return jsonify(cached)

        clipped  = text[:300]
        segments = _split_text_by_lang(clipped)

        # 英語セグメントがなければ通常のVOICEVOXに流す
        has_english = any(lang == 'en' for lang, _ in segments)
        if not has_english:
            print(f"[MIXED] 英語なし → VOICEVOXのみで処理")
            wav_data = generate_voicevox_wav(clipped, speaker_id)
        else:
            print(f"[MIXED] 日英混合TTS開始: {len(segments)}セグメント")
            wav_parts = []
            for lang, seg_text in segments:
                print(f"  [{lang}] {seg_text[:40]}")
                if lang == 'ja':
                    wav = generate_voicevox_wav(seg_text, speaker_id)
                else:
                    wav = _kokoro_tts(seg_text, voice=voice)
                if wav:
                    wav_parts.append(wav)

            if not wav_parts:
                return jsonify({"success": False, "error": "All synthesis failed"}), 500

            wav_data = _concat_wav_bytes(wav_parts)

        if not wav_data:
            return jsonify({"success": False, "error": "Synthesis failed"}), 500

        voice_id = f"mix_{int(time.time())}_{uuid.uuid4().hex}"
        wav_path = os.path.join(VOICE_STORAGE_DIR, f"{voice_id}.wav")
        sha256   = hashlib.sha256(wav_data).hexdigest()

        with open(wav_path, "wb") as f:
            f.write(wav_data)

        print(f"[MIXED] 完了: {voice_id} ({len(wav_data):,} bytes)")

        return jsonify({
            "success":       True,
            "voice_id":      voice_id,
            "size":          len(wav_data),
            "sha256":        sha256,
            "download_path": f"/voice/{voice_id}",
            "settings": {
                "text":   clipped,
                "engine": "mixed" if has_english else "voicevox",
            },
        })

    except Exception as e:
        print(f"[MIXED] ❌ error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

warmup_cache()

if __name__ == "__main__":
    print("=" * 50)
    print("🎤 音声生成サーバー (VOICEVOX版)")
    print("=" * 50)
    print(f"📁 ストレージ: {VOICE_STORAGE_DIR}")
    print(f"🎵 VOICEVOX: {VOICEVOX_URL}")
    print(f"🎭 話者ID: {VOICEVOX_SPEAKER_ID}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5001, debug=False)