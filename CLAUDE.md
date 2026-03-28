# CLAUDE.md - yuno-chan-api

## プロジェクト概要

おしゃべりホームアシスタント「ユノ」のバックエンド。  
M5Stack CoreS3 Lite をマイク・スピーカーとして使い、ローカル STT/TTS × LLM で音声会話を実現する Flask サーバー。

---

## アーキテクチャ

```
M5Stack（マイク録音）
  → POST /speech/transcribe（Whisper STT）
  → 話者判定（detect_speaker）
  → LLM（Gemini / Grok / Ollama / OpenRouter）
  → Google Search Grounding（「調べて」キーワード時のみ）
  → VOICEVOX / Kokoro（TTS）
  → POST /play → M5Stack（push型再生）

LINE / Discord
  → Render Webhook / Bot ポーリング
  → process_notification()
  → TTS → M5Stack
```

---

## ファイル構成と役割

| ファイル | 役割 |
|---------|------|
| `app.py` | Flask メインサーバー（ポート5000）。ルーティングのみ |
| `voice_server.py` | TTS サーバー（ポート5001）。VOICEVOX + Kokoro 日英混合 |
| `ai_handler.py` | 意図判定・プロンプト生成・LLM 呼び出し |
| `llm_client.py` | LLM 抽象化層。`AI_PROVIDER` で切り替え |
| `config.py` | 設定管理 + `mask_names()` / `unmask_names()` |
| `memory_manager.py` | Markdown ベース記憶（today.md 読み書き） |
| `member_loader.py` | member.json アクセサ。名前マスク・話者判定用データを提供 |
| `admin_routes.py` | Web 管理 UI（Flask Blueprint）。ENV_GROUPS 定義 |
| `init_files.py` | 初回起動時テンプレートファイル自動生成 |
| `services/chat_service.py` | 会話処理・話者判定（`detect_speaker`）・意図分岐 |
| `services/voice_service.py` | push型音声送信（`push_to_m5stack`）。fire-and-forget |
| `services/speech_service.py` | Whisper.cpp ラッパー |
| `services/weather_service.py` | Open-Meteo API。today.md に天気セクションを書く |
| `services/notification_service.py` | LINE/Discord 通知処理 |
| `services/discord_service.py` | Discord Bot ポーリング・起動時既読処理 |
| `services/batch_service.py` | 夜間バッチ。会話ログを要約→アーカイブ |
| `services/scheduler_service.py` | 定時アナウンス・ポーリング登録 |
| `services/andy_voice.py` | Mindcraft Andy の音声出力監視 |

---

## 重要な設計上の注意

### 名前マスク（config.py）
- LLM に送る前に `mask_names(text)` で個人名を `[学習者1]` `[家族1]` 等に置換
- LLM の返答に `unmask_names(text)` で元に戻す
- カタカナ・ひらがな両対応。`member.json` の `name` フィールドから自動生成

### LLM プロバイダー切り替え（llm_client.py）
- `AI_PROVIDER=gemini` → google-genai SDK
- `AI_PROVIDER=openai` → OpenAI 互換（Grok / Ollama / OpenRouter）
- Google Search Grounding は **Gemini 固定**。他プロバイダーでは使えない

### push 型音声再生（voice_service.py）
- Mac から M5Stack に `POST /play {"voice_url": "..."}` を送信
- `threading` で fire-and-forget。Flask をブロックしない
- M5Stack 側の `/play` エンドポイントで受け取りキューに積む

### 話者判定（chat_service.py）
- `detect_speaker(text)` がテキストの言語パターンで家族を識別
- `member.json` の `speech_patterns` フィールドを参照
- 戻り値: `"family1"` / `"family2"` / `"other"` / `"child"`

### Google Search Grounding
- `needs_search(text)` で `SEARCH_KEYWORDS` に一致する時だけ発火
- 必ず `google-genai` SDK（新SDK）を使うこと
- 旧 SDK（`google-generativeai`）では Search Grounding が使えない

### member.json の設計
- `name` / `call` フィールドは文字列・配列どちらでも可
  - 例: `"name": "ゆき"` または `"name": ["ゆき", "ユキ", "Yuki"]`
- `speech_patterns`: 話者判定に使うキーワードリスト
- `line_user_id` / `discord_user_id`: 通知の送信者識別に使用

### メモリ構成（basic-memory）
```
~/basic-memory/
├── today.md   # 当日の会話履歴 + 天気 + ゲーム進行
└── YYYY.md    # 年次アーカイブ（batch_service が自動生成）
```
- `batch_service.py` が起動時に前日分を要約して `today.md` を圧縮
- アーカイブは `SUMMARY_KEEP_DAYS`（デフォルト14日）を超えたら週単位で移動

---

## .env の主要設定

```bash
# AI
GEMINI_API_KEY=
AI_PROVIDER=gemini          # gemini / openai
AI_CHAT_MODEL=gemini-2.5-flash
AI_SUMMARY_MODEL=gemini-2.5-flash
AI_SEARCH_MODEL=gemini-2.5-flash   # Gemini 固定
SEARCH_KEYWORDS=調べて,しらべて,教えて,おしえて

# Whisper
WHISPER_CLI=/path/to/whisper-cli
WHISPER_MODEL=/path/to/ggml-kotoba-whisper-v2.0-q5_0.bin
WHISPER_MODEL_EN=/path/to/ggml-medium.en.bin
WHISPER_NO_SPEECH_THOLD=0.6

# TTS
VOICEVOX_URL=http://localhost:50021
VOICEVOX_SPEAKER_ID=2
VOICE_SERVER_URL=http://localhost:5001
KOKORO_VOICE_YUNO=af_sarah

# M5Stack
M5STACK_IP=192.168.1.49
M5STACK_PORT=80

# Memory
MEMORY_DIR=/Users/yourname/basic-memory
ARCHIVE_DIR=/path/to/archive
SUMMARY_KEEP_DAYS=14

# Server
SERVER_PORT=5000
```

---

## よくある問題

| 症状 | 原因 | 対処 |
|------|------|------|
| Search Grounding が動かない | 旧 SDK を使っている | `google-genai` に移行 |
| 名前がそのまま LLM に渡る | mask_names が効いていない | config.py のマスク設定を確認 |
| 音声が二重再生される | voice_state と push が両立している | push 型に一本化 |
| Discord の過去メッセージを拾う | 起動時既読処理が未実行 | `_init_last_message_id()` を確認 |
| Whisper が遅い | CPU 処理になっている | Metal（Apple Silicon）対応ビルドを使う |
