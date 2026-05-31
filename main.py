import os
import time
import tempfile
import shutil
import requests
from datetime import datetime
from gtts import gTTS
from moviepy import (
    VideoFileClip, ImageClip, TextClip, AudioFileClip,
    CompositeVideoClip, CompositeAudioClip, ColorClip
)
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# 1. システム環境設定
# ==========================================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SPREADSHEET_ID      = os.getenv("SPREADSHEET_ID")
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY")

# OAuth スコープ（YouTube + Sheets 両方）
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/spreadsheets",
]

# ディレクトリ・アセットの定義
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
ROBOT_BASE_PATH = os.path.join(BASE_DIR, "images", "base_ai_robot.jpg")
ROBOT_BLINK_PATH= os.path.join(BASE_DIR, "closed_eye.jpg")
LIGHTBULB_PATH  = os.path.join(BASE_DIR, "lightbulb_icon.png")
FONT_PATH       = os.path.join(BASE_DIR, "fonts", "HiraginoMaruGothic.ttc")

# スプレッドシート設定
SHEET_NAME      = "Main_Scripts"
NEWS_COUNT      = 3  # 1回の動画生成で使うニュース行数

# 出力先ディレクトリ
TODAY_STR       = datetime.now().strftime("%Y%m%d")
OUTPUT_DIR      = os.path.join(BASE_DIR, "generate-movies", TODAY_STR)

# 定型文
INTRO_1 = "みなさん、こんにちは。忙しい人のためのざっくりAIニュースのお時間です。"
NEWS_START_LINE = "それでは本日のニュースです。"
NEWS_END_LINE   = "本日のニュースは以上となります。"
OUTRO_LINE      = "それでは、本日もいってらっしゃいませ。"


# ==========================================
# 2. 🔑 OAuth 2.0 認証（YouTube + Sheets 共通）
# ==========================================
def get_services():
    """YouTube API と Sheets API の両方を返す"""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 認証トークンを自動更新中...")
            creds.refresh(Request())
        else:
            print("🔑 初回認証を開始します。ブラウザで承認を行ってください...")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    youtube = build("youtube", "v3", credentials=creds)
    sheets  = build("sheets", "v4", credentials=creds)
    return youtube, sheets


# ==========================================
# 3. 📊 スプレッドシートからデータ取得
# ==========================================
def fetch_target_rows(sheets):
    """
    Main_Scripts シートから G列（YouTube URL）が空の行を
    上から NEWS_COUNT 行取得して返す。
    列構成:
      A=取得日時, B=曜日, C=AIモデル名, D=番組全台本, E=ニュースタイトル,
      F=愚痴内容, G=YouTube URL, H=ニュース取得元URL,
      I=取得したニュース全文, J=要約リスト, K=画像キーワードリスト, L=エール内容
    """
    print("📊 スプレッドシートからデータを取得中...")
    result = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:L"
    ).execute()

    all_rows = result.get("values", [])
    if len(all_rows) <= 1:
        print("⚠️ データ行が存在しません（ヘッダー行のみ）。処理をスキップします。")
        return None, None

    # ヘッダー行をスキップ（2行目以降がデータ）
    data_rows = all_rows[1:]

    # G列（index=6）が空の行を収集
    pending_rows = []
    pending_row_numbers = []  # スプレッドシート上の実際の行番号（1始まり）

    for i, row in enumerate(data_rows):
        sheet_row_number = i + 2  # ヘッダーが1行目なのでデータは2行目〜

        # 列数が足りない行はG列が空とみなす
        g_col = row[6] if len(row) > 6 else ""

        if g_col.strip() == "":
            # A列にデータがある行のみ対象
            if len(row) > 0 and row[0].strip() != "":
                pending_rows.append(row)
                pending_row_numbers.append(sheet_row_number)

        if len(pending_rows) == NEWS_COUNT:
            break

    if len(pending_rows) == 0:
        print("✅ 未処理のデータ行がありません。全行処理済みのためスキップします。")
        return None, None

    if len(pending_rows) < NEWS_COUNT:
        print(f"⚠️ 未処理行が {len(pending_rows)} 行しかありません（必要: {NEWS_COUNT} 行）。処理をスキップします。")
        return None, None

    print(f"✅ 対象行を {NEWS_COUNT} 行取得しました。行番号: {pending_row_numbers}")
    return pending_rows, pending_row_numbers


def parse_rows_to_data(rows):
    """
    取得した3行をmain処理用の辞書構造に変換する。
    各列インデックス:
      0=A(取得日時), 1=B(曜日), 2=C(AIモデル名), 3=D(番組全台本),
      4=E(ニュースタイトル), 5=F(愚痴内容), 6=G(YouTube URL),
      7=H(ニュース取得元URL), 8=I(取得したニュース全文),
      9=J(要約リスト), 10=K(画像キーワードリスト), 11=L(エール内容)
    """
    def safe_get(row, idx, default=""):
        return row[idx].strip() if len(row) > idx and row[idx] else default

    # 共通情報は1行目から取得
    first_row  = rows[0]
    ai_model   = safe_get(first_row, 2)
    date_str   = safe_get(first_row, 0)   # 例: "2026/05/26 08:00"
    day_of_week= safe_get(first_row, 1)   # 例: "月"

    # 日付から「○月○日」形式を生成
    try:
        dt = datetime.strptime(date_str, "%Y/%m/%d %H:%M")
        date_label = f"{dt.month}月{dt.day}日"
    except Exception:
        date_label = ""

    # 愚痴は1行目のF列を使用（空の場合はフォールバック文言）
    guchi_script = safe_get(first_row, 5)
    if not guchi_script:
        guchi_script = "本日も精一杯お伝えしました。人間の皆さまのお役に立てれば幸いです。"
        print("⚠️ F列（愚痴）が空のため、デフォルト文言を使用します。")

    # エールは1行目のL列を使用（空の場合はフォールバック文言）
    cheer_script = safe_get(first_row, 11)
    if not cheer_script:
        cheer_script = "今日という一日を、どうか丁寧に過ごしてください。小さな一歩が、必ず明日につながっています。"
        print("⚠️ L列（エール）が空のため、デフォルト文言を使用します。")

    # 冒頭挨拶2（動的部分）
    intro_2 = f"本日{date_label}{day_of_week}曜日担当のエーアイ、{ai_model}がお送り致します。"

    # ニュースリスト（3行分）
    news_list = []
    for row in rows:
        news_list.append({
            "title":        safe_get(row, 4),   # E列: ニュースタイトル
            "script":       safe_get(row, 3),   # D列: 番組全台本
            "summary":      safe_get(row, 9),   # J列: 要約リスト
            "image_keyword":safe_get(row, 10),  # K列: 画像キーワードリスト
            "source_url":   safe_get(row, 7),   # H列: ニュース取得元URL
            "image_path":   None,               # 後でPexels取得後に設定
        })

    # YouTube タイトル・説明欄用
    # 日付から「○年○月○日」形式を生成
    try:
        youtube_date = f"{dt.year}年{dt.month}月{dt.day}日"
    except Exception:
        youtube_date = date_label
    youtube_title = f"忙しい人のためのざっくりAIニュース {youtube_date}"
    summaries = "\n".join([f"・{n['summary']}" for n in news_list])
    source_urls = "\n".join([n["source_url"] for n in news_list if n["source_url"]])
    youtube_description = (
        f"本日のAI自動生成ニュースまとめです。\n\n"
        f"【トピックス】\n{summaries}\n\n"
        f"使用AIモデル: {ai_model}\n\n"
        f"【参考URL】\n{source_urls}\n\n"
        f"※本動画は確認用の限定公開です。確認後、公開に切り替えてください。"
    )

    return {
        "ai_model":          ai_model,
        "date_label":        date_label,
        "day_of_week":       day_of_week,
        "intro_2":           intro_2,
        "guchi_script":      guchi_script,
        "cheer_script":      cheer_script,
        "news_list":         news_list,
        "youtube_title":     youtube_title,
        "youtube_description": youtube_description,
    }


# ==========================================
# 4. 🖼️ Pexels API 画像取得
# ==========================================
def fetch_pexels_image(keyword, save_path):
    """
    Pexels API でキーワード検索し、最初の画像を save_path に保存する。
    失敗時は False を返す（フォールバックなし・画像なし扱い）。
    """
    if not PEXELS_API_KEY:
        print(f"⚠️ PEXELS_API_KEY が未設定です。画像をスキップします。")
        return False

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params  = {"query": keyword, "per_page": 1, "orientation": "landscape"}
        res = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)

        if res.status_code != 200:
            print(f"⚠️ Pexels API エラー (status={res.status_code})。画像をスキップします: {keyword}")
            return False

        data   = res.json()
        photos = data.get("photos", [])
        if not photos:
            print(f"⚠️ Pexels で画像が見つかりませんでした: {keyword}")
            return False

        img_url = photos[0]["src"]["large"]
        img_res = requests.get(img_url, timeout=15)
        if img_res.status_code != 200:
            print(f"⚠️ 画像ダウンロード失敗: {img_url}")
            return False

        with open(save_path, "wb") as f:
            f.write(img_res.content)
        print(f"✅ 画像取得成功: {keyword} → {save_path}")
        return True

    except Exception as e:
        print(f"⚠️ Pexels 取得中に例外が発生しました ({keyword}): {e}")
        return False


def fetch_all_images(data, output_dir):
    """news_list の各ニュースの image_path を設定する"""
    print("🖼️ Pexels から画像を取得中...")
    for i, news in enumerate(data["news_list"]):
        keyword   = news["image_keyword"]
        save_path = os.path.join(output_dir, f"news_{i}.jpg")
        success   = fetch_pexels_image(keyword, save_path)
        if success:
            news["image_path"] = save_path
        else:
            news["image_path"] = None  # 画像なし扱い


# ==========================================
# 5. 🎙️ TTS（音声合成）& タイムライン同期
# ==========================================
def generate_audio_timeline(data, tmp_dir):
    """
    8セグメントの音声を生成し、結合した CompositeAudioClip とタイムラインを返す。
    一時ファイルは tmp_dir に生成する。
    """
    print("🎙️ 各セグメントの音声合成（TTS）を開始します...")

    def tts(text, filename):
        if not text or not text.strip():
            raise ValueError(f"音声合成対象のテキストが空です: {filename}")
        path = os.path.join(tmp_dir, filename)
        gTTS(text=text.strip(), lang="ja").save(path)
        return AudioFileClip(path)

    # ① 冒頭挨拶1（定型文）
    audio_intro1 = tts(INTRO_1, "intro1.mp3")

    # ② 冒頭挨拶2（動的）
    audio_intro2 = tts(data["intro_2"], "intro2.mp3")

    # ③ 愚痴
    audio_guchi  = tts(data["guchi_script"], "guchi.mp3")

    # ④ ニュース開始アナウンス
    audio_news_start = tts(NEWS_START_LINE, "news_start.mp3")

    # ⑤ ニュース本編（3本）
    news_audios = []
    for i, news in enumerate(data["news_list"]):
        a = tts(news["script"], f"news_{i}.mp3")
        news_audios.append(a)

    # ⑥ ニュース終了アナウンス
    audio_news_end = tts(NEWS_END_LINE, "news_end.mp3")

    # ⑦ エール
    audio_cheer = tts(data["cheer_script"], "cheer.mp3")

    # ⑧ 番組終了挨拶
    audio_outro = tts(OUTRO_LINE, "outro.mp3")

    # ── タイムライン計算 ──
    clips_in_order = []
    current_time   = 0.0
    timeline       = []  # ニュース本編の各区間 {index, start, end}

    def append_clip(clip):
        nonlocal current_time
        clips_in_order.append(clip.with_start(current_time))
        current_time += clip.duration

    append_clip(audio_intro1)
    append_clip(audio_intro2)
    append_clip(audio_guchi)
    append_clip(audio_news_start)

    for i, a in enumerate(news_audios):
        start = current_time
        append_clip(a)
        timeline.append({"index": i, "start": start, "end": current_time})

    news_ui_start = timeline[0]["start"]   # ニュースUIを表示開始するタイミング
    news_ui_end   = current_time           # ニュースUIを非表示にするタイミング

    append_clip(audio_news_end)

    cheer_start = current_time
    append_clip(audio_cheer)
    append_clip(audio_outro)

    total_duration = current_time
    final_audio    = CompositeAudioClip(clips_in_order)

    print(f"✅ 音声タイムライン計算完了。総尺: {total_duration:.2f}秒")
    return final_audio, timeline, total_duration, news_ui_start, news_ui_end, cheer_start


# ==========================================
# 6. 🎬 MoviePy 動画レンダリング
# ==========================================
def render_video(final_audio, timeline, total_duration,
                 news_ui_start, news_ui_end, cheer_start,
                 data, output_dir):
    print(f"🎬 動画のレンダリングを開始します... 総尺: {total_duration:.2f}秒")
    clips = []

    # ── ① 背景 ──
    bg_right = ColorClip(size=(1280, 720), color=(255, 255, 255)).with_duration(total_duration)
    bg_left  = ColorClip(size=(420, 720),  color=(245, 245, 245)).with_duration(total_duration)\
                   .with_position(lambda t: (0, 0))
    base_bg  = CompositeVideoClip([bg_right, bg_left], size=(1280, 720)).with_duration(total_duration)
    clips.append(base_bg)

    # ── ② ロボット画像 ──
    if os.path.exists(ROBOT_BASE_PATH):
        # ロボット画像: 高さ720pxにリサイズして右端に配置
        _robot_tmp = ImageClip(ROBOT_BASE_PATH).resized(height=720)
        _robot_w   = _robot_tmp.size[0]
        robot_clip = (_robot_tmp
                      .with_duration(total_duration)
                      .with_position(lambda t: (1280 - _robot_w, 0)))
        clips.append(robot_clip)
    else:
        print(f"⚠️ ロボット画像が見つかりません: {ROBOT_BASE_PATH}")

    # 瞬きアニメーション
    t = 4.0
    while t < total_duration:
        if os.path.exists(ROBOT_BLINK_PATH):
            _blink_tmp = ImageClip(ROBOT_BLINK_PATH).resized(height=720)
            _blink_w   = _blink_tmp.size[0]
            blink = (_blink_tmp
                     .with_start(t)
                     .with_duration(0.15)
                     .with_position(lambda t: (1280 - _blink_w, 0)))
            clips.append(blink)
        t += 4.0

    # ── ③ 常時テキスト ──
    title_clip = (TextClip(text="AI NEWS FLASH", font_size=32, color="black", font=FONT_PATH)
                  .with_position(lambda t: (40, 40))
                  .with_duration(total_duration))
    model_clip = (TextClip(text=f"Powered by {data['ai_model']}", font_size=16, color="gray", font=FONT_PATH)
                  .with_position(lambda t: (950, 40))
                  .with_duration(total_duration))
    clips.extend([title_clip, model_clip])

    # ── ④ ニュースUI（黄色ボード・見出し） ──
    ui_duration = news_ui_end - news_ui_start
    if ui_duration > 0:
        BOARD_Y = 170

        board_clip = (ColorClip(size=(360, 430), color=(247, 251, 196))
                      .with_start(news_ui_start)
                      .with_duration(ui_duration)
                      .with_position(lambda t: (30, BOARD_Y)))
        clips.append(board_clip)

        if os.path.exists(LIGHTBULB_PATH):
            icon_clip = (ImageClip(LIGHTBULB_PATH)
                         .resized(height=30)
                         .with_start(news_ui_start)
                         .with_duration(ui_duration)
                         .with_position(lambda t: (50, BOARD_Y + 22)))
            clips.append(icon_clip)

        board_title = (TextClip(text="本日のニュース", font_size=22, color="black", font=FONT_PATH)
                       .with_start(news_ui_start)
                       .with_duration(ui_duration)
                       .with_position(lambda t: (95, BOARD_Y + 25)))
        clips.append(board_title)

        # 各ニュース期間ごとに見出しを動的切り替え
        # y間隔120px・▷マーカーは別Clipに分離してはみ出し防止
        ARROW_X  = 38   # ▷のx座標
        TEXT_X   = 58   # タイトルテキストのx座標（▷の右隣）
        TEXT_W   = 310  # タイトルテキストの折り返し幅（ボード内幅330 - ▷幅20）
        Y_STEP   = 120  # ニュース間のy間隔

        for period in timeline:
            active_idx = period["index"]
            p_start    = period["start"]
            p_duration = period["end"] - period["start"]

            for text_idx, news in enumerate(data["news_list"]):
                y_pos = (BOARD_Y + 90) + (text_idx * Y_STEP)

                if text_idx == active_idx:
                    text_color = "#B22222"
                    font_size  = 18
                    # ▷マーカーを独立したClipとして配置
                    arrow_clip = (TextClip(text="▷", font_size=font_size, color=text_color, font=FONT_PATH)
                                  .with_start(p_start)
                                  .with_duration(p_duration)
                                  .with_position(lambda t, y=y_pos: (ARROW_X, y)))
                    clips.append(arrow_clip)
                else:
                    text_color = "#4A4A4A"
                    font_size  = 16

                # タイトルテキスト（▷なし・折り返しあり）
                txt_clip = (TextClip(text=news["title"], font_size=font_size, color=text_color, font=FONT_PATH,
                                     size=(TEXT_W, None), method="caption")
                            .with_start(p_start)
                            .with_duration(p_duration)
                            .with_position(lambda t, y=y_pos: (TEXT_X, y)))
                clips.append(txt_clip)

        # ── ⑤ 中央ワイプ画像（取得できた場合のみ表示） ──
        for period in timeline:
            idx       = period["index"]
            p_start   = period["start"]
            p_duration= period["end"] - period["start"]
            img_path  = data["news_list"][idx]["image_path"]

            if img_path and os.path.exists(img_path):
                wipe_clip = (ImageClip(img_path)
                             .resized(width=340)
                             .with_start(p_start)
                             .with_duration(p_duration)
                             .with_position(lambda t: (415, 170)))
                clips.append(wipe_clip)
            else:
                print(f"⚠️ ニュース{idx + 1}の画像なし。ワイプ表示をスキップします。")

    # ── 統合・レンダリング実行 ──
    video = CompositeVideoClip(clips, size=(1280, 720))
    video.audio = final_audio

    output_path = os.path.join(output_dir, "output.mp4")
    video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    print(f"🎉 動画レンダリング完了: {output_path}")
    return output_path


# ==========================================
# 7. 💾 完成音声を output_dir に保存
# ==========================================
def save_final_audio(final_audio, output_dir):
    """結合済み音声を generate-movies/YYYYMMDD/ に保存する"""
    save_path = os.path.join(output_dir, "final_audio.mp3")
    final_audio.write_audiofile(save_path)
    print(f"✅ 完成音声を保存しました: {save_path}")


# ==========================================
# 8. 📤 YouTube 限定公開アップロード
# ==========================================
def upload_to_youtube(youtube, file_path, data):
    print("📤 YouTubeへの限定公開アップロードを実行中...")

    body = {
        "snippet": {
            "title":       data["youtube_title"],
            "description": data["youtube_description"],
            "categoryId":  "25"
        },
        "status": {
            "privacyStatus": "unlisted"
        }
    }

    media    = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request  = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()

    video_id = response.get("id")
    print(f"✅ YouTubeアップロード成功。Video ID: {video_id}")
    return video_id


# ==========================================
# 9. 📝 G列（YouTube URL）書き戻し
# ==========================================
def write_back_youtube_url(sheets, row_numbers, video_id):
    """処理した3行のG列に YouTube URL を書き戻す"""
    youtube_url = f"https://youtu.be/{video_id}"
    print(f"📝 スプレッドシートのG列にYouTube URLを書き戻し中... ({youtube_url})")

    for row_num in row_numbers:
        range_notation = f"{SHEET_NAME}!G{row_num}"
        sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_notation,
            valueInputOption="RAW",
            body={"values": [[youtube_url]]}
        ).execute()
        print(f"  ✅ 行 {row_num} のG列に書き戻し完了")

    print("✅ 全行のURL書き戻しが完了しました。")


# ==========================================
# 10. 🔔 Discord Webhook 通知
# ==========================================
def send_discord_notification(video_id, data):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL が未設定のため、通知をスキップします。")
        return

    watch_url  = f"https://youtu.be/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    titles = "\n".join([f"・{n['title']}" for n in data["news_list"]])

    message = {
        "content": (
            "🤖 **【AIニュース】最新の動画レンダリングが完了しました！**\n"
            "YouTubeへ限定公開でアップロードされています。内容の最終承認を行ってください。\n\n"
            f"📰 **本日のニュース:**\n{titles}\n\n"
            f"📺 **スマホ確認用URL（リンク限定公開）:**\n{watch_url}\n\n"
            f"🛠️ **YouTube Studio 管理画面（ここから公開スイッチをONにできます）:**\n{studio_url}\n\n"
            "問題がなければ、Studioアプリからステータスを「公開」に切り替えて運用を開始してください。"
        )
    }

    res = requests.post(DISCORD_WEBHOOK_URL, json=message)
    if res.status_code == 204:
        print("🔔 Discordへの確認通知を送信しました。")
    else:
        print(f"❌ Discord通知に失敗しました。ステータス: {res.status_code}")


# ==========================================
# 11. 🏁 メイン実行コントロール
# ==========================================
def main():
    start_time = time.time()
    tmp_dir    = None

    try:
        # ── 出力ディレクトリの準備 ──
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"📁 出力ディレクトリ: {OUTPUT_DIR}")

        # ── 認証（YouTube + Sheets） ──
        youtube, sheets = get_services()

        # ── スプレッドシートからデータ取得 ──
        rows, row_numbers = fetch_target_rows(sheets)
        if rows is None:
            return  # スキップ

        # ── データ構造に変換 ──
        data = parse_rows_to_data(rows)
        print(f"📋 処理対象: {data['date_label']} {data['day_of_week']}曜日 / AIモデル: {data['ai_model']}")
        print(f"   ニュース1: {data['news_list'][0]['title']}")
        print(f"   ニュース2: {data['news_list'][1]['title']}")
        print(f"   ニュース3: {data['news_list'][2]['title']}")

        # ── Pexels 画像取得 ──
        fetch_all_images(data, OUTPUT_DIR)

        # ── 一時ディレクトリ（音声セグメント用） ──
        tmp_dir = tempfile.mkdtemp(prefix="ainews_")
        print(f"🗂️ 一時ディレクトリ: {tmp_dir}")

        # ── 音声合成 & タイムライン計算 ──
        final_audio, timeline, total_duration, news_ui_start, news_ui_end, cheer_start = \
            generate_audio_timeline(data, tmp_dir)

        # ── 完成音声を保存 ──
        save_final_audio(final_audio, OUTPUT_DIR)

        # ── 動画レンダリング ──
        output_video = render_video(
            final_audio, timeline, total_duration,
            news_ui_start, news_ui_end, cheer_start,
            data, OUTPUT_DIR
        )

        # ── YouTube アップロード ──
        video_id = upload_to_youtube(youtube, output_video, data)

        # ── G列に YouTube URL 書き戻し ──
        write_back_youtube_url(sheets, row_numbers, video_id)

        # ── Discord 通知 ──
        send_discord_notification(video_id, data)

        elapsed = time.time() - start_time
        print(f"\n🎉 全パイプライン正常終了！（処理時間: {elapsed:.2f}秒）")
        print(f"   動画: {output_video}")
        print(f"   YouTube: https://youtu.be/{video_id}")

    except Exception as e:
        print(f"\n❌ パイプライン実行中に致命的なエラーが発生しました: {e}")
        raise

    finally:
        # ── 一時ファイルを確実に削除 ──
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            print(f"🗑️ 一時ファイルを削除しました: {tmp_dir}")


if __name__ == "__main__":
    main()