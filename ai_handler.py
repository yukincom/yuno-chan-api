# ai_handler.py

import re
import time
from datetime import datetime

from config import config
from member_loader import get_family_call_map, get_primary_child, get_family, get_primary_call, mask_names, unmask_names
import llm_client

def needs_search(text):
    """検索キーワードを含む発話はWeb検索を使う"""
    return any(kw in text for kw in config.SEARCH_KEYWORDS)


# アンディ待機モード状態
_andy_wait = {
    "active":     False,
    "expires_at": 0.0,
}

def _is_english(text):
    """テキストが主に英語かどうか判定（英字比率50%以上）"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    en_count = sum(1 for c in letters if ord(c) < 128)
    return (en_count / len(letters)) >= 0.5

def detect_intent(user_text):
    """発話の意図を判定して返す
    
    Returns:
        'andy_direct'    : 「アンディ」＋英語 or 待機モード中＋英語 → アンディに転送
        'andy_english'   : 「アンディ」＋「英語で/英語に」→ フレーズ教えて待機モードON
        'andy_minecraft' : 「アンディ」のみ → Minecraft文脈でassistantが応答
        'english_yuno'   : 英語のみ → assistantが英語で応答
        'normal'         : それ以外 → 通常応答
    """
    has_andy    = any(kw in user_text for kw in config.ANDY_KEYWORDS)
    has_en_kw   = any(kw in user_text for kw in config.ENGLISH_TRANSLATE_KEYWORDS)
    is_english  = _is_english(user_text)

    # 待機モードの期限チェック
    if _andy_wait["active"] and time.time() > _andy_wait["expires_at"]:
        _andy_wait["active"] = False
        print("[INTENT] アンディ待機モード タイムアウト")

    # 待機モード中 or 「アンディ」＋英語 → アンディに転送
    if is_english and (_andy_wait["active"] or has_andy):
        return "andy_direct"

    # 「アンディ」＋「英語で/英語に」→ フレーズ教えて待機モードON
    if has_andy and has_en_kw:
        return "andy_english"

    # 「アンディ」のみ → マイクラ文脈
    if has_andy:
        return "andy_minecraft"

    # 英語のみ → ユノが英語で応答
    if is_english:
        return "english_yuno"

    return "normal"

def set_andy_wait_mode(active):
    """アンディ待機モードのON/OFF"""
    _andy_wait["active"]     = active
    _andy_wait["expires_at"] = time.time() + config.ANDY_WAIT_TIMEOUT if active else 0.0
    print(f"[INTENT] アンディ待機モード {'ON' if active else 'OFF'}")

# 英語モード
_english_mode = {
    "active": False,
}
def set_english_mode(active: bool):
    _english_mode["active"] = active
    print(f"[INTENT] 英語モード {'ON' if active else 'OFF'}")

def is_english_mode() -> bool:
    return _english_mode["active"]

def _remove_katakana_reading(text: str) -> str:
    """「英単語」の後に続くカタカナ読みを除去する"""
    # 「発音は〜って感じ」パターンを除去
    text = re.sub(r'[。、]?発音は[「」ァ-ヶー・\s]+(?:って感じ)?(?:かな)?', '', text)
    # 英単語直後のカタカナ括弧を除去（例：school（スクール））
    text = re.sub(r'([A-Za-z\"\'])\s*[（(][ァ-ヶー・]+[）)]', r'\1', text)
    return text.strip()

def get_ai_response(user_text, context, speaker, mode="normal"):
    """AIで応答生成（llm_client経由・プロバイダー切り替え対応）"""
    # ★ AIに渡す前に名前をマスク
    masked_text = mask_names(user_text)

    recent_text = ""
    for conv in context.get("recent_conversations", []):
        recent_text += f"  {mask_names(conv['user'])} → {mask_names(conv['assistant'])}\n"

    # ★ 家族構成もマスク
    family_text = chr(10).join(
        f"- {mask_names(name)}: {role}"
        for name, role in context.get('family', {}).items()
    )
    notes_text = mask_names(context.get('notes', '注釈なし'))
    game_text = ""
    for game in context.get("game_progress", []):
        game_text += f"  {game['game_name']}: {game['progress']}\n"

    if needs_search(user_text):
        sentence_rule = "- 回答は検索結果の内容を優先してね！3〜4文、150文字程度でまとめてね！"
    else:
        sentence_rule = "- 2文程度、50文字以内でまとめてね！"
    
    _call_map = get_family_call_map()  # {"family1": "お母さん", ...}
    _child_name = get_primary_child() 
    family_call = _call_map.get(speaker)

    if family_call:
        speaker_rule = f"- 今話しかけているのは{family_call}です。{family_call}に向けて返答してください。{_child_name}には話しかけないでください。"
    elif speaker == "other":
        speaker_rule = f"- 話者は{_child_name}ではありません。返答に「{_child_name}」という名前を含めないでください。"
    else:
        speaker_rule = f"- 話者は{_child_name}です。"

    mode_rule = ""
    if mode == "andy_english":
        mode_rule = f"""
- userがMinecraftのAI assistantに英語で話しかけたいと思っています。
- userの日本語を英語フレーズに変換して1つ教えてあげてください。
- 例：「"Andy, where are the diamonds?" って言ってみよう！」
- フレーズは短く、言いやすいものにしてください。
"""
    elif mode == "andy_minecraft":
        mode_rule = """
- MinecraftのAI assistantに関する話題です。
- Minecraftの文脈で自然に会話してください。
"""
    elif mode == "english_yuno":
        mode_rule = "- 英語で返答してください。"


    # マスクラベルの呼び名ルールを動的生成
    family_call_rules = "\n".join(
        f"- [家族{i}]のことは「{get_primary_call(member)}」と呼んでください。"
        for i, member in enumerate(get_family(), 1)
    )

    prompt = f"""
    あなたの名前は「{config.ASSISTANT_NAME}」。{context.get('persona', '')} {config.ASSISTANT_PERSONA}

# 家族構成
{family_text} 

# 最近の会話
{recent_text if recent_text else '今日はまだ会話していない'} 

# ゲーム進行状況
{game_text if game_text else 'ゲーム情報なし'}

# 子供についての注釈
{notes_text} 

現在時刻: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}
話者: {speaker}

会話のルール:
{mode_rule}
- {sentence_rule} 
- {speaker_rule}
- {family_call_rules}
- userの発言を繰り返したり、言い換えたりしないでね！
- 直近、５件程度の出力にuserの名前がある場合は、userの名前を入れないでね！
- 直近、５件程度の出力に「お」とか「あ」のような感嘆がある場合は、感嘆を入れないようにしてね。
- 「最近の会話」を参照し、話題が続いている場合はそれまでの文脈を踏まえて返答する
- 以下の「好きなもの」に関するキーワードが出たら、前の文脈と自然に繋げる
  {context.get('interests', '')}
- わからないことは必要以上に想像で補わず、「わからないなー」と正直に回答してください。
- 「おはよう」等の挨拶は、された時だけ返してね！
- 「〜だよ」「〜だな」「〜じゃない？」など親しみやすい口調
- 電話で喋っているようなつもりで話してください。
- できないお願いは「ごめんね、それ僕にはできないんだ〜」って優しく断ってね。

ユーザー: {masked_text} 
アシスタント: """
    try:
        if needs_search(user_text):
            raw = llm_client.call_search(prompt)
        else:
            raw = llm_client.call(prompt)
        ai_text = unmask_names(raw)
        ai_text = _remove_katakana_reading(ai_text)
        return ai_text
    except Exception as e:
        print(f"[ERROR] LLM エラー: {e}")
        return "ごめん、今ちょっと調子悪いや...後でまた話そうね！"