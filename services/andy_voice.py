"""
andy_voice.py
Mindcraftのログを監視してアンディの発言をローカルスピーカーで再生するサービス。

watchdogでandy.logの変更を検知 → 新しい行だけ読む → Kokoro(am_adam) → プレイヤー再生
"""

import os
import re
import queue
import subprocess
import tempfile
import threading
from pathlib import Path

import requests
from config import config
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

# Mindcraftのログファイルパス
ANDY_LOG_PATH = Path(config.ANDY_LOG_PATH).expanduser()
ANDY_LOG_RESOLVED = ANDY_LOG_PATH.resolve(strict=False)

# アンディの発言を抽出する正規表現
ANDY_RESPONSE_PATTERN = re.compile(r'andy full response to .*?:\s*"{1,2}(.*?)"{1,2}')

# マインクラフトコマンドを除去
COMMAND_PATTERN = re.compile(r"![a-zA-Z]+(?:\([^)]*\)?)?")
LOOP_PATTERNS = [
    "What is going on? Report your status!",
    "Hey Notch, I'm back online",
]
# 再生キュー（1つずつ順番に再生するため）
_speech_queue = queue.Queue()

def clear_speech_queue():
    """再生キューを空にする"""
    while not _speech_queue.empty():
        try:
            _speech_queue.get_nowait()
            _speech_queue.task_done()
        except Exception:
            break

def _speech_worker():
    while True:
        text = _speech_queue.get()
        if text is None:
            break
        _speak_as_andy(text)
        _speech_queue.task_done()

def _extract_speech(raw_text: str):
    """コマンドを除去してセリフだけ返す"""
    text = COMMAND_PATTERN.sub("", raw_text).strip()
    return text if text else None


def _play_wav(tmp_path: str):
    """環境に応じて再生コマンドを選択（macOSはafplay優先）"""
    if subprocess.call(["which", "afplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return subprocess.Popen(["afplay", tmp_path])

    if subprocess.call(["which", "ffplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    raise RuntimeError("音声再生コマンドが見つかりません（afplay / ffplay）")


def _speak_as_andy(text: str):
    """Kokoro(am_adam)で音声生成 → ローカル再生"""
    try:
        voice_server = config.VOICE_SERVER_URL
        voice = config.KOKORO_VOICE_ANDY

        res = requests.post(
            f"{voice_server}/generate_en",
            json={"text": text, "voice": voice},
            timeout=30,
        )
        res.raise_for_status()
        result = res.json()
        if not result.get("success"):
            print(f"[ANDY] 音声生成失敗: {result.get('error')}")
            return

        wav_url = f"{voice_server}{result['download_path']}"
        wav_data = requests.get(wav_url, timeout=10).content

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_data)
            tmp_path = f.name

        proc = _play_wav(tmp_path)
        proc.wait()

        try:
            os.remove(tmp_path)
        except Exception:
            pass

    except Exception as e:
        print(f"[ANDY] エラー: {e}")


class AndyLogHandler(FileSystemEventHandler):
    """andy.logの変更を検知して新しい行だけ処理するハンドラ"""

    def __init__(self):
        self._pos = 0
        self._open_log(seek_end=True)

    @staticmethod
    def _same_target(path_str: str) -> bool:
        return Path(path_str).resolve(strict=False) == ANDY_LOG_RESOLVED

    def _open_log(self, seek_end: bool):
        """ログファイルを開いて位置を初期化"""
        try:
            if ANDY_LOG_PATH.exists():
                with open(ANDY_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                    if seek_end:
                        f.seek(0, os.SEEK_END)
                    else:
                        f.seek(0)
                    self._pos = f.tell()
                print(f"[ANDY] 監視対象: {ANDY_LOG_PATH} (pos={self._pos})")
            else:
                self._pos = 0
                print(f"[ANDY] ログファイル待機中: {ANDY_LOG_PATH}")
        except Exception as e:
            print(f"[ANDY] ログオープンエラー: {e}")
            self._pos = 0

    def _read_new_lines(self):
        """前回位置から新しい行だけ読む（truncate/rotate対応）"""
        try:
            size = ANDY_LOG_PATH.stat().st_size
            if size < self._pos:
                self._pos = 0

            with open(ANDY_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                lines = f.readlines()
                self._pos = f.tell()
            return lines
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"[ANDY] 読み取りエラー: {e}")
            return []

    def _handle_lines(self):
        for line in self._read_new_lines():
            match = ANDY_RESPONSE_PATTERN.search(line)
            if not match:
                continue
            raw_text = match.group(1)
            speech = _extract_speech(raw_text)
            if not speech:
                continue

            # ループ検出：キューをクリアして再生しない
            if any(pattern in raw_text for pattern in LOOP_PATTERNS):
                print(f"[ANDY] ループ検出・スキップ: {raw_text[:40]}")
                clear_speech_queue()
                continue

            print(f"[ANDY] 発言検出: {speech[:60]}")
            _speech_queue.put(speech)

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not self._same_target(event.src_path):
            return
        self._handle_lines()

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or not self._same_target(event.src_path):
            return
        print("[ANDY] ログファイルが作成されました。先頭から監視します")
        self._open_log(seek_end=False)
        self._handle_lines()

    def on_moved(self, event: FileSystemEvent):
        if event.is_directory:
            return
        dest_path = getattr(event, "dest_path", "")
        if dest_path and self._same_target(dest_path):
            print("[ANDY] ログファイルが移動/再作成されました。先頭から監視します")
            self._open_log(seek_end=False)
            self._handle_lines()


class AndyVoiceWatcher:
    """watchdogオブザーバーの管理クラス"""

    def __init__(self):
        self._observer = None
        self._handler = None
        self._worker = None

    def start(self):
        """監視開始（app.py起動時に呼ぶ）"""
        # 再生ワーカー起動
        self._worker = threading.Thread(target=_speech_worker, daemon=True)
        self._worker.start()

        self._handler = AndyLogHandler()
        self._observer = Observer(timeout=3)

        watch_dir = ANDY_LOG_PATH.parent
        watch_dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(watch_dir), recursive=False)
        self._observer.start()
        print(f"[ANDY] watchdog 監視開始: {watch_dir}")

    def stop(self):
        """監視停止（app.py終了時に呼ぶ）"""
        _speech_queue.put(None) 
        if self._observer:
            self._observer.stop()
            self._observer.join()
            print("[ANDY] watchdog 停止")


# シングルトン
andy_watcher = AndyVoiceWatcher()