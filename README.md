# 🤖 AI News YouTuber System

**「忙しい人のためのざっくりAIニュース」自動生成・投稿システム**

Google スプレッドシートに書き込まれたAIニュース原稿を読み取り、音声合成・動画生成・YouTube投稿・Discord通知までをすべて自動で行うシステムです。

---

## 📐 システム構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                    Google Apps Script (GAS)                     │
│              ※スプレッドシートに紐づいた自動プログラム            │
│                                                                 │
│  毎日指定時刻に自動実行                                           │
│  ┌──────────────┐      ┌──────────────────────────────────┐    │
│  │ Gemini API   │ ×3本 │  第1回: AIニュースを生成           │    │
│  │(2回呼び出し) │ ───▶ │  第2回: 台本の検証・圧縮・         │    │
│  │              │      │  冒頭挨拶削除・400文字以内に要約   │    │
│  └──────────────┘      └──────────────────────────────────┘    │
│                                          │                      │
│                                          ▼                      │
│                         Google Sheets「Main_Scripts」に書き込み  │
│                         (A〜L列・ニュース3行分・G列=空=未処理)    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ (G列が空＝まだ動画を作っていない行を3行取得)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   main.py（Pythonプログラム）                     │
│                ※お使いのMacBook上で動くメインプログラム            │
│                                                                 │
│  ① スプレッドシートから未処理の3行を読み込む                      │
│  ② Pexels（写真サイト）からニュース画像を3枚取得                  │
│  ③ テキストを音声に変換して8つのパーツに分けて結合                │
│  ④ 音声＋画像＋テロップを合成して動画を作成（1280×720）           │
│  ⑤ YouTubeに限定公開でアップロード                               │
│  ⑥ スプレッドシートのG列にYouTubeのURLを書き込む                 │
│  ⑦ Discordに確認通知を送る                                      │
└─────────────────────────────────────────────────────────────────┘
                               │
                 ┌─────────────┴──────────────┐
                 ▼                            ▼
        YouTube（限定公開）            Discord通知
        generate-movies/              （視聴URL +
        YYYYMMDD/output.mp4           YouTube管理画面URL）
```

---

## 🎬 動画の構成（音声の流れ）

動画の音声は以下の8つのパーツで構成されています。

| # | パート | 内容 |
|---|---|---|
| ① | 冒頭挨拶1 | 「みなさん、こんにちは。忙しい人のためのざっくりAIニュースのお時間です。」（固定文） |
| ② | 冒頭挨拶2 | 「本日○月○日○曜日担当のAI、[モデル名]がお送り致します。」（C列・B列から自動生成） |
| ③ | AIの愚痴 | AIから人間への一言（F列） |
| ④ | ニュース開始 | 「それでは本日のニュースです。」（固定文） |
| ⑤ | ニュース本編 | 3本分のニュース台本（D列 × 3行） |
| ⑥ | ニュース終了 | 「本日のニュースは以上となります。」（固定文） |
| ⑦ | エール | 今日を乗り越えるための一言（L列） |
| ⑧ | 番組終了 | 「それでは、本日もいってらっしゃいませ。」（固定文） |

---

## 📊 スプレッドシートの構成

### シート名：`Main_Scripts`

1行目はタイトル行です。2行目以降にデータが入ります（GASが毎回2行目に追加するため、最新のニュースが一番上に来ます）。

| 列 | 項目名 | 内容 | 備考 |
|---|---|---|---|
| A | 取得日時 | `2026/06/01 07:00` のような形式 | GASが自動入力 |
| B | 曜日 | 月・火・水… | GASが自動入力 |
| C | AIモデル名 | `Gemini 2.5 Flash` など | GASが自動入力 |
| D | 番組全台本 | 音声読み上げ用テキスト（400文字以内） | GASが自動入力 |
| E | ニュースタイトル | 動画内の見出し・Discord通知に使用 | GASが自動入力 |
| F | 愚痴内容 | AIからの一言（敬語） | GASが自動入力 |
| **G** | **YouTube URL** | **処理済みかどうかの判定に使用。Pythonが動画投稿後に自動記入** | 空＝未処理、URLあり＝処理済み |
| H | ニュース取得元URL | YouTube説明欄に記載する出典URL | GASが自動入力 |
| I | 取得したニュース全文 | D列と同じ内容（記録用） | GASが自動入力 |
| J | 要約リスト | YouTube説明欄に載せる概要 | GASが自動入力 |
| K | 画像キーワードリスト | Pexelsで画像を検索するための英語キーワード | GASが自動入力 |
| L | エール内容 | 今日を乗り越える一言（敬語） | GASが自動入力 |

### スプレッドシートの作成手順

1. [Google スプレッドシート](https://sheets.google.com) を新規作成します
2. 画面下部のシートタブ名を右クリックして `Main_Scripts` に変更します
3. 1行目（タイトル行）のA〜L列に、上の表の「項目名」をそれぞれ入力します
4. スプレッドシートのURLの中から `SPREADSHEET_ID` を確認します
   ```
   https://docs.google.com/spreadsheets/d/【ここの部分がSPREADSHEET_ID】/edit
   ```
   例：`https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit`
   → SPREADSHEET_ID は `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`

---

## 🔧 MacBookの環境構築手順

### 事前に必要なもの（アカウント・権限）

- Google アカウント（YouTubeチャンネルを持っていること）
- Discord サーバー（通知を受け取りたいチャンネルの管理権限があること）
- Pexels アカウント（無料・[https://www.pexels.com](https://www.pexels.com) で作成できます）

---

### 手順1：Homebrewをインストールする

Homebrew（ホームブリュー）とは、MacBookにさまざまなソフトウェアを簡単にインストールできる仕組みです。

ターミナル（MacBookの標準アプリ。Spotlight検索で「ターミナル」と入力すると見つかります）を開いて、以下を1行コピーして貼り付け、Enterキーを押します。

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

途中でMacBookのパスワードを求められたら入力します（画面には何も表示されませんが、入力されています）。

インストールが完了したら、以下で確認します。

```bash
brew --version
```

`Homebrew 4.x.x` のように表示されれば成功です。

---

### 手順2：Pythonをインストールする

```bash
brew install python@3.11
```

インストール後、以下で確認します。

```bash
python3 --version
```

`Python 3.11.x` のように表示されれば成功です。

---

### 手順3：このリポジトリをダウンロードする

```bash
git clone https://github.com/your-username/Ai_News_Youtuber.git
cd Ai_News_Youtuber
```

> `git` コマンドが見つからない場合は `brew install git` を実行してから再度お試しください。

---

### 手順4：仮想環境を作成して有効化する

仮想環境とは、このプロジェクト専用のPythonの実行場所です。他のプロジェクトに影響を与えません。

```bash
python3 -m venv venv
source venv/bin/activate
```

コマンドの先頭に `(venv)` と表示されれば、仮想環境が有効になっています。

> **次回ターミナルを開いたときは、** 毎回 `source venv/bin/activate` を実行してから作業してください。

---

### 手順5：必要なライブラリをインストールする

ライブラリとは、Pythonに追加できる便利な機能パッケージです。

```bash
pip install -r requirements.txt
```

`requirements.txt` の内容：

```
moviepy
gTTS
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
requests
```

---

### 手順6：ファイルの配置を確認する

以下の構成になっていることを確認します。

```
Ai_News_Youtuber/
├── main.py                        ← メインのPythonプログラム
├── generateDailyNewsScript.js     ← GASのバックアップ（GitHubで管理）
├── requirements.txt               ← 必要なライブラリの一覧
├── run.sh                         ← cron用ラッパースクリプト
├── .gitignore                     ← GitHubの管理対象外ファイルの設定
│
├── credentials/                   ← 認証ファイルをまとめるフォルダ
│   ├── client_secrets.json        ← Google Cloudからダウンロード（後述）
│   └── token.json                 ← 初回実行後に自動生成される認証ファイル
│
├── images/                        ← 動画生成に必要な画像をまとめるフォルダ
│   ├── base_ai_robot.jpg          ← ロボットキャラクターの画像
│   ├── closed_eye.jpg             ← ロボットの瞬きアニメーション用画像
│   └── lightbulb_icon.png         ← 💡アイコン画像
│
├── fonts/
│   └── HiraginoMaruGothic.ttc    ← 日本語フォント（動画のテロップに使用）
│
├── generate-movies/               ← 完成した動画の保存先（プログラムが自動で作成）
│   └── 20260601/                  ← 実行した日付のフォルダ
│       ├── output.mp4             ← 完成動画
│       ├── final_audio.mp3        ← 完成音声
│       ├── news_0.jpg             ← 取得した画像（ニュース1）
│       ├── news_1.jpg             ← 取得した画像（ニュース2）
│       └── news_2.jpg             ← 取得した画像（ニュース3）
│
└── venv/                          ← 仮想環境フォルダ（手順4で自分で作成）
```

> **注意：** `venv/`・`credentials/`・`generate-movies/` はGitHubには含まれていません（`.gitignore` で除外済み）。`venv/` は手順4で自分で作成し、`credentials/` 内のファイルは各自でダウンロード・生成してください。

---

## 📋 .gitignore の設定

プロジェクトフォルダに `.gitignore` というファイルを作成して以下を記載します。GitHubに認証情報や大容量ファイルが誤ってアップロードされるのを防ぎます。

```
# 認証情報（絶対にGitHubにアップしない）
credentials/

# 仮想環境（各自の環境で作成するため不要）
venv/

# 完成した動画・音声（大容量のため除外）
generate-movies/

# Pythonのキャッシュファイル
__pycache__/
*.pyc

# ログファイル
*.log
```

---

## 🔑 各種APIキーの設定

このシステムでは、サービスによってAPIキーの設定場所が異なります。

| APIキー・設定情報 | 設定場所 |
|---|---|
| SPREADSHEET_ID | MacBookの環境変数（`~/.zshrc`） |
| PEXELS_API_KEY | MacBookの環境変数（`~/.zshrc`） |
| DISCORD_WEBHOOK_URL | MacBookの環境変数（`~/.zshrc`） |
| GEMINI_API_KEY | GASのスクリプトプロパティ（スプレッドシート側） |
| YouTube・Sheets認証 | `credentials/client_secrets.json`（Google Cloudからダウンロード） |

---

### 1. MacBookの環境変数に設定する

環境変数とは、プログラムが参照するMacBook全体の設定値です。パスワードやAPIキーをプログラムに直接書かずに済むため、安全に管理できます。

まず設定ファイルが存在するか確認します。

```bash
ls ~/.zshrc
```

`No such file or directory` と表示された場合は、以下で新規作成します。

```bash
touch ~/.zshrc
```

次に設定ファイルをテキストエディタで開きます。

```bash
open ~/.zshrc
```

ファイルの末尾に以下を追記して保存します（`"..."` の中身はご自身の値に置き換えてください）。

```bash
# Ai_News_Youtuber 用の設定
export SPREADSHEET_ID="スプレッドシートのID"
export PEXELS_API_KEY="PexelsのAPIキー"
export DISCORD_WEBHOOK_URL="DiscordのWebhook URL"
```

保存後、以下を実行して設定を即座に反映させます。

```bash
source ~/.zshrc
```

正しく設定されているか確認します。

```bash
echo $SPREADSHEET_ID
```

スプレッドシートのIDが表示されれば成功です。

---

### 2. Google Cloudの設定（YouTube・Sheetsの利用許可）

YouTubeへの動画投稿とスプレッドシートの読み書きには、Googleから許可を取る必要があります。その許可証にあたるファイルが `client_secrets.json` です。

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセスしてGoogleアカウントでログインします
2. 画面上部の「プロジェクトを選択」→「新しいプロジェクト」で新規プロジェクトを作成します
3. 左メニューの「APIとサービス」→「ライブラリ」から以下の2つを検索して有効化します
   - **YouTube Data API v3**
   - **Google Sheets API**
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」を選択します
5. アプリケーションの種類で「デスクトップアプリ」を選択して作成します
6. ダウンロードしたJSONファイルを `client_secrets.json` という名前に変更して、プロジェクトの `credentials/` フォルダの中に置きます

```bash
mkdir -p credentials
mv ~/Downloads/client_secret_xxx.json credentials/client_secrets.json
```

> **初回実行時の認証について**
> 初めてプログラムを実行するとブラウザが自動で開き、Googleアカウントへのログインと権限の許可を求められます。許可が完了すると `credentials/token.json` が自動生成され、次回以降は自動的に認証されます。

---

### 3. Gemini APIキーの設定（GAS側）

GeminiのAPIキーはMacBookではなく、スプレッドシートのGAS側に設定します。

> ⚠️ **APIキーはGASのコードに直接書かないでください。**
> コードに直接書いてしまうと、GASの実行ログにキーがそのまま表示されてしまい、流出する危険があります。必ず以下の「スクリプトプロパティ」に設定してください。

1. 対象のスプレッドシートを開き、上部メニューの「拡張機能」→「Apps Script」を選択します
2. GASエディタが開いたら、左側メニューの「⚙️（歯車マーク）プロジェクトの設定」をクリックします
3. ページ下部の「スクリプトプロパティ」→「スクリプトプロパティを追加」をクリックします
4. 以下の1件を追加します

   | プロパティ名（左欄） | 値（右欄） |
   |---|---|
   | `GEMINI_API_KEY` | Google AI Studio で発行したAPIキー |

   > **補足：** `SPREADSHEET_ID` はここには設定不要です。GASはスプレッドシートを自動認識するため、IDを指定する必要がありません。

Gemini APIキーは [Google AI Studio](https://aistudio.google.com/) に無料でアクセスして発行できます。

---

### 4. Pexels APIキーの取得と設定

1. [Pexels](https://www.pexels.com/api/) にアクセスして無料アカウントを作成します
2. ログイン後、「Your API Key」からAPIキーをコピーします
3. 前述の `~/.zshrc` の `PEXELS_API_KEY` にそのキーを貼り付けます

---

### 5. Discord Webhook URLの取得と設定

Webhook URLとは、外部のプログラムからDiscordへメッセージを送るための専用URLです。

1. 通知を受け取りたいDiscordのチャンネルを右クリックして「チャンネルの編集」を選択します
2. 「連携サービス」→「ウェブフック」→「新しいウェブフック」をクリックします
3. 作成されたWebhookの「WebhookのURLをコピー」をクリックします
4. コピーしたURLを `~/.zshrc` の `DISCORD_WEBHOOK_URL` に貼り付けます

---

## 📝 Google Apps Script（GAS）の設定

GASとは、Googleスプレッドシートに組み込んで動かすことができるプログラムです。このシステムでは、毎日自動でAIニュースを生成してスプレッドシートに書き込む役割を担います。

> **GASのバックアップについて**
> GASにはバックアップ機能やバージョン管理機能がありません。万が一GASが消えてしまっても復元できるよう、`generateDailyNewsScript.js` としてローカルに保存し、GitHubで管理してください。

### GASのプログラムを設定する手順

1. 対象のスプレッドシートを開きます
2. 上部メニューの「拡張機能」→「Apps Script」を選択します
3. GASエディタが開いたら、`generateDailyNewsScript.js` の内容をすべてコピーして貼り付けます
4. 上部の「💾 保存」ボタンをクリックします
5. 前述の手順でGemini APIキーをスクリプトプロパティに設定します
6. 画面上部の「実行」ボタンを押して動作を確認します（初回はGoogleアカウントの権限承認が必要です）

### GASの毎日自動実行を設定する手順

1. GASエディタの左メニューにある「⏰（時計マーク）トリガー」をクリックします
2. 右下の「トリガーを追加」をクリックします
3. 以下のように設定します
   - 実行する関数：`generateDailyNewsScript`
   - イベントのソース：時間主導型
   - 時間ベースのトリガーのタイプ：日付ベースのタイマー
   - 時刻：任意の時間帯（例：午前8時〜9時）

### GASの処理内容

ニュース1本につきGemini APIを2回使用し、3本合計で6回のAPI通信を行います。

- **1回目**：最新のAIニュースを生成します
- **2回目**：生成した台本を確認・修正します（冒頭の挨拶を削除・400文字以内に圧縮）

---

## 🚀 main.pyの実行方法

### 手動で実行する場合

ターミナルを開いてプロジェクトフォルダに移動し、以下を実行します。

```bash
cd Ai_News_Youtuber
./venv/bin/python main.py
```

> **「仮想環境を有効化してから実行する」方法でも動作します。**
> ```bash
> cd Ai_News_Youtuber
> source venv/bin/activate
> python main.py
> ```

### 実行前のチェックリスト

実行前に以下を確認してください。

- [ ] `credentials/client_secrets.json` が置かれている
- [ ] `~/.zshrc` に3つの環境変数（SPREADSHEET_ID・PEXELS_API_KEY・DISCORD_WEBHOOK_URL）が設定されている
- [ ] `source ~/.zshrc` を実行して環境変数を反映済み
- [ ] GASを実行してスプレッドシートにニュースが3行書き込まれている（G列が空の行が3行あること）
- [ ] `images/` フォルダに画像3枚が揃っている
- [ ] `fonts/HiraginoMaruGothic.ttc` が置かれている

### 実行ログの例

正常に完了した場合、ターミナルには以下のようなログが表示されます。

```
📁 出力ディレクトリ: /Users/yourname/Ai_News_Youtuber/generate-movies/20260601
📊 スプレッドシートからデータを取得中...
✅ 対象行を 3 行取得しました。行番号: [2, 3, 4]
📋 処理対象: 6月1日 月曜日 / AIモデル: Gemini 2.5 Flash
   ニュース1: ○○○○○○○○
   ニュース2: ○○○○○○○○
   ニュース3: ○○○○○○○○
🖼️ Pexels から画像を取得中...
✅ 画像取得成功: ... → generate-movies/20260601/news_0.jpg
✅ 画像取得成功: ... → generate-movies/20260601/news_1.jpg
✅ 画像取得成功: ... → generate-movies/20260601/news_2.jpg
🎙️ 各セグメントの音声合成を開始します...
✅ 音声の結合が完了しました。総尺: xxx.xx秒
✅ 完成音声を保存しました: generate-movies/20260601/final_audio.mp3
🎬 動画のレンダリングを開始します...
🎉 動画レンダリング完了: generate-movies/20260601/output.mp4
📤 YouTubeへの限定公開アップロードを実行中...
✅ YouTubeアップロード成功。Video ID: xxxxxxxxxxxx
📝 スプレッドシートのG列にYouTube URLを書き込み中...
  ✅ 行 2 のG列に書き込み完了
  ✅ 行 3 のG列に書き込み完了
  ✅ 行 4 のG列に書き込み完了
🔔 Discordへの確認通知を送信しました。
🎉 全工程が正常に完了しました！（処理時間: xxx.xx秒）
🗑️ 一時ファイルを削除しました
```

### 実行時間の目安

台本400文字×3本のニュースでの実測値です。

| 処理の内容 | 目安時間 |
|---|---|
| データ取得・画像取得 | 約30秒 |
| 音声合成（8パート） | 約30秒 |
| 動画の生成 | 約4〜5分 |
| YouTubeへのアップロード | 約30〜60秒 |
| スプレッドシート更新・Discord通知 | 約5秒 |
| **合計** | **約6〜7分** |

### よくあるエラーと対処法

| エラーメッセージ | 原因 | 対処法 |
|---|---|---|
| `No text to speak` | スプレッドシートの列（F列・L列など）が空 | GASを再実行してデータを入れ直す |
| `未処理行が○行しかありません` | G列が空の行が3行未満 | GASを実行してニュースを追加する |
| `FileNotFoundError: client_secrets.json` | 認証ファイルの場所が違う | `credentials/` フォルダに置かれているか確認する |
| `token.json` 関連エラー | 認証トークンの期限切れ | `credentials/token.json` を削除して再実行する |
| 環境変数が空 | `source ~/.zshrc` を実行していない | `source ~/.zshrc` を実行してから再度試す |

---

## ⏰ MacBookに毎日自動実行させる設定（cron）

cron（クーロン）とは、**お使いのMacBookで指定した時刻にプログラムを自動的に実行する仕組み**です。スマートフォンのアラームのようなイメージで、毎日決まった時間に `main.py` を起動させることができます。

> **注意：** cronを使う場合、MacBookが起動してスリープしていない状態である必要があります。毎日確実に動かしたい場合は、実行時間帯にMacBookがスリープしない設定にしておいてください（システム設定 → ディスプレイ → スリープ）。

### 手順1：ラッパースクリプトを作成する

cronはMacBookの環境変数を自動では読み込まないため、あらかじめ設定を読み込むスクリプトを用意します。

プロジェクトフォルダに `run.sh` というファイルを以下の内容で作成します（`yourname` の部分はご自身のMacBookのユーザー名に変更してください）。

```bash
#!/bin/bash
source /Users/yourname/.zshrc
cd /Users/yourname/Ai_News_Youtuber
./venv/bin/python main.py
```

> ユーザー名がわからない場合は、ターミナルで `whoami` と入力すると確認できます。

ファイルを作成したら、実行できるように権限を付与します。

```bash
chmod +x /Users/yourname/Ai_News_Youtuber/run.sh
```

### 手順2：自動実行の時刻を設定する

ターミナルで以下を実行します。

```bash
crontab -e
```

エディタ（`vi`）が開きます。`i` キーを押して入力モードにしてから、以下を入力します（例：毎日午前8時15分に実行）。

```
15 8 * * * /Users/yourname/Ai_News_Youtuber/run.sh >> /Users/yourname/Ai_News_Youtuber/cron.log 2>&1
```

入力後、`Esc` キーを押してから `:wq` と入力してEnterキーを押すと保存されます。

左端の数字の意味は `分 時 * * *` の順番です。`15 8` であれば「8時15分」を意味します。

> **GASの実行時刻との関係について**
> GASを午前8時に実行するよう設定した場合、スプレッドシートへの書き込みは10分以内に完了します。そのため cronを「午前8時15分」に設定すると、午前8時30分ごろには動画がYouTubeに投稿されます。

### 手順3：ログを確認する

実行結果は `cron.log` に自動保存されます。以下で確認できます。

```bash
cat /Users/yourname/Ai_News_Youtuber/cron.log
```

---

## ⚠️ セキュリティについて

APIキーや認証情報の取り扱いには注意してください。

- **APIキーをコードに直接書かない。** GASのコード内にキーを書いてしまうと、実行ログにキーがそのまま表示されて流出します。必ず環境変数またはスクリプトプロパティで管理してください
- **`credentials/` フォルダはGitHubにアップしない。** `.gitignore` で除外されていますが、意図せずアップロードしないよう注意してください
- **APIキーが含まれたログをAIなどの外部サービスに貼り付けない。** ログにキーが混入している場合があります
- **サービス完成後はAPIキーを新しいものに取り替える**と、より安全に運用できます

---

## 💰 APIの利用料金について

このシステムで使用するAPIはすべて**無料枠内で運用できます**。

### Gemini API（GAS側）の利用回数

| 期間 | APIの呼び出し回数 |
|---|---|
| 1日 | 6回（3本 × 2回） |
| 1ヶ月（30日） | 180回 |

Gemini 2.5 Flash の無料枠は1日あたり250回まで利用できます。このシステムは1日6回しか使用しないため、**無料枠の約2.4%しか消費しません。1ヶ月間毎日動かし続けても、完全に無料枠内に収まります。**

> ⚠️ Googleは無料枠の上限を変更することがあります。現在の正確な上限は [AI Studio Rate Limitページ](https://aistudio.google.com/rate-limit) でご確認ください。

### その他のAPIの料金

| サービス | 料金 |
|---|---|
| YouTube Data API v3 | 無料（1日の利用上限内） |
| Google Sheets API | 無料 |
| Pexels API | 無料（商用利用可） |
| gTTS（Google テキスト読み上げ） | 無料 |
| Discord Webhook | 無料 |

---

## 📁 保存されるファイル

プログラムを実行した日付ごとのフォルダに、以下のファイルが保存されます。

```
generate-movies/
└── 20260601/                  ← 実行日（年月日）のフォルダ
    ├── output.mp4             ← 完成動画（YouTubeに投稿済み）
    ├── final_audio.mp3        ← 完成音声（全パートを結合したもの）
    ├── news_0.jpg             ← ニュース1の画像（Pexelsから取得）
    ├── news_1.jpg             ← ニュース2の画像
    └── news_2.jpg             ← ニュース3の画像
```

音声合成中の途中ファイルは処理完了後に自動的に削除されます。

---

## 🔄 同じ動画が二重投稿されないしくみ

スプレッドシートの **G列（YouTube URL）** が処理済みかどうかの判断に使われます。

- **G列が空欄** → まだ動画を作っていない → 処理対象
- **G列にYouTubeのURLが入っている** → 既に動画を投稿済み → スキップ

YouTubeへの投稿が完了すると、自動的にG列にURLが書き込まれます。そのため、誤って2回実行してしまっても同じニュースで動画が重複投稿されることはありません。

---

## 📄 ライセンス

MIT License
