# services/discord_service.py
"""Discord通知サービスモジュール"""

import requests
from config import config
from services.notification_service import process_notification

# Discord API ベースURL
DISCORD_API = "https://discord.com/api/v10"

# 最後に取得したメッセージIDを記録（重複防止）
_last_message_id = None

def _init_last_message_id():
    """起動時に最新メッセージIDを取得して既読扱いにする"""
    global _last_message_id
    try:
        headers = {"Authorization": f"Bot {config.DISCORD_BOT_TOKEN}"}
        url = f"https://discord.com/api/v10/channels/{config.DISCORD_CHANNEL_ID}/messages?limit=1"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json()
            if messages:
                _last_message_id = messages[0]["id"]
                print(f"[DISCORD] 起動時スキップ: {_last_message_id}")
    except Exception as e:
        print(f"[DISCORD] 初期化エラー: {e}")
        
def poll_discord():
    """Discordチャンネルの最新メッセージを取得して通知処理する"""
    global _last_message_id

    if not config.DISCORD_BOT_TOKEN or not config.DISCORD_CHANNEL_ID:
        print("[DISCORD] Token or Channel ID が設定されていません")
        return

    headers = {
        "Authorization": f"Bot {config.DISCORD_BOT_TOKEN}"
    }

    # 最新1件だけ取得
    params = {"limit": 1}
    if _last_message_id:
        params["after"] = _last_message_id

    try:
        response = requests.get(
            f"{DISCORD_API}/channels/{config.DISCORD_CHANNEL_ID}/messages",
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()

        messages = response.json()
        if not messages:
            return  # 新しいメッセージなし

        # 新しい順に並んでいるので最初の1件を処理
        msg = messages[0]
        message_id = msg["id"]
        content    = msg["content"]
        user_id    = msg["author"]["id"]

        # Bot自身のメッセージは無視
        if msg["author"].get("bot"):
            _last_message_id = message_id
            return

        print(f"[DISCORD] 新着メッセージ: {content} (user_id={user_id})")

        process_notification(user_id, content)

        _last_message_id = message_id

    except requests.exceptions.Timeout:
        print("[DISCORD] タイムアウト")
    except requests.exceptions.ConnectionError:
        print("[DISCORD] 接続エラー")
    except Exception as e:
        print(f"[DISCORD] エラー: {e}")