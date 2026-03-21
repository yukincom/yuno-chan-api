# services/scheduler_service.py
"""スケジューラーサービスモジュール"""

import requests
from datetime import date
import jpholiday

from config import config
from apscheduler.schedulers.background import BackgroundScheduler
from services.weather_service import update_weather, get_weather_response
from services.voice_service import generate_voice, cleanup_old_voice_files, push_to_m5stack
from services.notification_service import process_notification
from services.discord_service import poll_discord
from member_loader import has_line_users, has_discord_users
from memory_manager import RobotMemory 


# スケジューラーインスタンス（グローバル）
scheduler = BackgroundScheduler()

# ════════════════════════════════════════
#  ユーティリティ
# ════════════════════════════════════════

def is_holiday():
    """今日が土日または日本の祝日か判定"""
    today = date.today()
    return today.weekday() >= 5 or jpholiday.is_holiday(today)


def scheduled_announcement(message: str, with_weather: bool = False, weekday_only: bool = False, weather_target: str = "today", holiday_only: bool = False):
    """定時アナウンス（Gemini不使用・スクリプト固定）"""
    if weekday_only and is_holiday():
        print(f"[ANNOUNCE] 休日のためスキップ: {message[:20]}")
        return
    if holiday_only and not is_holiday():
        print(f"[ANNOUNCE] 平日のためスキップ: {message[:20]}")
        return
    try:
        text = message
        if with_weather:
            weather = get_weather_response(weather_target) 
            if weather:
                text += weather

        print(f"[ANNOUNCE] {text[:50]}")
        voice_result = generate_voice(text)
        if voice_result:
            push_to_m5stack(voice_result["source_url"])
            memory = RobotMemory()
            memory.add_conversation("schedule", text, "", speaker_label="スケジュール")

    except Exception as e:
        print(f"[ANNOUNCE] エラー: {e}")

# ════════════════════════════════════════
#  LINE / Render ポーリング
# ════════════════════════════════════════

def poll_render():
    """Renderの/pollエンドポイントをポーリング"""
    try:
        response = requests.get(f"{config.RENDER_URL}/poll", timeout=60)
        response.raise_for_status()
        data = response.json()
        if data.get("notification"):
            n = data["notification"]
            process_notification(n.get("user_id", ""), n.get("message", ""))
    except requests.exceptions.Timeout:
        pass
    except Exception as e:
        print(f"[ERROR] poll_render: {e}")


def scheduled_cleanup():
    """スケジュールドクリーンアップ実行"""
    try:
        cleanup_old_voice_files(max_age_seconds=3600, keep_latest=True)
    except Exception as e:
        print(f"[ERROR] scheduled_cleanup: {e}")


# ════════════════════════════════════════
#  スケジューラー設定
# ════════════════════════════════════════

def setup_scheduler(notification_enabled=True):
    if notification_enabled:
        if has_line_users():
            scheduler.add_job(poll_render, "interval", seconds=config.POLL_INTERVAL)
            print("[SCHEDULER] LINE ポーリング開始")

        if has_discord_users():
            scheduler.add_job(poll_discord, "interval", seconds=config.POLL_INTERVAL)
            print("[SCHEDULER] Discord ポーリング開始")

    scheduler.add_job(scheduled_cleanup, "interval", hours=1)

    # 天気更新
    scheduler.add_job(update_weather, "cron",
        hour=config.WEATHER_MORNING_HOUR, minute=config.WEATHER_MORNING_MINUTE, args=["morning"])
    scheduler.add_job(update_weather, "cron",
        hour=config.WEATHER_NOON_HOUR, minute=config.WEATHER_NOON_MINUTE, args=["noon"])

    # 定時アナウンス（リストをループで登録）
    for item in config.ANNOUNCEMENTS:
        scheduler.add_job(
            scheduled_announcement, "cron",
            hour=item["hour"], minute=item["minute"],
            kwargs={
                "message":      item["message"],
                "with_weather":   item.get("with_weather", False),
                "weekday_only":   item.get("weekday_only", False),
                "weather_target": item.get("weather_target", "today"), 
                "holiday_only":   item.get("holiday_only", False),     
            }
        )
    print("[SCHEDULER] 定時アナウンス ")

    scheduler.start()


def start_scheduler():
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()