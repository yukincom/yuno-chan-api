# services/notification_service.py
"""LINE/Discord通知サービスモジュール"""
from config import config
from member_loader import get_call_name_by_user_id, mask_names
from services.voice_service import generate_voice, push_to_m5stack
from memory_manager import RobotMemory


def generate_notification_message(sender_name, original_message):
    """元のメッセージ内容に基づいて通知メッセージを生成"""
    if "帰る" in original_message or "帰ります" in original_message:
        return f"{sender_name}がそろそろ帰ってくるって言っているよ！"
    elif "遅い" in original_message or "遅く" in original_message:
        return f"{sender_name}、今夜はちょっと遅いって言ってるよ〜"
    elif "よろしく" in original_message:
        return f"{sender_name}からよろしくって言ってるよ〜"
    elif "買" in original_message:
        return f"{sender_name}が買ってきてほしいものある？って聞いてるよ〜"
    else:
        return f"{sender_name}からメッセージだよ。「{original_message}」だってさ！"


def process_notification(user_id, message):
    """LINE/Discord通知を処理してM5Stackにpushする"""
    sender_name = get_call_name_by_user_id(user_id, default=config.FAMILY_DEFAULT)
    notification_message = generate_notification_message(sender_name, mask_names(message))

    # 音声生成 → M5Stackにpush
    voice_result = generate_voice(notification_message)
    if voice_result:
        push_to_m5stack(voice_result["source_url"])
    else:
        print("[NOTIFY] 音声生成失敗")

    # メモリに保存
    memory = RobotMemory()
    memory.add_conversation(
        "notify",
        mask_names(message),
        "",
        speaker_label=f"[LINE通知] {sender_name}"
    )

    return {
        "sender":        sender_name,
        "message":       notification_message,
        "original_text": message,
    }