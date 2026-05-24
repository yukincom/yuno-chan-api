# 🐥 Yuno-chan / ﾕﾉﾁｬﾝ

**こちらのプロジェクトはStackChan_EX_Amigoのサーバーとして統合されました**

https://github.com/yukincom/StackChan_EX_Amigo

---

**Talking home assistant for M5Stack — Local STT/TTS × LLM × Push-based audio**

日本語・English 両対応のおしゃべりホームアシスタント。  
M5Stack CoreS3 をマイク・スピーカーとして使い、**ローカル音声認識 × AI 会話 × 音声合成**を組み合わせたホームアシスタントです。

---

## ✨ 主な機能

- 🎙️ **ローカル STT** — Whisper.cpp（kotoba-whisper-v2.0）
- 🇯🇵 **日本語 TTS** — VOICEVOX
- 🇺🇸 **英語 TTS** — Kokoro-82M（日英混合テキスト対応）
- 🤖 **マルチ LLM** — Gemini / Grok / Ollama / OpenRouter を Web UI で切り替え
- 🔍 **Web 検索** — 「調べて」で Google Search Grounding 発動
- 📱 **LINE / Discord 通知を音声読み上げ**
- 📣 **定時アナウンス** — 時報・天気・祝日対応
- ⛏️ **Mindcraft 連携** — AI エージェント「Andy」と Minecraft 内で音声対話
- 🔒 **名前マスク** — 個人名を自動マスクして LLM に送信
- ⚙️ **Web 管理 UI** — ブラウザから家族構成・AI 設定を編集

### 💰 API コストを最小化する設計

STT・TTS・話者判定・天気はすべてローカル or 無料 API。  
有料 LLM API は会話応答と必要時の Web 検索のみ。

---

## 🖥️ システム構成

```
話しかける
  ↓
M5Stack CoreS3 Lite（マイク・スピーカー）
  ↕ HTTP
Mac / Linux サーバー（Flask :5000）
  ├─ Whisper.cpp（STT）
  ├─ LLM（Gemini 等）
  ├─ VOICEVOX / Kokoro（TTS）
  └─ M5Stack に push 型で音声送信

LINE / Discord → Webhook / Bot → Mac → M5Stack
```

M5Stack ファームウェアは [m5stack-push-avatar](https://github.com/yukincom/m5stack-push-avatar) を使用。

---

## 🔧 必要なもの

| 用途 | 必要なもの |
|------|-----------|
| ハードウェア | M5Stack CoreS3 Lite |
| 音声認識 | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) + [kotoba-whisper-v2.0](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0-gguf) |
| 日本語 TTS | [VOICEVOX](https://voicevox.hiroshiba.jp/) |
| 英語 TTS | [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) |
| LLM | Gemini API キー（他プロバイダーも可） |
| 記憶 | [Basic Memory](https://github.com/basicmachines-co/basic-memory) |

---

## 🚀 セットアップ

```bash
git clone https://github.com/yukincom/yuno-chan-api.git
cd yuno-chan-api
pip install -r requirements.txt
```

`.env` に API キーを設定：

```bash
GEMINI_API_KEY=your_key_here
```

サーバーを起動：

```bash
python voice_server.py  # TTS サーバー（ポート5001）
python app.py           # メインサーバー（ポート5050）
```

ブラウザで `http://localhost:5000/admin` を開いて残りの設定を入力。  
初回起動時に設定ファイルのテンプレートが自動生成されます。

---

## ⚠️ ご利用上の注意

本プロジェクトは **API キー・サーバーを管理する成人の方が責任をもって運用することを前提**としています。  
各 LLM API の利用規約を確認のうえ、運用者の責任においてご使用ください。

---

## 📄 License

MIT License

---

## 🙏 Acknowledgements

[m5stack-avatar](https://github.com/meganetaaan/m5stack-avatar) /
[whisper.cpp](https://github.com/ggerganov/whisper.cpp) /
[kotoba-whisper](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.0-gguf) /
[VOICEVOX](https://voicevox.hiroshiba.jp/) /
[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) /
[Open-Meteo](https://open-meteo.com/) /
[Mindcraft](https://github.com/kolbytn/mindcraft) /
[Basic-Memory](https://github.com/basicmachines-co/basic-memory)
