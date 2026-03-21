# member_loader.py
"""member.jsonを読み込み、家族データへのアクセスを提供する"""
import re
import json
from pathlib import Path

_MEMBER_JSON = Path(__file__).parent / "member.json"


# ─────────────────────────────────────
# 内部ヘルパー（name/callがリストでも文字列でも対応）
# ─────────────────────────────────────

def _load():
    if not _MEMBER_JSON.exists():
        return {"children": [], "family": [], "friends": []}  # ファイルなしは空データ
    with open(_MEMBER_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def get_primary_name(member: dict) -> str:
    """name の最初の1つを返す（表示・照合の基準名）"""
    name = member.get("name", "")
    return name[0] if isinstance(name, list) else name

def get_all_names(member: dict) -> list:
    """name の全バリアントをリストで返す（マスク用）"""
    name = member.get("name", "")
    if isinstance(name, list):
        return [n for n in name if n]
    return [name] if name else []

def get_primary_call(member: dict) -> str:
    """call の最初の1つを返す（通知メッセージ等で使う表示名）"""
    call = member.get("call", "")
    return call[0] if isinstance(call, list) else call

# ─────────────────────────────────────
# 基本アクセサ
# ─────────────────────────────────────

def get_children() -> list:
    return _load().get("children", [])

def get_family() -> list:
    return _load().get("family", [])

def get_friends() -> list:
    return _load().get("friends", [])

def get_primary_child() -> str:
    """メインの学習者の名前（表示用・基準名）を返す"""
    children = get_children()
    return get_primary_name(children[0]) if children else ""


def get_child_notes(child: dict) -> str:
    """学習者の注釈を返す"""
    return child.get("notes", "")

def get_child_interests(child: dict) -> list:
    """学習者の興味・好きなものを返す"""
    interests = child.get("interests", [])
    return interests if isinstance(interests, list) else [interests]

# ─────────────────────────────────────
# 通知・話者判定
# ─────────────────────────────────────

def find_by_user_id(user_id: str) -> dict | None:
    if not user_id:
        return None
    data = _load()
    all_members = data.get("family", []) + data.get("children", [])
    for member in all_members:
        if member.get("line_user_id") == user_id:
            return member
        if member.get("discord_user_id") == user_id:
            return member
    return None

def get_call_name_by_user_id(user_id: str, default: str = "") -> str:
    member = find_by_user_id(user_id)
    if not member:
        return default
    return get_primary_call(member) or get_primary_name(member) or default

def get_speaker_patterns() -> list:
    """
    話者判定用パターンを返す
    [(patterns_list, call_name, speaker_id), ...]
    例: (["あら", "かしら"], "お母さん", "family1")
    """
    result = []
    for i, member in enumerate(get_family(), 1):
        patterns = [p for p in member.get("speech_patterns", []) if p]
        call = get_primary_call(member)   
        result.append((patterns, call, f"family{i}"))
    return result

def get_family_call_map() -> dict:
    """speaker_id → call_name のマッピングを返す
    例: {"family1": "お母さん", "family2": "お父さん"}
    """
    return {
        f"family{i}": get_primary_call(member) 
        for i, member in enumerate(get_family(), 1)
    }


# ─────────────────────────────────────
# 名前よびだし
# ─────────────────────────────────────

def get_mask_replacements() -> dict:
    """mask_names用: {実名: ラベル}
    学習者1, 学習者2 / 家族1, 家族2 / 友達1, 友達2
    """
    rep = {}
    for i, child in enumerate(get_children(), 1):
        for name in get_all_names(child):   
            rep[name] = f"[学習者{i}]"
    for i, member in enumerate(get_family(), 1):
        for name in get_all_names(member):  
            rep[name] = f"[家族{i}]"
    for i, friend in enumerate(get_friends(), 1):
        name = friend.get("name", "")        
        if name and name != "友達の呼び名":  
            rep[name] = f"[友達{i}]"

    return rep

def get_unmask_replacements() -> dict:
    """unmask_names用: {ラベル: 実名}"""
    rep = {}
    for i, child in enumerate(get_children(), 1):
        name = get_primary_name(child)   
        if name:
            rep[f"[学習者{i}]"] = name
    for i, member in enumerate(get_family(), 1):
        name = get_primary_name(member) 
        if name:
            rep[f"[家族{i}]"] = name
    for i, friend in enumerate(get_friends(), 1):
        name = friend.get("name", "")
        if name and name != "友達の呼び名":
            rep[f"[友達{i}]"] = name
    return rep


# ─────────────────────────────────────
# 通知有効チェック
# ─────────────────────────────────────

def has_line_users() -> bool:
    data = _load()
    for m in data.get("family", []) + data.get("children", []):
        if m.get("line_user_id"):
            return True
    return False

def has_discord_users() -> bool:
    data = _load()
    for m in data.get("family", []) + data.get("children", []):
        if m.get("discord_user_id"):
            return True
    return False


# ─────────────────────────────────────
# 名前マスク適用
# ─────────────────────────────────────
def _to_hira(s: str) -> str:
    return ''.join(
        chr(ord(c) - 0x60) if 'ァ' <= c <= 'ン' else c
        for c in s
    )

def mask_names(text: str) -> str:
    """家族・子どもの名前をラベルに置換（アシスタント名は対象外）"""
    replacements = {}
    for name, label in get_mask_replacements().items():
        replacements[name] = label
        replacements[_to_hira(name)] = label  # ひらがな版も対象

    for name, label in replacements.items():
        if not name:
            continue
        text = re.sub(
            rf'(?<![ぁ-んァ-ン一-龥ａ-ｚＡ-Ｚ]){re.escape(name)}(?![ぁ-んァ-ン一-龥ａ-ｚＡ-Ｚ])',
            label,
            text
        )
    return text

def unmask_names(text: str) -> str:
    """ラベルを元の名前に戻す"""
    for label, name in get_unmask_replacements().items():
        text = text.replace(label, name)
    return text