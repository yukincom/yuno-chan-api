# services/chat_service.py
"""チャットサービスモジュール"""

import traceback

from config import config
from ai_handler import get_ai_response, detect_intent, set_andy_wait_mode, set_english_mode
from services.andy_bridge import is_andy_online, send_to_andy
from services.voice_service import generate_voice_mixed, push_to_m5stack
from services.weather_service import get_weather_response
from member_loader import get_speaker_patterns, get_children, get_primary_child, get_all_names
from memory_manager import RobotMemory
from phrases import get_phrase


def _build_voice_response(ai_response, user_text, speaker, speaker_label, generate_voice_flag):
    """音声生成・M5Stackへpush・会話保存・レスポンス返却をまとめた共通処理"""
    memory = RobotMemory()
    _child_name = get_primary_child()
    label  = speaker_label if speaker_label else _child_name
    memory.add_conversation(speaker, user_text, ai_response, speaker_label=label)

    if generate_voice_flag:
        print(f"[AI] ({len(ai_response)}文字): {ai_response}")
        voice_result = generate_voice_mixed(
            ai_response,
            speaker_id=config.VOICEVOX_SPEAKER_ID
        )
        if voice_result:
            push_to_m5stack(voice_result["source_url"])
        else:
            print("[AI] 音声生成失敗")

    return {"success": True, "response": ai_response, "error": None}


def process_chat(user_text, speaker="child", generate_voice_flag=False, speaker_label=None):
    NOISE_PATTERNS = ["ごちそう"]  # 誤認識しやすいワード

    if user_text.strip() in NOISE_PATTERNS:
        ai_response = get_phrase("noise_check") 
        return _build_voice_response(
            ai_response, user_text, speaker, speaker_label, generate_voice_flag
        )
    # チャットを処理
    if any(kw in user_text for kw in ["イングリッシュモード", "イングイッシュモード", "英語モード", "えいごもーど"]):
        set_english_mode(True)
        ai_response = get_phrase("ok_english") 
        return _build_voice_response(
            ai_response, user_text, speaker, speaker_label, generate_voice_flag
        )
    if any(kw in user_text.lower() for kw in ["japanese mode", "japanese modo", "日本語モード", "にほんごもーど"]):
        set_english_mode(False)
        ai_response = get_phrase("ok_japanese")
        return _build_voice_response(
            ai_response, user_text, speaker, speaker_label, generate_voice_flag
        )
    
    # 天気キーワードチェック
    weather_keywords = [
        (config.WEATHER_KEYWORDS_TODAY,    "today"),
        (config.WEATHER_KEYWORDS_TOMORROW, "tomorrow"),
    ]
    for keywords, target in weather_keywords:
        if any(kw in user_text for kw in keywords):
            ai_response = get_weather_response(target)
            if ai_response:
                return _build_voice_response(
                    ai_response, user_text, speaker, speaker_label, generate_voice_flag
                )
    # 歌唱
    if any(kw in user_text for kw in config.SONG_TRIGGER):

        def to_hira(s):
            return ''.join(
                chr(ord(c) - 0x60) if 'ァ' <= c <= 'ン' else c
                for c in s
            )
        user_hira = to_hira(user_text)

        song_id = next(
            (sid for keyword, sid in config.SONG_MAP.items() if to_hira(keyword) in user_hira),
            None
        )
        
        if song_id:
            song_url = f"{config.VOICE_SERVER_URL}/song/{song_id}"
            ai_response = "うたうよ～！"

            memory = RobotMemory()
            memory.add_conversation(speaker, user_text, ai_response, speaker_label=speaker_label)

            push_to_m5stack(song_url)
            return {"success": True, "response": ai_response, "error": None}

    # ── アンディ/英語 意図判定 ──────────────
    intent = detect_intent(user_text)
    print(f"[INTENT] {intent}: {user_text[:40]}")
    # アンディに直接転送
    if intent == "andy_direct":
        if is_andy_online():
            send_to_andy(user_text)
            set_andy_wait_mode(False)
            return {"success": True, "response": None, "error": None}
        else:
            return _build_voice_response(
                config.ANDY_OFFLINE_MESSAGE, user_text, speaker, speaker_label, generate_voice_flag
            )

    # LLM応答が必要な全パターン
    try:
        mode = intent if intent in ("andy_english", "andy_minecraft", "english_yuno") else "normal"
        memory      = RobotMemory()
        context     = memory.get_context(query=user_text)
        ai_response = get_ai_response(user_text, context, speaker, mode=mode)

        if intent == "andy_english":
            set_andy_wait_mode(True)

        return _build_voice_response(
            ai_response, user_text, speaker, speaker_label, generate_voice_flag
        )

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "response": None, "error": str(e)}
    

def detect_speaker(text):
    """発話内容から話者を判定（カタカナ・ひらがな両対応）

    Returns:
        "family1" / "family2" / ... / "other" / "child"
    """

    def to_hira(s):
        return ''.join(
            chr(ord(c) - 0x60) if 'ァ' <= c <= 'ン' else c
            for c in s
        )

    text_hira = to_hira(text)

    # member.jsonの家族パターンで判定
    for patterns, call_name, speaker_id in get_speaker_patterns():
        for pattern in patterns:
            if pattern and to_hira(pattern) in text_hira:
                print(f"[SPEAKER] → {call_name}  {pattern}")
                return speaker_id

    # 子供の名前が含まれていたら「other（子供以外が話してる）」
    for child in get_children():
        for child_name in get_all_names(child): 
            if child_name and to_hira(child_name) in text_hira:
                print(f"[SPEAKER] → other（{child_name}を検出）")
                return "other"

    return "child"
