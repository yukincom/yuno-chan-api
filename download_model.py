# download_model.py
"""MLXモデルのダウンロードスクリプト
使い方: python download_model.py [model_id]
例:    python download_model.py mlx-community/Qwen3.6-35B-A3B-4bit-DWQ
引数なしの場合は .env.local の AI_CHAT_MODEL を使用
"""
import sys
from huggingface_hub import snapshot_download
from dotenv import load_dotenv
import os

load_dotenv()
load_dotenv(".env.local", override=True)

def download(model_id: str):
    print(f"📥 ダウンロード開始: {model_id}")
    snapshot_download(
        repo_id=model_id,
        local_files_only=False,
    )
    print(f"✅ ダウンロード完了: {model_id}")

if __name__ == "__main__":
    model_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("AI_CHAT_MODEL")
    if not model_id:
        print("❌ モデルIDを指定してください")
        sys.exit(1)
    download(model_id)