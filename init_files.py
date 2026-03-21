# init_files.py
"""初回起動時に必要なファイルを自動生成する"""
import json
from pathlib import Path

_BASE = Path(__file__).parent

def ensure_default_files():
    """存在しないファイルだけテンプレートから生成（既存ファイルは触らない）"""

    # ── member.json ──────────────────────────────────────
    _ensure_json(_BASE / "member.json", {
        "children": [{
                "name": ["たろう", "タロウ", "TARO", "TAROU"],
                "notes": "大学に通っている",
                "interests": ["たこやき","空を眺める"],
                "speech_patterns": [],
                "line_user_id": "",
                "discord_user_id": ""
            }
        ],
        "family": [{
                "name": ["ゆうこ", "ユウコ", "YUUKO"],
                "call": ["お母さん", "おかあさん"],
                "speech_patterns": ["あら", "かしら"," ゆのちゃん", "ユノちゃん", "タロちゃん", "タロウちゃん", "タロオちゃん", "ただしさん", "ただすさん",  "ますよ", "ですよ"],
                "notes": "看護師",
                "line_user_id": "",
                "discord_user_id": ""
                },{
                "name": ["ただし", "タダシ", "ただす", "タダス", "TADASHI"],
                "call": ["お父さん", "おとうさん"],
                "speech_patterns": ["たろう", "タロウ", "タロ", "ゆのくん", "ユノくん", "ゆうこさん", "ユウコさん", "ゆこさん", "ユコさん"],
                "notes": "教師",
                "line_user_id": "",
                "discord_user_id": ""
            }
        ],
            "friends": [{
                "name": "友達の呼び名"
            }
        ]
    })    

    # ── announcements.json ────────────────────────────────
    _ensure_json(_BASE / "announcements.json", [
        {
        "hour": 7,
        "message": "そろそろ出かける時間だよ！もう準備はできた？",
        "minute": 25,
        "weekday_only": True,
        "with_weather": True
        }
    ])

    # ── .env（.env.exampleをコピー） ───────────────────────
    _ENV_DIR = Path.home() / "env"
    env_path = _ENV_DIR / ".env"
    if not env_path.exists():
        example_path = _BASE / ".env.example"
        if example_path.exists():
            env_path.write_text(example_path.read_text(encoding="utf-8"))
            print("[INIT] ✅ .env を .env.example からコピーしました")
            print("[INIT] ⚠️  .env を編集してAPIキー等を設定してください")
        else:
            print("[INIT] ⚠️  .env も .env.example も見つかりません")

    print("[INIT] ✅ ファイル初期化チェック完了")


def _ensure_json(path: Path, default: dict | list):
    """JSONファイルが存在しない場合だけ生成"""
    if not path.exists():
        path.write_text(
            json.dumps(default, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[INIT] ✅ {path.name} を新規作成しました")