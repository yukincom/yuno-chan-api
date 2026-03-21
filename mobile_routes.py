# mobile_routes.py
"""モバイルアプリ向け API エンドポイント"""

from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

from config import config
from services.voice_service import generate_voice
from memory_manager import RobotMemory

mobile_bp = Blueprint("mobile", __name__)

# M5Stack の URL をまとめるヘルパー（config に M5STACK_URL がないため）
def _m5stack_url(path: str) -> str:
    return f"http://{config.M5STACK_IP}:{config.M5STACK_PORT}{path}"

M5STACK_TIMEOUT = 5  # 秒（config に項目なし）


# ─────────────────────────────────────────────
# ① Mac サーバー ヘルスチェック
# ─────────────────────────────────────────────

@mobile_bp.route("/api/mobile/health", methods=["GET"])
def mobile_health():
    return jsonify({
        "ok": True,
        "server": "yuno-chan-api",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
    })


# ─────────────────────────────────────────────
# ② M5Stack 疎通確認
# ─────────────────────────────────────────────

@mobile_bp.route("/api/mobile/m5stack/status", methods=["GET"])
def m5stack_status():
    """M5Stack の疎通確認（/audio/status を叩く）"""
    try:
        resp = requests.get(
            _m5stack_url("/audio/status"),
            timeout=M5STACK_TIMEOUT,
        )
        data = resp.json()
        return jsonify({
            "ok": True,
            "reachable": True,
            "m5stack_ip": config.M5STACK_IP,
            "ready": data.get("ready", False),
            "mode": data.get("mode", "unknown"),
            "checked_at": datetime.now().isoformat(),
        })
    except requests.exceptions.ConnectionError:
        return jsonify({
            "ok": True,
            "reachable": False,
            "m5stack_ip": config.M5STACK_IP,
            "error": "M5Stack に接続できません",
            "checked_at": datetime.now().isoformat(),
        })
    except requests.exceptions.Timeout:
        return jsonify({
            "ok": True,
            "reachable": False,
            "m5stack_ip": config.M5STACK_IP,
            "error": "タイムアウト",
            "checked_at": datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# ③ 外出先ログを today.md に追記（1件）
# ─────────────────────────────────────────────

@mobile_bp.route("/api/mobile/logs/append", methods=["POST"])
def append_log():
    """外出先の1件ログを today.md に追記する

    リクエスト:
      {"text": "公園に行った", "timestamp": "2026-03-20T09:00:00"}
      ※ timestamp は省略可（省略時はサーバー時刻）
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text は必須です"}), 400

    ts_str = data.get("timestamp")
    try:
        ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
    except ValueError:
        ts = datetime.now()

    label = ts.strftime("%Y-%m-%d %H:%M")

    try:
        memory = RobotMemory()
        memory.add_conversation(
            speaker="mobile",
            user_text=text,
            ai_response="",
            speaker_label=f"[外出メモ] {label}",
        )
        return jsonify({"ok": True, "appended_at": label, "text": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# ④ 外出先ログをまとめて同期
# ─────────────────────────────────────────────

@mobile_bp.route("/api/mobile/logs/sync", methods=["POST"])
def sync_logs():
    """外出先ログを一括で today.md に追記する

    リクエスト:
      {"logs": [{"text": "...", "timestamp": "2026-03-20T09:00:00"}, ...]}
    レスポンス:
      {"ok": true, "synced": 2, "failed": 0, "results": [...]}
    """
    data = request.get_json(silent=True) or {}
    logs = data.get("logs", [])
    if not logs:
        return jsonify({"ok": False, "error": "logs は空にできません"}), 400

    memory = RobotMemory()
    results = []
    synced = 0
    failed = 0

    for entry in logs:
        text = (entry.get("text") or "").strip()
        if not text:
            results.append({"text": text, "ok": False, "error": "text が空"})
            failed += 1
            continue

        ts_str = entry.get("timestamp")
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
        except ValueError:
            ts = datetime.now()

        label = ts.strftime("%Y-%m-%d %H:%M")

        try:
            memory.add_conversation(
                speaker="mobile",
                user_text=text,
                ai_response="",
                speaker_label=f"[外出メモ] {label}",
            )
            results.append({"text": text, "ok": True, "appended_at": label})
            synced += 1
        except Exception as e:
            results.append({"text": text, "ok": False, "error": str(e)})
            failed += 1

    return jsonify({"ok": failed == 0, "synced": synced, "failed": failed, "results": results})


# ─────────────────────────────────────────────
# ⑤ TTS 疎通テスト
# ─────────────────────────────────────────────

@mobile_bp.route("/api/mobile/voice/test", methods=["POST"])
def voice_test():
    """TTS の疎通テスト。短文を合成して voice_url を返す。

    リクエスト: {"text": "テスト"}（省略時はデフォルト文）
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "ユノです！テスト中だよ！").strip()[:50]

    try:
        result = generate_voice(text)
        if not result:
            return jsonify({"ok": False, "error": "音声生成に失敗しました"}), 500

        return jsonify({
            "ok": True,
            "voice_id": result["voice_id"],
            "voice_url": result["source_url"],
            "size": result["size"],
            "text": text,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500