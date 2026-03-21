# phrases.py
"""固定フレーズの定義（唯一の真実の場所）"""
from member_loader import get_family, get_primary_call

# 静的フレーズ（キー: テキスト）
FIXED_PHRASES: dict[str, str] = {
    "ok_english":  "OK! Let's speak English!",
    "ok_japanese": "わかった！日本語に戻るね！",
    "noise_check": "なんの音？",
}

def build_all_phrases() -> dict[str, str]:
    """family_home など動的フレーズも含めた全フレーズを返す"""
    phrases = dict(FIXED_PHRASES)
    for i, member in enumerate(get_family(), 1):
        call = get_primary_call(member)
        if call:
            phrases[f"family{i}_home"] = f"{call}がそろそろ帰ってくるって言ってるよ！"
    return phrases

def get_phrase(key: str) -> str:
    """キーからフレーズを取得（見つからなければ空文字）"""
    return build_all_phrases().get(key, "")