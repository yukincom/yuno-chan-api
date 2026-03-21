# config.py
"""設定管理モジュール"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

_ENV_DIR = Path.home() / "env" 

load_dotenv(_ENV_DIR / ".env")
load_dotenv(_ENV_DIR / ".env.local", override=True) 

class Config:
    """アプリケーション設定"""
    # AI モデル設定
    AI_PROVIDER      = os.getenv("AI_PROVIDER", "gemini")

    AI_CHAT_MODEL    = os.getenv("AI_CHAT_MODEL", "gemini-2.5-flash")
    AI_SUMMARY_MODEL = os.getenv("AI_SUMMARY_MODEL", "gemini-2.5-flash")
    AI_SEARCH_MODEL  = os.getenv("AI_SEARCH_MODEL",  "gemini-2.5-flash")  # 検索（Gemini固定）

    SEARCH_KEYWORDS = os.getenv("SEARCH_KEYWORDS", "調べて,しらべて,調査して,ちょうさして,サーチして,さーちして,ぐぐって,ググって").split(",")
    SPEECH_ALLOW_SHORT = os.getenv("SPEECH_ALLOW_SHORT", "はーい,いや,やだ,だめ,ねえ").split(",")

    # AI出力設定
    AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "1200"))
    AI_RECENT_TURNS              = int(os.getenv("AI_RECENT_TURNS", "5"))
    
    # 用途別temperature
    AI_CHAT_TEMPERATURE    = float(os.getenv("AI_CHAT_TEMPERATURE",    "0.8"))  # 会話：豊か目に
    AI_SUMMARY_TEMPERATURE = float(os.getenv("AI_SUMMARY_TEMPERATURE", "0.3"))  # 要約：正確に
    AI_SEARCH_TEMPERATURE  = float(os.getenv("AI_SEARCH_TEMPERATURE",  "0.3"))  # 検索：正確に

    # M5Stack
    M5STACK_IP   = os.getenv("M5STACK_IP",   "192.168.1.49")
    M5STACK_PORT = int(os.getenv("M5STACK_PORT", "80"))
    M5STACK_URL = os.getenv("M5STACK_URL", "http://192.168.1.49")
    M5STACK_TIMEOUT = int(os.getenv("M5STACK_TIMEOUT", "5"))


    # Whisper.cpp settings
    WHISPER_CLI   = os.getenv("WHISPER_CLI", "")
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "")
    WHISPER_NO_SPEECH_THOLD = float(os.getenv("WHISPER_NO_SPEECH_THOLD", "0.6"))
    WHISPER_MODEL_EN = os.getenv("WHISPER_MODEL_EN", "")

    # Voice Server settings(VOICE VOX)
    VOICE_SERVER_URL = os.getenv("VOICE_SERVER_URL", "")
    VOICE_REQUEST_TIMEOUT = int(os.getenv("VOICE_REQUEST_TIMEOUT", "30"))

    # VOICEVOX settings
    VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021")
    VOICEVOX_SPEAKER_ID = int(os.getenv("VOICEVOX_SPEAKER_ID", "2"))

    # 音声の最小バイト数（マジックナンバー）
    SPEECH_MIN_BYTES = int(os.getenv("SPEECH_MIN_BYTES", "10000"))

    # Render settings
    POLL_INTERVAL = 60
    RENDER_URL = os.getenv("RENDER_URL", "")

    #SERVER setting
    SERVER_PORT = int(os.getenv("SERVER_PORT", "5000"))

    # パーソナル設定
    ASSISTANT_NAME   = os.getenv("ASSISTANT_NAME", "")
    FAMILY_DEFAULT   = os.getenv("FAMILY_DEFAULT", "")
    ASSISTANT_PERSONA = os.getenv(
        "ASSISTANT_PERSONA",
        ""
    )

    # 通知サービス設定
    NOTIFICATION_SERVICE = os.getenv("NOTIFICATION_SERVICE", "line")
    # Discord 設定
    DISCORD_BOT_TOKEN    = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_CHANNEL_ID   = os.getenv("DISCORD_CHANNEL_ID", "")

    # Memory settings（basic-memory）
    MEMORY_DIR = os.getenv("MEMORY_DIR", "")
    ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "")
    SUMMARY_KEEP_DAYS = int(os.getenv("SUMMARY_KEEP_DAYS", "14"))
    # 天気設定
    WEATHER_LATITUDE  = os.getenv("WEATHER_LATITUDE",  "")
    WEATHER_LONGITUDE = os.getenv("WEATHER_LONGITUDE", "")
    WEATHER_KEYWORDS_TODAY    = os.getenv("WEATHER_KEYWORDS_TODAY",    "今日の天気,きょうのてんき").split(",")
    WEATHER_KEYWORDS_TOMORROW = os.getenv("WEATHER_KEYWORDS_TOMORROW", "明日の天気,あしたのてんき").split(",")
    WEATHER_MORNING_HOUR   = int(os.getenv("WEATHER_MORNING_HOUR",   "6"))
    WEATHER_MORNING_MINUTE = int(os.getenv("WEATHER_MORNING_MINUTE", "30"))
    WEATHER_NOON_HOUR      = int(os.getenv("WEATHER_NOON_HOUR",      "12"))
    WEATHER_NOON_MINUTE    = int(os.getenv("WEATHER_NOON_MINUTE",    "0"))
     # アナウンス設定（announcements.jsonから読み込み）
    _announcements_path = Path(os.getenv("ANNOUNCEMENTS_FILE", str(Path(__file__).parent / "announcements.json")))
    ANNOUNCEMENTS = json.loads(_announcements_path.read_text(encoding="utf-8")) \
        if _announcements_path.exists() else []

    # 歌機能
    SONG_TRIGGER = os.getenv("SONG_TRIGGER", "歌って,うたって,歌ってください").split(",")

    SONG_MAP = {}
    for item in os.getenv("SONG_MAP", "").split(","):
        if ":" in item:
            keys, filename = item.rsplit(":", 1)
            for key in keys.split("|"):
                SONG_MAP[key.strip()] = filename.strip()

    # Andy / 英語判定キーワード
    ANDY_KEYWORDS = os.getenv("ANDY_KEYWORDS", "アンディ,andy,Andy").split(",")
    ENGLISH_TRANSLATE_KEYWORDS = ["英語で", "英語に"]
    ANDY_WAIT_TIMEOUT          = int(os.getenv("ANDY_WAIT_TIMEOUT", "30"))
    MINDSERVER_URL             = os.getenv("MINDSERVER_URL", "http://localhost:8080")
    ANDY_OFFLINE_MESSAGE       = os.getenv("ANDY_OFFLINE_MESSAGE", "アンディは今、休憩中みたいだよ！またあとで話しかけてみよう！")                
    MINDCRAFT_PLAYER_NAME      = os.getenv("MINDCRAFT_PLAYER_NAME", "")
    ANDY_LOG_PATH              = os.getenv("ANDY_LOG_PATH", str(Path.home() / "AI_assistant/mindcraft/andy.log"))
    KOKORO_VOICE_ANDY          = os.getenv("KOKORO_VOICE_ANDY", "am_adam")
    
# インスタンス
config = Config()