"""
Socket.IOでMindcraftのMindServerにメッセージを送るブリッジ。
アンディがオンラインかどうかの確認も行う。
"""

import socketio
import time
from config import config


def _make_client():
    """毎回新しいクライアントを作って接続"""
    sio = socketio.SimpleClient()
    sio.connect(
        config.MINDSERVER_URL,
        wait_timeout=3,
        transports=["websocket"], 
    )
    return sio


def is_andy_online():
    """アンディがMinecraft内にいるか確認"""
    try:
        sio = _make_client()
        try:
            for _ in range(3):
                event = sio.receive(timeout=1)
                if not event:
                    continue
                event_name = event[0]
                payload = event[1] if len(event) > 1 else []
                if event_name == "agents-status":
                    return any(
                        a.get("name") == "andy" and a.get("in_game")
                        for a in (payload or [])
                    )
            return False
        finally:
            sio.disconnect()
    except Exception as e:
        print(f"[ANDY_BRIDGE] オンライン確認失敗（MindServer未起動？）: {e}")
        return False


def send_to_andy(message):
    try:
        sio = _make_client()
        try:
            sio.emit("send-message", ("andy", {"from": config.MINDCRAFT_PLAYER_NAME, "message": message}))
            time.sleep(0.5)  # ← 送信完了を待つ
            return True
        finally:
            sio.disconnect()
    except Exception as e:
        print(f"[ANDY_BRIDGE] 送信失敗: {e}")
        return False
