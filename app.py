# app.py
"""Flaskアプリケーション"""


import traceback
from datetime import datetime

import requests
from flask import Flask, Response, jsonify, request

from init_files import ensure_default_files
from config import config
from ai_handler import is_english_mode
from member_loader import get_family_call_map, get_primary_child, has_line_users, has_discord_users
from services.chat_service import process_chat, detect_speaker
from services.discord_service import _init_last_message_id
from services.scheduler_service import setup_scheduler, start_scheduler, stop_scheduler
from services.batch_service import run_if_needed
from services.speech_service import speech_service
from services.andy_voice import andy_watcher
from admin_routes import admin_bp
from mobile_routes import mobile_bp


app = Flask(__name__)
app.register_blueprint(admin_bp)
app.register_blueprint(mobile_bp)
ensure_default_files()

def check_notification_config():
    """通知サービスの設定確認（起動時のみ）"""
    line_ok    = has_line_users()
    discord_ok = has_discord_users()

    if not line_ok and not discord_ok:
        print("[NOTIFY] ⚠️ LINE・Discord ともにユーザーIDが未設定です")
        print("[NOTIFY] 通知機能はオフで起動します（会話機能は使えます）")
        return False

    if line_ok:
        print("[NOTIFY] ✅ LINE通知: 有効")
    else:
        print("[NOTIFY] LINE通知: ユーザーID未設定のためオフ")

    if discord_ok:
        print("[NOTIFY] ✅ Discord通知: 有効")
    else:
        print("[NOTIFY] Discord通知: ユーザーID未設定のためオフ")

    return True

# スケジューラー開始（インポート時に自動開始）
run_if_needed()
if config.DISCORD_BOT_TOKEN:
    _init_last_message_id()
notification_enabled = check_notification_config()  
setup_scheduler(notification_enabled)               
start_scheduler()
andy_watcher.start() 

@app.route("/health", methods=["GET"])
def health_check():
    """ヘルスチェック"""
    return jsonify({
        "status": "ok",
        "version": "2.3",
        "memory": "local",
        "voice_server": config.VOICE_SERVER_URL,
    })

@app.route("/time", methods=["GET"])
def get_server_time():
    """M5Stack起動時のserverHour同期用"""
    return jsonify({"server_hour": datetime.now().hour})

@app.route("/chat", methods=["POST"])
def chat():
    """チャットエンドポイント"""
    try:
        data = request.json
        user_text = data["text"]
        generate_voice_flag = data.get("generate_voice", False)

        # ★ テキストで話者判定
        speaker = detect_speaker(user_text)

        # ★ 表示用ラベルを設定
        _call_map = get_family_call_map()   # {"family1": "お母さん", ...}
        _child_name = get_primary_child() 
        label_map = {**_call_map, "other": "その他", "child": _child_name}
        speaker_label = label_map.get(speaker, _child_name)
        print(f"[SPEAKER]{speaker}")

        result = process_chat(user_text, speaker, generate_voice_flag, speaker_label=speaker_label)

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/notify/pending", methods=["GET"])
def get_pending_notifications():
    """M5Stackからの時刻同期用（push型移行後はserverHourのみ返す）"""
    return jsonify({
        "success": True,
        "notification": None,
        "server_hour": datetime.now().hour,
    })

@app.route("/voice/<voice_id>", methods=["GET"])
def get_voice_by_id(voice_id):
    """特定のvoice_idを取得（プロキシ）"""
    try:
        voice_url = f"{config.VOICE_SERVER_URL}/voice/{voice_id}"
        remote_response = requests.get(voice_url, timeout=30)

        if remote_response.status_code != 200:
            return jsonify({"success": False, "status": "not_found"}), 404

        return Response(
            remote_response.content,
            mimetype="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=voice.wav",
                "X-Voice-Id": voice_id,
            },
        )
    except requests.RequestException:
        return jsonify({"success": False, "status": "upstream_unreachable"}), 502


@app.route("/speech/transcribe", methods=["POST"])
def transcribe_speech():
    # 音声認識エンドポイント

    try:
        # リクエストボディから音声データを取得
        audio_content = request.data
        
        if not audio_content or len(audio_content) < config.SPEECH_MIN_BYTES:
            return jsonify({"success": False, "error": "Audio too short"}), 400
        
        # 英語モデル切り替え
        use_english = is_english_mode()
        transcript = speech_service.transcribe(
            audio_content,
            use_english_model=use_english
        )
        
        if not transcript:
            return jsonify({"success": False, "error": "No speech detected"}), 400
        return jsonify({"success": True, "transcript": transcript})
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
    finally:
        # アプリケーション終了時にスケジューラーを停止
        stop_scheduler()
        andy_watcher.stop() 