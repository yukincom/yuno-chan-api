# memory_manager.py
"""basic-memory版 記憶システム（Markdown形式）"""

import re
from datetime import datetime
from pathlib import Path

from config import config
from member_loader import get_children, get_primary_name, mask_names

MEMORY_DIR = Path(config.MEMORY_DIR)
MEMORY_DIR.mkdir(exist_ok=True)

class RobotMemory:
    """
    Markdown形式の記憶システム。

    ファイル構成:
    ~/basic-memory/
    └── today.md    # ゲーム進行 + 会話履歴
    """

    def __init__(self):
        self.memory_dir = MEMORY_DIR

    # ─────────────────────────────
    # ファイル読み書き
    # ─────────────────────────────
    def _read(self, name):
        path = self.memory_dir / f"{name}.md"
        if not path.exists():
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _append(self, name, text):
        path = self.memory_dir / f"{name}.md"
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
            
    # ─────────────────────────────
    # 会話の記憶
    # ─────────────────────────────
    def add_conversation(self, speaker, user_text, ai_response, speaker_label=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        label = speaker_label if speaker_label else speaker
        masked_user = mask_names(user_text)
        masked_ai   = mask_names(ai_response)
        entry = f"\n### {timestamp}\n- {label}: {masked_user}\n- {config.ASSISTANT_NAME}: {masked_ai}\n"
        self._append("today", entry)

    def get_recent_conversations(self, limit=None):
        """today.mdから最近の会話を取得（speaker引数は互換性のために残すが使わない）"""
        content = self._read("today")
        if not content:
            return []

        blocks = re.split(r'\n### ', content)
        conversations = []

        for block in blocks:
            lines = block.strip().split("\n")
            if not lines:
                continue

            user_text = ""
            ai_text = ""
            timestamp = ""

            for line in lines:
                if re.match(r'\d{4}-\d{2}-\d{2}', line):
                    timestamp = line.strip()
                elif line.startswith("- ") and ": " in line:
                    parts = line[2:].split(": ", 1)
                    if len(parts) == 2:
                        role, text = parts
                        if role == config.ASSISTANT_NAME:
                            ai_text = text
                        else:
                            user_text = text

            if user_text and ai_text:
                conversations.append({
                    "timestamp": timestamp,
                    "user": user_text,
                    "assistant": ai_text,
                })

        return conversations[-limit:] if limit else conversations

    # ─────────────────────────────
    # コンテキスト取得（AI呼び出し用）
    # ─────────────────────────────
    def get_context(self, query=None):
        """AI呼び出し用のコンテキストを構築"""
        today_md = self._read("today") 

        # ペルソナは.envから
        persona = config.ASSISTANT_PERSONA

        # interests / notes は member.json の children[0] から
        children = get_children()
        primary_child = children[0] if children else {}
        raw_interests = primary_child.get("interests", [])
        interests = "、".join(raw_interests) if isinstance(raw_interests, list) else raw_interests
        notes = primary_child.get("notes", "")

        # 家族構成（年齢計算込み）
        family = {}
        for child in children: 
            name = get_primary_name(child)
            family[name] = child.get("notes", "")

        recent = self.get_recent_conversations(limit=config.AI_RECENT_TURNS)

        game_text = self._extract_section(today_md, "ゲーム進行")
        game_progress = []
        for line in game_text.split("\n"):
            if ": " in line and line.startswith("- "):
                parts = line[2:].split(": ", 1)
                if len(parts) == 2:
                    game_progress.append({
                        "game_name": parts[0].strip(),
                        "progress": parts[1].strip()
                    })

        return {
            "persona":              persona,
            "family":               family,
            "recent_conversations": recent,
            "game_progress":        game_progress,
            "notes":                notes,
            "interests":            interests,
        }

    def _extract_section(self, content, section_name):
        """## セクション名 の内容を抽出"""
        pattern = rf'## {re.escape(section_name)}\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    # ─────────────────────────────
    # バッチ処理用
    # ─────────────────────────────
    def get_daily_summary(self):
        """今日の会話を取得"""
        today = datetime.now().strftime("%Y-%m-%d")
        recent = self.get_recent_conversations(limit=100)
        return [c for c in recent if c.get("timestamp", "").startswith(today)]