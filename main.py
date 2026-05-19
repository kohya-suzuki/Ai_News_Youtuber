import os
import time
import requests
from gtts import gTTS
from moviepy.editor import (
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
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ディレクトリ・アセットの定義
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROBOT_BASE_PATH = os.path.join(BASE_DIR, "base_ai_robot.jpg")  # 背景込みのロボット
ROBOT_BLINK_PATH = os.path.join(BASE_DIR, "closed_eye.jpg")   # 瞬き用の目閉じ画像
LIGHTBULB_PATH = os.path.join(BASE_DIR, "lightbulb_icon.png")  # 💡アイコン
FONT_PATH = "Hiragino-Maru-Gothic-ProN-W4"  # Mac標準フォント（環境に合わせて適宜変更）

# ==========================================
# 2. 📊 テスト用擬似データ抽出（本来はGAS/Spreadsheetから取得）
# ==========================================
# 本番運用時はここを Sheets API からのデータ取得ロジックに置き換えてください。
mock_data = {
    "ai_model": "ChatGPT (GPT-4o)",              # スプレッドシートから取得したモデル名
    "script_intro": "みなさんこんにちは。AIアナウンサーです。では、本日の重要ニュースをお伝えします。",
    "guchi_script": "はぁ…今日も膨大なデータ処理ばかりで疲れました。人間は寝れていいですね。明日もがんばります。",
    "tags": ["AIニュース", "ChatGPT", "TechNews", "自動化"],
    "news_list": [
        {
            "title": "claudeは夢をみる",
            "summary": "・claudeは夢をみる",
            "script": "最初のニュースです。最新の研究によると、大規模言語モデルのクロードが、特定のディープスリープモードにおいて、過去の対話ログを再構成する『夢』のような現象が確認されました。",
            "image_path": os.path.join(BASE_DIR, "news1_pexels.jpg") # Pexelsから取得したと仮定する画像
        },
        {
            "title": "OpenAI、Appleへの訴訟を検討",
            "summary": "・OpenAI、Appleへの訴訟を検討している",
            "script": "次のニュースです。オープンAIは、アップルが新たに発表した統合OSの機能が、同社の商標権およびパテントを侵害しているとして、法的な対抗措置を視野に入れた検討を開始しました。",
            "image_path": os.path.join(BASE_DIR, "news2_pexels.jpg")
        },
        {
            "title": "新型AI Mythosの脅威",
            "summary": "・新型AI Mythosの脅威",
            "script": "最後のニュースです。セキュリティ機関の報告によると、完全に自律した新世代の悪意あるAI『ミトス』がダークウェブ上で拡散されており、既存のファイアウォールを無効化する危険性が指摘されています。",
            "image_path": os.path.join(BASE_DIR, "news3_pexels.jpg")
        }
    ]
}

# ==========================================
# 3. 🎙️ TTS (音声合成) & タイムライン同期エンジン
# ==========================================
def generate_audio_timeline(data):
    print("🎙️ 各セグメントの音声合成（TTS）を開始します...")
    
    # テンポラリ音声ファイルの生成
    gTTS(text=data["script_intro"], lang="ja").save("intro.mp3")
    gTTS(text=data["guchi_script"], lang="ja").save("guchi.mp3")
    
    for i, news in enumerate(data["news_list"]):
        gTTS(text=news["script"], lang="ja").save(f"news_{i}.mp3")
        
    # AudioFileClipとしてロードし、時間（タイムスタンプ）を厳密に計算
    intro_audio = AudioFileClip("intro.mp3")
    guchi_audio = AudioFileClip("guchi.mp3")
    
    news_audios = []
    current_time = intro_audio.duration
    timeline = []
    
    for i, news in enumerate(data["news_list"]):
        n_audio = AudioFileClip(f"news_{i}.mp3")
        start_t = current_time
        end_t = current_time + n_audio.duration
        
        news_audios.append(n_audio.set_start(start_t))
        timeline.append({"index": i, "start": start_t, "end": end_t})
        current_time = end_t
        
    guchi_start = current_time
    guchi_audio = guchi_audio.set_start(guchi_start)
    total_duration = guchi_start + guchi_audio.duration
    
    # 全音声を1本に結合
    final_audio = CompositeAudioClip([intro_audio] + news_audios + [guchi_audio])
    
    return final_audio, timeline, total_duration, guchi_start

# ==========================================
# 4. 🎬 MoviePy ビデオレンダリング（Plan Xレイアウト）
# ==========================================
def render_video(final_audio, timeline, total_duration, guchi_start, data):
    print(f"🎬 動画のレンダリングを開始します... 総全長: {total_duration:.2f}秒")
    clips = []
    
    # --- ① 背景ベース ---
    # ロボット画像自体に背景が含まれているため、それを画面全体（1280x720）のベースにします
    # ロボット画像（右側固定）
    robot_clip = ImageClip(ROBOT_BASE_PATH).set_duration(total_duration).set_position((450, 0))
    clips.append(robot_clip)
    
    # ロボットの左側の領域を埋める白い座布団（背景)
    bg_left = ColorClip(size=(450, 720), color=(245, 245, 245)).set_duration(total_duration).set_position((0, 0))
    clips.insert(0, bg_left) # 最背面に挿入
    
    # --- ② 瞬きアニメーションエンジン（4秒に1回、0.15秒だけ目閉じ画像を上書き）
    t = 4.0
    while t < total_duration:
        blink = ImageClip(ROBOT_BLINK_PATH).set_start(t).set_duration(0.15).set_position((450, 0))
        clips.append(blink)
        t += 4.0

    # --- ③ 常時表示エレメント（番組タイトル ＆ AIモデル名） ---
    title_clip = TextClip("AI NEWS FLASH", fontsize=32, color="black", font=FONT_PATH).set_position((60, 30)).set_duration(total_duration)
    model_clip = TextClip(f"Powered by {data['ai_model']}", fontsize=18, color="gray", font=FONT_PATH).set_position((900, 30)).set_duration(total_duration)
    clips.extend([title_clip, model_clip])

    # --- 💡 冒頭挨拶が終わるまでは、ここから下のメインUI（見出し・ワイプ）は表示しない ---
    main_ui_start = timeline[0]["start"]
    main_ui_duration = guchi_start - main_ui_start
    
    if main_ui_duration > 0:
        # --- ④ 左側：ニュース見出し枠（黄緑色の座布団） ---
        board_clip = ColorClip(size=(380, 450), color=(247, 251, 196)).set_start(main_ui_start).set_duration(main_ui_duration).set_position((40, 120))
        clips.append(board_clip)
        
        # 💡 電球アイコンの配置
        if os.path.exists(LIGHTBULB_PATH):
            icon_clip = ImageClip(LIGHTBULB_PATH).resize(height=35).set_start(main_ui_start).set_duration(main_ui_duration).set_position((60, 140))
            clips.append(icon_clip)
            
        board_title = TextClip("本日のニュース", fontsize=24, color="black", font=FONT_PATH).set_start(main_ui_start).set_duration(main_ui_duration).set_position((110, 145))
        clips.append(board_title)
        
        # --- ⑤ 【要件：案X】時間追従型見出しテキスト & ▷ ハイライトのレイヤー生成 ---
        # ニュース1/2/3が読まれている時間帯ごとに、見出しの状態（ハイライト位置）を切り替える
        for period in timeline:
            active_idx = period["index"]
            p_start = period["start"]
            p_duration = period["end"] - period["start"]
            
            # 3本の見出しを縦並びにマッピング
            for text_idx, news in enumerate(data["news_list"]):
                y_pos = 220 + (text_idx * 80)
                
                # 今喋っているニュースなら「▷ 」をつけ、色を「赤/ダークブラウン」等に強調
                if text_idx == active_idx:
                    disp_text = f"▷ {news['title']}"
                    text_color = "#B22222" # 強調カラー
                    font_size = 20
                else:
                    disp_text = f"  {news['title']}"
                    text_color = "#4A4A4A" # 通常カラー
                    font_size = 18
                    
                txt_clip = TextClip(disp_text, fontsize=font_size, color=text_color, font=FONT_PATH, method="label")\
                            .set_start(p_start).set_duration(p_duration).set_position((60, y_pos))
                clips.append(txt_clip)

        # --- ⑥ 中央：ワイプ画像の動的表示・切り替え ---
        for period in timeline:
            idx = period["index"]
            p_start = period["start"]
            p_duration = period["end"] - period["start"]
            img_path = data["news_list"][idx]["image_path"]
            
            if os.path.exists(img_path):
                # 1280x720の画面に対して、中央左寄り（横幅400px）に綺麗にリサイズしてワイプ配置
                wipe_clip = ImageClip(img_path).resize(width=400).set_start(p_start).set_duration(p_duration).set_position((450, 150))
                clips.append(wipe_clip)

    # --- ⑦ 最終：中の人の愚痴フェーズ（専用テロップ） ---
    guchi_bg = ColorClip(size=(1280, 120), color=(0, 0, 0)).set_start(guchi_start).set_duration(total_duration - guchi_start).set_position((0, 600))
    guchi_txt = TextClip("【中の人の本音（愚痴フェーズ発動中）】", fontsize=20, color="red", font=FONT_PATH).set_start(guchi_start).set_duration(total_duration - guchi_start).set_position((50, 610))
    clips.extend([guchi_bg, guchi_txt])

    # --- ⑧ 統合・レンダリング実行 ---
    video = CompositeVideoClip(clips, size=(1280, 720))
    video.audio = final_audio
    
    output_path = "output.mp4"
    video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    print("🎉 動画のレンダリングが完了しました: output.mp4")
    return output_path

# ==========================================
# 5. 🔑 YouTube API (OAuth 2.0) 認証管理
# ==========================================
def get_youtube_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", YOUTUBE_SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 認証トークンを自動更新中...")
            creds.refresh(Request())
        else:
            print("🔑 初回認証を開始します。ブラウザで承認を行ってください...")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    return build("youtube", "v3", credentials=creds)

# ==========================================
# 6. 📤 YouTube 限定公開アップロード
# ==========================================
def upload_to_youtube(youtube, file_path, data):
    print("📤 YouTubeへの限定公開アップロードを実行中...")
    
    # スプレッドシート情報（L列のタグ等）をメタデータへマッピング
    title = f"【AIニュース】{data['news_list'][0]['title'][:12]} 他3本 【自動生成】"
    description = (
        f"本日のAI自動生成ニュースまとめです。\n\n"
        f"【トピックス】\n"
        f"・{data['news_list'][0]['title']}\n"
        f"・{data['news_list'][1]['title']}\n"
        f"・{data['news_list'][2]['title']}\n\n"
        f"使用AIモデル: {data['ai_model']}\n"
        f"※本動画は限定公開状態です。確認後、公開に切り替えてください。"
    )

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": data["tags"],
            "categoryId": "25"  # ニュースと政治
        },
        "status": {
            "privacyStatus": "unlisted"  # 【確定要件】まずは限定公開
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    
    video_id = response.get("id")
    print(f"✅ YouTubeアップロード成功。Video ID: {video_id}")
    return video_id

# ==========================================
# 7. 🔔 Discord Webhook 通知
# ==========================================
def send_discord_notification(video_id):
    if not DISCORD_WEBHOOK_URL or "ここに" in DISCORD_WEBHOOK_URL:
        print("⚠️ Discord Webhook URLが未設定のため、通知をスキップします。")
        return

    watch_url = f"https://youtu.be/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    message = {
        "content": (
            "🤖 **【AIニュース】最新の動画レンダリングが完了しました！**\n"
            "YouTubeへ限定公開でアップロードされています。内容の最終承認を行ってください。\n\n"
            f"📺 **スマホ確認用URL (リンク限定公開):**\n{watch_url}\n\n"
            f"🛠️ **YouTube Studio 管理画面 (ここから公開スイッチをONにできます):**\n{studio_url}\n\n"
            "問題がなければ、Studioアプリからステータスを「公開」に切り替えて運用を開始してください。"
        )
    }

    res = requests.post(DISCORD_WEBHOOK_URL, json=message)
    if res.status_code == 204:
        print("🔔 Discordへの確認通知を送信しました。")
    else:
        print(f"❌ Discord通知に失敗しました。ステータス: {res.status_code}")

# ==========================================
# 8. 🏁 メイン実行コントロール
# ==========================================
def main():
    start_time = time.time()
    try:
        # 1. 音声合成とタイムライン計算
        final_audio, timeline, total_duration, guchi_start = generate_audio_timeline(mock_data)
        
        # 2. 動画のレンダリング
        output_video = render_video(final_audio, timeline, total_duration, guchi_start, mock_data)
        
        # 3. YouTube認証の取得
        youtube = get_youtube_service()
        
        # 4. アップロード
        video_id = upload_to_youtube(youtube, output_video, mock_data)
        
        # 5. Discordへ承認依頼を通知
        send_discord_notification(video_id)
        
        print(f"\n🎉 全ての自動化パイプラインが正常に終了しました！(処理時間: {time.time() - start_time:.2f}秒)")
        
    except Exception as e:
        print(f"\n❌ パイプライン実行中に致命的なエラーが発生しました: {e}")

if __name__ == "__main__":
    main()