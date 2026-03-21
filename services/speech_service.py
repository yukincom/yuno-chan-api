import subprocess
import tempfile
import os

import re
from config import config

WHISPER_CLI   = config.WHISPER_CLI
WHISPER_MODEL = config.WHISPER_MODEL

class SpeechService:
    """whisper.cpp ラッパー"""

    def transcribe(self, audio_content: bytes, language_code: str = "ja-JP", use_english_model: bool = False):
        """音声データをテキストに変換"""
        tmp_16k = None
        try:
            lang = language_code.split("-")[0]

            # WAVを一時保存（M5Stackが16kHzで録音するのでそのまま使う）
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_content)
                tmp_16k = f.name

            if use_english_model and config.WHISPER_MODEL_EN:
                model  = config.WHISPER_MODEL_EN
                lang   = "en"
                prompt = "User talking to Minecraft bot"
            else:
                model  = WHISPER_MODEL
                prompt = "日本語の日常会話です。"

            result = subprocess.run(
                [
                    WHISPER_CLI,
                    "-m", model,
                    "-f", tmp_16k,
                    "-l", lang,
                    "--prompt", prompt,
                    "--no-speech-thold", str(config.WHISPER_NO_SPEECH_THOLD),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            if result.returncode != 0:
                print(f"[SPEECH] whisper.cpp stderr:\n{result.stderr}")

            output = result.stdout.strip()
            lines = [line.strip() for line in output.splitlines() if line.strip()]

            transcript = ""
            for line in lines:
                if line.startswith("[") and "-->" in line:
                    parts = line.split("]", 1)
                    if len(parts) > 1:
                        text = parts[1].strip()
                        # specialトークンを除去
                        text = re.sub(r'\[_[A-Z_0-9]+_\]', '', text).strip()
                        if text:
                            transcript += text + " "
            transcript = transcript.strip()

            if not transcript:
                print("[SPEECH] No speech detected")
                return None
            
            # 許可リスト
            ALLOW_SHORT = [config.ASSISTANT_NAME] + config.SPEECH_ALLOW_SHORT
            # ノイズパターン（トイレ・水音・背景音の誤認識）
            NOISE_PATTERNS = ["ごおおお", "ごーーー", "ざーーー", "うおおお"]

            if any(noise in transcript for noise in NOISE_PATTERNS):
                print(f"[SPEECH] Noise detected, ignoring: '{transcript}'")
                return None
            if len(transcript.strip()) <= 3:
                if transcript.strip() not in ALLOW_SHORT:
                    print(f"[SPEECH] Too short, ignoring: '{transcript.strip()}'")
                    return None

            return transcript

        except subprocess.TimeoutExpired:
            print("[SPEECH] タイムアウト (60秒超)")
            return None
        except subprocess.CalledProcessError as e:
            print(f"[SPEECH] 実行エラー: {e.stderr[:200]}")
            return None
        except Exception as e:
            print(f"[SPEECH] 例外: {e}")
            return None
        finally:
            # 必ず一時ファイルを削除
            for f in [tmp_16k]:
                if f and os.path.exists(f):
                    os.unlink(f)
                

# グローバルインスタンス
speech_service = SpeechService()