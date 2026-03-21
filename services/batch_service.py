# services/batch_service.py
"""
毎起動時に昨日分の会話履歴を処理するバッチサービス。

処理内容:
1. 昨日の会話履歴があるか確認
2. LLMで要約生成
3. 生データをアーカイブ化
4. mdファイルを要約だけに圧縮
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from config import config
from member_loader import mask_names, unmask_names, get_primary_child
import llm_client


MEMORY_DIR = Path(config.MEMORY_DIR)
ARCHIVE_DIR = Path(config.ARCHIVE_DIR)

def run_if_needed():
    """起動時に呼ぶ。未処理の日付を全て処理する。"""

    if not Path(config.ARCHIVE_DIR).exists():
        print("[BATCH] アーカイブ先が見つかりません。スキップします")
        return

    md_path = MEMORY_DIR / "today.md"
    content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    # today.md 内の全日付を抽出
    all_dates = sorted(set(re.findall(r'### (\d{4}-\d{2}-\d{2})', content)))
    today = datetime.now().strftime("%Y-%m-%d")

    # 今日以外 かつ 未アーカイブの日付を全部処理
    for target_date in all_dates:
        if target_date == today:
            continue  # 今日分はスキップ

        archive_path = ARCHIVE_DIR / f"{target_date}.md"
        if archive_path.exists():
            print(f"[BATCH] {target_date}.md は処理済み → スキップ")
            continue

        day_convos = _extract_day_conversations(content, target_date)
        if not day_convos:
            continue

        print(f"[BATCH] {target_date} 分を処理中...")
        # contentを毎回読み直す（前の処理でファイルが更新されるため）
        content = md_path.read_text(encoding="utf-8")
        _process_speaker(target_date, day_convos, content, md_path)
        
def _extract_day_conversations(content, date):
    """指定日の会話ブロックを抽出"""
    # ### 2026-02-20 15:46 形式のブロックを抽出
    pattern = rf'### {re.escape(date)}.*?(?=\n### |\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    return matches


def _process_speaker(date, day_convos, full_content, md_path):
    """1人分のバッチ処理"""

    # 1. アーカイブフォルダを作成
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 生データをSSDに保存
    archive_path = ARCHIVE_DIR / f"{date}.md"
    archive_content = f"# today の会話ログ ({date})\n\n"
    archive_content += unmask_names("\n".join(day_convos))
    archive_path.write_text(archive_content, encoding="utf-8")
    print(f"[BATCH] アーカイブ保存: {archive_path}")

    # 3. AIで要約生成
    summary = _generate_summary(date, day_convos)
    print(f"[BATCH] 要約生成完了:\n{summary}")

    # 4. mdファイルを更新（生の会話履歴を削除 → 要約に置換）
    new_content = _update_md(full_content, date, day_convos, summary)
    md_path.write_text(new_content, encoding="utf-8")
    print(f"[BATCH] today.md を更新しました")

    _archive_old_summaries(md_path)


def _generate_summary(date, day_convos):
    """AIで会話を要約"""
    convos_text = "\n".join(day_convos)

    _child_name = get_primary_child() 
    _child_label = "[学習者1]"  # マスク後のラベル

    prompt = f"""
以下は{date}の{_child_label}と{config.ASSISTANT_NAME}の会話履歴です。

音声認識のため、背景音・テレビ・YouTubeの音声が混入している可能性があります。

以下のルールで日記を書いてください：
- {_child_name}が実際に話しかけた内容を優先的に抽出する
- 文脈が不明・断片的・支離滅裂な発言は「YouTubeや背景音の可能性あり」として「youtubeを見ていた」と記載
- 明らかに{_child_name}本人の発言（呼びかけ、質問、感情表現）の場合は、{_child_name}の発言として記載
- 何も拾えなかった場合は「- この日は明確な会話なし（背景音混入の可能性）」とだけ書く
- 3〜5項目、箇条書き（- で始める）
- 全体で300字程度

例：
- Minecraftのスライムブロックに興味を示していた
- 「声枯れてる？」とお母さんの体調を気にかけていた

出力のルール：
- 日付や名前の見出しはPythonで補完します。なので、あなたは「2026年2月25日の...」「以下は...」などの導入文は書かなくていいよ！
- 箇条書き（-）だけで始めること

会話履歴:
{mask_names(convos_text)}

要約:"""
    try:
        return llm_client.call_summary(prompt)
    except Exception as e:
        print(f"[BATCH] 要約生成エラー: {e}")
        return f"- {date} の会話（要約失敗）"


def _update_md(content, date, day_convos, summary):
    """
    mdファイルから指定日の生会話を削除し、
    ## 📅 過去の要約 セクションに要約を追記する。
    """
    # 生の会話ブロックを削除
    new_content = content
    for block in day_convos:
        # ブロックの前の ### も含めて削除
        new_content = new_content.replace(f"\n### {block}", "")
        new_content = new_content.replace(block, "")

    # 要約セクションがなければ作成
    summary_entry = f"\n### {date}\n{summary}\n"

    if "## 📅 過去の要約" in new_content:
        # 既存のセクションに追記
        new_content = new_content.replace(
            "## 📅 過去の要約",
            f"## 📅 過去の要約\n{summary_entry}"
        )
    else:
        # セクション自体を新規追加（💬 会話履歴の前に挿入）
        new_content = new_content.replace(
            "## 💬 会話履歴",
            f"## 📅 過去の要約\n{summary_entry}\n## 💬 会話履歴"
        )
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    return new_content

def _archive_old_summaries(md_path):
    """
    today.mdの要約が14日を超えたら、
    最も古い週（月〜日）をyear.mdに移す。
    """
    content = md_path.read_text(encoding="utf-8")

    # 要約セクションを抽出
    summary_section = re.search(
        r'## 📅 過去の要約\n(.*?)(?=\n## |\Z)',
        content, re.DOTALL
    )
    if not summary_section:
        return

    # ### YYYY-MM-DD のブロックを日付順に取得
    blocks = re.findall(
        r'(### (\d{4}-\d{2}-\d{2})\n.*?)(?=\n### |\Z)',
        summary_section.group(1), re.DOTALL
    )
    if len(blocks) <= 14:
        return  # 14日以内なら何もしない

    # 日付でソート
    blocks.sort(key=lambda x: x[1])

    # 最も古いブロックの日付から「その週の月曜〜日曜」を特定
    oldest_date = datetime.strptime(blocks[0][1], "%Y-%m-%d").date()
    week_monday = oldest_date - timedelta(days=oldest_date.weekday())
    week_sunday = week_monday + timedelta(days=6)

    # その週に属するブロックを抽出
    to_archive = []
    to_keep = []
    for block_text, block_date_str in blocks:
        block_date = datetime.strptime(block_date_str, "%Y-%m-%d").date()
        if week_monday <= block_date <= week_sunday:
            to_archive.append((block_date_str, block_text))
        else:
            to_keep.append((block_date_str, block_text))

    if not to_archive:
        return

    # year.mdに書き出す（年をまたぐ場合は正しいyear.mdへ）
    for date_str, block_text in to_archive:
        year = date_str[:4]
        year_md_path = MEMORY_DIR / f"{year}.md"

        # year.mdがなければ新規作成（＝年が切り替わった）
        if not year_md_path.exists():
            # 前年のyear.mdをARCHIVE_DIR/year/に移動
            prev_year = str(int(year) - 1)
            prev_year_md = MEMORY_DIR / f"{prev_year}.md"
            if prev_year_md.exists():
                dest_dir = ARCHIVE_DIR / "year"
                dest_dir.mkdir(parents=True, exist_ok=True)
                prev_year_md.rename(dest_dir / f"{prev_year}.md")
                print(f"[BATCH] {prev_year}.md を {dest_dir} に移動しました")

            year_md_path.write_text(f"# {year} 会話要約\n\n", encoding="utf-8")
            print(f"[BATCH] {year}.md を新規作成")

        # ## YYYY-MM-DD 形式で追記
        entry = f"## {date_str}\n"
        # block_textから要約の中身だけ取り出す（### 行を除く）
        summary_lines = "\n".join(
            line for line in block_text.split("\n")
            if not line.startswith("### ")
        ).strip()
        entry += summary_lines + "\n\n"

        with open(year_md_path, "a", encoding="utf-8") as f:
            f.write(entry)

    print(f"[BATCH] {len(to_archive)}日分を year.md にアーカイブしました")

    # today.mdから移動済みブロックを削除
    new_summary_text = "\n".join(text for _, text in to_keep)
    new_content = re.sub(
        r'(## 📅 過去の要約\n).*?(?=\n## |\Z)',
        f'## 📅 過去の要約\n{new_summary_text}',
        content, flags=re.DOTALL
    )
    # 空白行を整理
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)
    md_path.write_text(new_content, encoding="utf-8")