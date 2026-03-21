# admin_routes.py
"""管理UI用 Blueprint"""

import os
import json
from pathlib import Path
from flask import Blueprint, jsonify, render_template, request

admin_bp = Blueprint("admin", __name__, template_folder="templates")

_BASE = Path(__file__).parent
_ENV_DIR = Path.home() / "env" 

# ===== ヘルパー =====

def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ===== 管理画面 =====

@admin_bp.route("/admin")
def admin_index():
    return render_template("admin/index.html")


# ===== member.json =====

@admin_bp.route("/admin/api/member", methods=["GET"])
def get_member():
    data = _read_json(_BASE / "member.json")
    if data is None:
        data = {"children": [], "family": [], "friends": []}
    return jsonify(data)

@admin_bp.route("/admin/api/member", methods=["POST"])
def save_member():
    try:
        _write_json(_BASE / "member.json", request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== reading_map.json =====

@admin_bp.route("/admin/api/reading_map", methods=["GET"])
def get_reading_map():
    data = _read_json(_BASE / "reading_map.json")
    if data is None:
        data = {}
    items = [{"word": k, "reading": v} for k, v in data.items()]
    return jsonify(items)

@admin_bp.route("/admin/api/reading_map", methods=["POST"])
def save_reading_map():
    try:
        items = request.get_json(force=True)  # [{word, reading}, ...]
        data = {item["word"]: item["reading"] for item in items if item.get("word")}
        _write_json(_BASE / "reading_map.json", data)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== announcements.json =====

@admin_bp.route("/admin/api/announcements", methods=["GET"])
def get_announcements():
    data = _read_json(_BASE / "announcements.json")
    if data is None:
        data = []
    return jsonify(data)

@admin_bp.route("/admin/api/announcements", methods=["POST"])
def save_announcements():
    try:
        _write_json(_BASE / "announcements.json", request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== andy.json =====

def _andy_json_path() -> Path | None:
    """ANDY_LOG_PATHと同じディレクトリのandy.jsonを返す"""
    log_path = os.getenv("ANDY_LOG_PATH", "")
    if not log_path:
        return None
    return Path(log_path).parent / "andy.json"

@admin_bp.route("/admin/api/andy", methods=["GET"])
def get_andy():
    path = _andy_json_path()
    if path is None or not path.exists():
        # デフォルトテンプレートを返す
        return jsonify({
            "name": "andy",
            "model": "ollama/sweaterdog/andy-4:micro-q8_0",
            "embedding": {"api": "ollama", "model": "nomic-embed-text"},
            "speak": "yuno/kokoro/am_adam"
        })
    return jsonify(_read_json(path))

@admin_bp.route("/admin/api/andy", methods=["POST"])
def save_andy():
    try:
        path = _andy_json_path()
        if path is None:
            return jsonify({"ok": False, "error": "ANDY_LOG_PATHが未設定です"}), 400
        _write_json(path, request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== .env =====

ENV_GROUPS = [
    {
        "group": "🎤 音声認識 / Whisper.cpp",
        "items": [
            {"key": "WHISPER_CLI",             "label": "Whisper CLIパス",  "type": "text"},
            {"key": "",                        "label": "",                 "type": "empty"},
            {"key": "WHISPER_MODEL",           "label": "日本語モデルパス", "type": "text"},
            {"key": "WHISPER_MODEL_EN",        "label": "英語モデルパス",   "type": "text"},
            {"key": "WHISPER_NO_SPEECH_THOLD", "label": "無音判定しきい値", "type": "number"},
            {"key": "SPEECH_MIN_BYTES",        "label": "最小音声バイト数", "type": "number"},
            {"key": "SPEECH_ALLOW_SHORT",      "label": "短文許可ワード（カンマ区切り）", "type": "text"},
            {"key": "",                        "label": "",                 "type": "empty"},
        ]
    },
    {
        "group": "🔊 音声合成 / VOICEVOX, KOKORO",
        "items": [
            {"key": "VOICEVOX_URL",        "label": "VOICEVOX URL",  "type": "text"},
            {"key": "VOICE_SERVER_URL",    "label": "音声サーバーURL", "type": "text"},
            {"key": "VOICEVOX_SPEAKER_ID", "label": "日本語音声 / VOICEBOX", "type": "datalist",
             "options": [
                "2:四国めたん（ノーマル）",
                "3:ずんだもん（ノーマル）",
                "8:春日部つむぎ（ノーマル）",
                "13:青山龍星（ノーマル）",
                "12:白上虎太郎（ノーマル）",
                "10:雨晴はう（ノーマル）",
             ]},
            {"key": "KOKORO_VOICE_YUNO",   "label": "英語音声 / KOKORO", "type": "datalist",
             "options": ["af_sarah","af_sky","af_bella","af_nicole","am_adam","am_michael"]},
            {"key": "VOICE_STORAGE_DIR",   "label": "音声ファイル保存先", "type": "text"},
            {"key": "",                    "label": "",               "type": "empty"},
        ]
    },
    {
        "group": "🌤️ 天気設定 / Open-Meteo",
        "items": [
            {"key": "WEATHER_LATITUDE",  "label": "緯度", "type": "text"},
            {"key": "WEATHER_LONGITUDE", "label": "経度", "type": "text"},
        ]
    },
    {
        "group": "🔖 記憶設定 / Basic Memory",
        "items": [
            {"key": "MEMORY_DIR",        "label": "記憶ディレクトリ",       "type": "text"},
            {"key": "ARCHIVE_DIR",       "label": "アーカイブディレクトリ", "type": "text"},
            {"key": "SUMMARY_KEEP_DAYS", "label": "要約保持日数",           "type": "number"},
        ]
    },
    {
        "group": "📱 通信設定 / LINE_Render,Discord（空欄可）",
        "items": [
            {"key": "DISCORD_BOT_TOKEN",  "label": "Discord Botトークン",  "type": "password"},
            {"key": "DISCORD_CHANNEL_ID", "label": "Discord チャンネルID", "type": "text"},
            {"key": "RENDER_URL",         "label": "Render URL",           "type": "text"},
        ]
    },
    {
        "group": "⚙️ サーバー設定",
        "items": [
            {"key": "SERVER_PORT", "label": "サーバーポート", "type": "number"},
        ]
    },
]
# ===== AI設定専用グループ =====
AI_ENV_GROUPS = [
    {
        "group": "🤖 アシスタント基本設定",
        "items": [
            {"key": "ASSISTANT_NAME",    "label": "アシスタント名", "type": "text"},
            {"key": "ASSISTANT_PERSONA", "label": "ペルソナ設定",   "type": "textarea"},
        ]
    },
    {
        "group": "🔀 AIプロバイダー設定",
        "items": [
            {"key": "AI_PROVIDER", "label": "プロバイダー", "type": "select",
             "options": [
                 "gemini:Gemini",
                 "openai:OpenAI互換（Grok / Ollama / OpenRouter）"
             ]},
            {"key": "AI_CHAT_MODEL",    "label": "会話モデル",              "type": "text"},
            {"key": "AI_SUMMARY_MODEL", "label": "要約モデル",              "type": "text"},
            {"key": "AI_SEARCH_MODEL",  "label": "検索モデル（Gemini固定）", "type": "text"},
        ]
    },
    {
        "group": "🔢 生成パラメータ",
        "items": [
            {"key": "AI_MAX_OUTPUT_TOKENS",   "label": "最大出力トークン数",                        "type": "number"},
            {"key": "AI_RECENT_TURNS",        "label": "会話記憶ターン数（推奨：10未満）",           "type": "number"},
            {"key": "AI_CHAT_TEMPERATURE",    "label": "会話 Temperature（豊かさ・デフォルト 0.8）", "type": "number"},
            {"key": "AI_SUMMARY_TEMPERATURE", "label": "要約 Temperature（正確さ・デフォルト 0.3）", "type": "number"},
            {"key": "AI_SEARCH_TEMPERATURE",  "label": "検索 Temperature（正確さ・デフォルト 0.3）", "type": "number"},
        ]
    },
    {
        "group": "🔑 APIキー",
        "items": [
            {"key": "GEMINI_API_KEY",  "label": "Gemini API キー（検索機能のため常に必須）",       "type": "password"},
            {"key": "",                      "label": "",                      "type": "empty"},
            {"key": "OPENAI_BASE_URL", "label": "OpenAI互換 Base URL",                          "type": "text"},
            {"key": "OPENAI_API_KEY",  "label": "OpenAI互換 API キー（AI_PROVIDER=openai の時）", "type": "password"},
        ]
    },
    {
        "group": "🔍 検索設定",
        "items": [
            {"key": "SEARCH_KEYWORDS", "label": "検索トリガーワード（カンマ区切り）", "type": "text"},
        ]
    },
]

# Mindcraft / アンディ専用の env 設定
ANDY_ENV_GROUPS = [
    {
        "group": "🔗 Mindcraft - YUNO 接続設定",
        "items": [
            {"key": "MINDSERVER_URL",        "label": "MindServer URL",        "type": "text"},
            {"key": "MINDCRAFT_PLAYER_NAME", "label": "Minecraftプレイヤー名", "type": "text"},
            {"key": "ANDY_LOG_PATH",         "label": "andy.logパス",          "type": "text"},
            {"key": "",                      "label": "",                      "type": "empty"},
        ]
    },
    {
        "group": "🎙️ アンディ音声・動作設定",
        "items": [
            {"key": "KOKORO_VOICE_ANDY",   "label": "アンディの声（Kokoro）", "type": "datalist",
             "options": ["am_adam","am_michael","af_sarah","af_sky","af_bella","af_nicole"]},
            {"key": "ANDY_WAIT_TIMEOUT",   "label": "待機タイムアウト（秒）", "type": "number"},
            {"key": "ANDY_KEYWORDS",       "label": "アンディ起動キーワード（カンマ区切り）", "type": "text"},
            {"key": "ANDY_OFFLINE_MESSAGE","label": "オフライン時メッセージ", "type": "text"},
        ]
    },
]

def _write_dotenv(path: Path, updates: dict[str, str]):
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f'{k}={updates[k]}')
                updated_keys.add(k)
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f'{k}={v}')
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _build_env_response(groups):
    result = []
    for group in groups:
        items = [{**item, "value": os.getenv(item["key"], "")} for item in group["items"]]
        result.append({"group": group["group"], "items": items})
    return result


@admin_bp.route("/admin/api/env", methods=["GET"])
def get_env():
    return jsonify(_build_env_response(ENV_GROUPS))

@admin_bp.route("/admin/api/env", methods=["POST"])
def save_env():
    try:
        _write_dotenv(_ENV_DIR / ".env.local", request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@admin_bp.route("/admin/api/ai_env", methods=["GET"])
def get_ai_env():
    return jsonify(_build_env_response(AI_ENV_GROUPS))

@admin_bp.route("/admin/api/ai_env", methods=["POST"])
def save_ai_env():
    try:
        _write_dotenv(_ENV_DIR / ".env.local", request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500    

@admin_bp.route("/admin/api/andy_env", methods=["GET"])
def get_andy_env():
    return jsonify(_build_env_response(ANDY_ENV_GROUPS))

@admin_bp.route("/admin/api/andy_env", methods=["POST"])
def save_andy_env():
    try:
        _write_dotenv(_ENV_DIR / ".env.local", request.get_json(force=True))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
