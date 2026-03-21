# services/weather_service.py
"""
天気取得サービス（Open-Meteo API使用）
APIキー不要・無料・pip install requests だけでOK

対象地域: .envの WEATHER_LATITUDE / WEATHER_LONGITUDE で設定
"""

import re
import requests
from datetime import datetime
from pathlib import Path
from config import config

# 座標（.envから取得）
LATITUDE  = float(config.WEATHER_LATITUDE)
LONGITUDE = float(config.WEATHER_LONGITUDE)

# 天気コード → 日本語変換
WEATHER_CODE = {
    0:  "快晴",
    1:  "晴れ",
    2:  "晴れ時々くもり",
    3:  "くもり",
    45: "霧",
    48: "霧",
    51: "小雨",
    53: "雨",
    55: "強い雨",
    61: "小雨",
    63: "雨",
    65: "強い雨",
    71: "小雪",
    73: "雪",
    75: "大雪",
    77: "みぞれ",
    80: "にわか雨",
    81: "にわか雨",
    82: "強いにわか雨",
    85: "にわか雪",
    86: "強いにわか雪",
    95: "雷雨",
    96: "雷雨",
    99: "激しい雷雨",
}


def _fetch_weather():
    """Open-Meteo APIから天気データを取得"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  LATITUDE,
        "longitude": LONGITUDE,
        "daily": [
            "weathercode",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
        ],
        "current_weather": True,
        "timezone":        "Asia/Tokyo",
        "forecast_days":   2,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _build_weather_section(data, mode="morning"):
    """
    today.md に保存する ## 天気 セクションを生成

    mode:
        "morning" → 今日の予報のみ
        "noon"    → 今日の確定値 + 明日の予報
    """
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")
    daily = data["daily"]

    def day_text(idx, label):
        code  = daily["weathercode"][idx]
        t_max = daily["temperature_2m_max"][idx]
        t_min = daily["temperature_2m_min"][idx]
        rain  = daily["precipitation_probability_max"][idx]
        desc  = WEATHER_CODE.get(code, f"不明({code})")
        return f"- {label}: {desc}、最高{t_max:.0f}℃ / 最低{t_min:.0f}℃、降水確率{rain}%"

    today_text    = day_text(0, "今日")
    tomorrow_text = day_text(1, "明日")

    if mode == "morning":
        return (
            f"## 天気\n"
            f"{today_text}\n"
            f"- 更新: {now}（朝の予報）\n"
        )
    else:
        return (
            f"## 天気\n"
            f"{today_text}\n"
            f"{tomorrow_text}\n"
            f"- 更新: {now}（昼の確定値）\n"
        )


def _update_today_md(weather_section):
    """today.md の ## 天気 セクションを上書き"""
    md_path = Path(config.MEMORY_DIR) / "today.md"

    if not md_path.exists():
        md_path.write_text(weather_section + "\n", encoding="utf-8")
        print("[WEATHER] today.md を新規作成して天気を記録")
        return

    content = md_path.read_text(encoding="utf-8")

    pattern = r'## 天気\n.*?(?=\n## |\Z)'
    if re.search(pattern, content, re.DOTALL):
        new_content = re.sub(pattern, weather_section.rstrip(), content, flags=re.DOTALL)
    else:
        # セクションがなければ先頭に追加
        new_content = weather_section + "\n" + content

    md_path.write_text(new_content, encoding="utf-8")
    print(f"[WEATHER] today.md を更新しました")


def update_weather(mode):
    """天気更新の共通処理"""
    label = "朝の予報" if mode == "morning" else "昼の確定値"
    try:
        data    = _fetch_weather()
        section = _build_weather_section(data, mode=mode)
        _update_today_md(section)
        print(f"[WEATHER] {label}を記録:\n{section}")
    except Exception as e:
        print(f"[WEATHER] {label}の更新失敗: {e}")


def get_weather_response(target="today"):
    """
    「今日/明日の天気は？」に対する返答テキストを生成
    → chat_service.py から呼ぶ

    target: "today" or "tomorrow"
    """
    try:
        data  = _fetch_weather()
        daily = data["daily"]

        idx   = 0 if target == "today" else 1
        label = "今日" if target == "today" else "明日"

        code  = daily["weathercode"][idx]
        t_max = daily["temperature_2m_max"][idx]
        t_min = daily["temperature_2m_min"][idx]
        rain  = daily["precipitation_probability_max"][idx]

        # ── 天気コメント
        if code in (0, 1):
            weather_comment = f"{label}は晴れるみたいだよ！"
        elif code in (2, 3, 45, 48):
            weather_comment = f"{label}はくもりみたい。"
        elif code in (71, 73, 75, 77, 85, 86):
            weather_comment = f"{label}は雪が降るんだって！どのくらい降るのかなー！"
        else:
            # 雨系（51〜82, 95〜99）
            if rain >= 70:
                weather_comment = f"{label}は雨だよ！傘を持って行ってね！"
            else:
                weather_comment = f"{label}は雨が降るかもしれないよ。念のため傘を持って行ってね！"

        # ── 気温コメント
        if t_max <= 10:
            temp_comment = f"最高気温は{t_max:.0f}度、かなり寒いよ！暖かくしてね！"
        elif t_max <= 18:
            temp_comment = f"最高気温は{t_max:.0f}度、寒そうだよ！"
        elif t_max <= 26:
            temp_comment = f"最高気温は{t_max:.0f}度、過ごしやすい気温だね！"
        elif t_max <= 29:
            temp_comment = f"最高気温は{t_max:.0f}度、暑いみたい！"
        else:
            temp_comment = f"最高気温は{t_max:.0f}度、かなり暑いみたい！出かけるときは気をつけてね！"

        # ── 寒暖差コメント
        diff_comment = ""
        if t_max - t_min >= 7:
            diff_comment = f"寒暖差が{t_max - t_min:.0f}度もあるから、体調に気をつけてね！"

        return f"{weather_comment}{temp_comment}{diff_comment}"

    except Exception as e:
        print(f"[WEATHER] 天気返答生成失敗: {e}")
        return None