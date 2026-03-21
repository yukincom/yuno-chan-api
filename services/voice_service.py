# services/voice_service.py
"""音声生成サービスモジュール"""
import threading
import time

import requests
from config import config


def generate_voice(text, **kwargs):
    """voice_server.py の /generate を呼ぶ。

    Args:
        text: 音声生成するテキスト
        **kwargs: speaker_idなど（省略時はvoice_server側のデフォルト使用）

    Returns:
        dict: {
            "voice_id": str,
            "source_url": str,
            "size": int,
            "sha256": str,
            "settings": dict
        } または 失敗時はNone
    """
    try:
        payload = {"text": text}
        # speaker_idが指定された場合のみ追加
        if "speaker_id" in kwargs:
            payload["speaker_id"] = kwargs["speaker_id"]

        response = requests.post(
            f"{config.VOICE_SERVER_URL}/generate",
            json=payload,
            timeout=config.VOICE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("success"):
            print(f"❌ voice_server generation failed: {result.get('error')}")
            return None

        voice_id = result["voice_id"]
        download_path = result.get("download_path", f"/voice/{voice_id}")
        source_url = f"{config.VOICE_SERVER_URL}{download_path}"

        return {
            "voice_id": voice_id,
            "source_url": source_url,
            "size": result["size"],
            "sha256": result["sha256"],
            "settings": result["settings"],
        }
    except requests.exceptions.Timeout:
        print(f"❌ timeout: voice_server({config.VOICE_SERVER_URL})")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ connection error: voice_server({config.VOICE_SERVER_URL})")
        return None
    except Exception as e:
        print(f"❌ generate_voice error: {e}")
        return None


def generate_voice_mixed(text, speaker_id=None, voice=None):
    """日英混合音声生成（/generate_mixed を呼ぶ）
    
    日本語はVOICEVOX、英語はKokoro(af_sarah)で生成・結合。
    
    Args:
        text:       読み上げるテキスト（日英混在OK）
        speaker_id: VOICEVOXの話者ID（省略時はサーバーデフォルト）
        voice:      Kokoroの声（省略時はaf_sarah）
    
    Returns:
        generate_voice() と同じ形式の dict または None
    """
    try:
        payload = {"text": text}
        if speaker_id is not None:
            payload["speaker_id"] = speaker_id
        if voice is not None:
            payload["voice"] = voice

        response = requests.post(
            f"{config.VOICE_SERVER_URL}/generate_mixed",
            json=payload,
            timeout=config.VOICE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("success"):
            print(f"❌ generate_mixed failed: {result.get('error')}")
            return None

        voice_id      = result["voice_id"]
        download_path = result.get("download_path", f"/voice/{voice_id}")
        source_url    = f"{config.VOICE_SERVER_URL}{download_path}"

        return {
            "voice_id":   voice_id,
            "source_url": source_url,
            "size":       result["size"],
            "sha256":     result["sha256"],
            "settings":   result["settings"],
        }

    except requests.exceptions.Timeout:
        print(f"❌ timeout: generate_mixed")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ connection error: generate_mixed")
        return None
    except Exception as e:
        print(f"❌ generate_voice_mixed error: {e}")
        return None
    
def push_to_m5stack(voice_url: str) -> bool:
    """TTS生成済みのURLをM5Stackに送りつけて再生させる（push型・fire-and-forget）"""
    def _send():
        time.sleep(1.5)
        try:
            m5stack_url = f"http://{config.M5STACK_IP}:{config.M5STACK_PORT}/play"
            requests.post(
                m5stack_url,
                json={"voice_url": voice_url},
                timeout=30,
            )
        except Exception as e:
            print(f"[PUSH] エラー: {e}")
    
    threading.Thread(target=_send, daemon=True).start()
    print(f"[PUSH] M5Stack再生指示: {voice_url}")
    return True

def cleanup_old_voice_files(max_age_seconds=3600, keep_latest=True):
    """古い音声ファイルを削除する"""
    try:
        response = requests.post(
            f"{config.VOICE_SERVER_URL}/cleanup",
            json={"max_age_seconds": max_age_seconds, "keep_latest": keep_latest},
            timeout=config.VOICE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return int(response.json().get("deleted", 0))
    except Exception as e:
        print(f"⚠️ cleanup error: {e}")
        return 0
