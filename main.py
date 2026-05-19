import os
import re
import requests
import json
from moviepy import ImageClip, TextClip, CompositeVideoClip, vfx
from PIL import Image, ImageDraw
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from gtts import gTTS

# --- 設定（微調整ポイント） ---
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# Mac用の日本語フォントパス（ヒラギノ角ゴ W6）
FONT_PATH = "/System/Library/Fonts/Hints/Hiragino Sans GB W6.otf" 
if not os.path.exists(FONT_PATH):
    FONT_PATH = "Arial" # 万が一無い場合のフォールバック

# ロボットの目の座標 (base_ai_robot.jpg の左上からのピクセル数)
EYE_LEFT_POS = (740, 435) 
EYE_RIGHT_POS = (775, 435)
EYE_SIZE = 12

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# --- 1. 閉じ目画像を生成 ---
def create_closed_eye_image(base_img_path):
    closed_path = "closed_eye.jpg"
    if os.path.exists(closed_path):
        return closed_path
        
    with Image.open(base_img_path) as img:
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        # 目の少し上の色をサンプリングして塗りつぶす（擬似的に目を閉じる）
        bg_color = img.getpixel((EYE_LEFT_POS[0], EYE_LEFT_POS[1] - 20)) 
        draw.ellipse([EYE_LEFT_POS[0]-EYE_SIZE, EYE_LEFT_POS[1]-EYE_SIZE, 
                      EYE_LEFT_POS[0]+EYE_SIZE, EYE_LEFT_POS[1]+EYE_SIZE], fill=bg_color)
        draw.ellipse([EYE_RIGHT_POS[0]-EYE_SIZE, EYE_RIGHT_POS[1]-EYE_SIZE, 
                      EYE_RIGHT_POS[0]+EYE_SIZE, EYE_RIGHT_POS[1]+EYE_SIZE], fill=bg_color)
        img.save(closed_path)
    return closed_path

# --- 2. Pexels画像取得 ---
def get_pexels_image(keyword):
    if not PEXELS_API_KEY:
        print("警告: PEXELS_API_KEY が設定されていません。デフォルト画像を使用します。")
        return "base_ai_robot.jpg"
        
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        img_url = res['photos'][0]['src']['large']
        img_data = requests.get(img_url).content
        path = "downloaded_news.jpg"
        with open(path, 'wb') as f:
            f.write(img_data)
        return path
    except Exception as e:
        print(f"Pexels画像取得失敗: {e}。デフォルト画像を使用します。")
        return "base_ai_robot.jpg"

# --- 3. 自動音声の生成と時間計測 (gTTS) ---
def generate_voice_and_duration(full_script):
    # [WAIT0.5] や [WAIT1.0] などのタグを除去してピュアな読み上げテキストを作る
    clean_text = re.sub(r'\[.*?\]', '', full_script)
    
    voice_filename = "news_voice.mp3"
    print("音声合成エンジン(gTTS)を実行中...")
    
    # Googleの音声合成を呼び出してMP3として保存 (日本語: lang='ja')
    tts = gTTS(text=clean_text, lang='ja', slow=False)
    tts.save(voice_filename)
    
    # 出来上がった音声ファイルの「正確な長さ」をMoviePyを使って取得する
    from moviepy import AudioFileClip
    audio_clip = AudioFileClip(voice_filename)
    actual_duration = audio_clip.duration
    audio_clip.close() # 読み込みを閉じる
    
    print(f"音声ファイルの作成が完了しました。実時間: {actual_duration:.1f} 秒")
    return voice_filename, actual_duration

# --- 4. メイン動画合成 ---
def create_video(row_data):
    # 列順定義 (A:日時, B:曜日, C:モデル, D:台本, E:要約, F:見出し, G:画像KW, H:YouTube, I:タイトル, J:元URL, K:愚痴)
    ai_name = row_data[2]
    full_script = row_data[3]
    summary_text = row_data[4]
    headline_text = row_data[5]
    image_keyword = row_data[6]
    complaint_text = row_data[10] if len(row_data) > 10 else "エンジニアの独り言"

    bg_path = "base_ai_robot.jpg"
    if not os.path.exists(bg_path):
        raise Exception(f"背景画像 {bg_path} がディレクトリに見つかりません。")

    # 【変更点】実際に音声を生成し、そのファイルの長さをもとに動画を作る
    voice_file, total_duration = generate_voice_and_duration(full_script)

    # 背景（じわじわズーム）
    bg = ImageClip(bg_path).with_duration(total_duration).with_effects([
        vfx.Resize(lambda t: 1 + 0.01 * t / total_duration)
    ])

    # 瞬きロジック (4秒に1回、0.15秒間目を閉じる)
    closed_path = create_closed_eye_image(bg_path)
    blink_clips = []
    blink_interval = 4.0
    blink_duration = 0.15
    
    t = 2.0
    while t < total_duration:
        blink = ImageClip(closed_path).with_start(t).with_duration(blink_duration)
        blink_clips.append(blink)
        t += blink_interval

    # AIモデル名表示 (ロボットの頭上付近)
    pwr_text = TextClip(text=f"Powered by {ai_name}", font_size=24, color='gray', font=FONT_PATH)\
        .with_position((680, 320)).with_duration(total_duration)

    # 画面上部：核心を突く1文（要約リスト）
    summary_clip = TextClip(text=summary_text, font_size=32, color='white', font=FONT_PATH, size=(1200, None), method='caption')\
        .with_position(('center', 40)).with_duration(total_duration)

    # 画面左側：短い見出し
    headline_clip = TextClip(text=f"【{headline_text}】", font_size=40, color='yellow', font=FONT_PATH, size=(400, None), method='caption')\
        .with_position((50, 200)).with_duration(total_duration)

    # 画面中央：Pexelsから取得したニュース関連画像
    img_path = get_pexels_image(image_keyword)
    news_img = ImageClip(img_path)\
    .resized(width=450)\
    .with_position(('center', 180))\
    .with_duration(total_duration)\
    .with_effects([vfx.FadeIn(0.5)])
    
    # 画面下部：エンジニアの愚痴（後半10秒間だけ表示する演出）
    complaint_start = max(0.0, total_duration - 10.0)
    complaint_clip = TextClip(text=f"中の人の愚痴:\n{complaint_text}", font_size=24, color='orange', font=FONT_PATH, size=(1000, None), method='caption')\
        .with_position(('center', 600)).with_start(complaint_start).with_duration(total_duration - complaint_start)

    # 【変更点】生成した音声ファイルをMoviePyのオーディオとして読み込む
    from moviepy import AudioFileClip
    audio_clip = AudioFileClip(voice_file)

    # 全てをレイヤーとして重ね合わせ
    clips = [bg] + blink_clips + [pwr_text, summary_clip, headline_clip, news_img, complaint_clip]
    final_video = CompositeVideoClip(clips, size=(SCREEN_WIDTH, SCREEN_HEIGHT))
    
    # 【変更点】動画に音声をセットする
    final_video = final_video.with_audio(audio_clip)
    
    output_filename = "output.mp4"
    print("動画・音声の統合エンコードを開始します...")
    
    # 【変更点】音声あり(audio=True)で出力し、aac形式でエンコード
    final_video.write_videofile(
        output_filename, 
        fps=24, 
        codec="libx264", 
        audio=True, 
        audio_codec="aac"
    )
    
    # メモリ解放
    audio_clip.close()
    print(f"音声付き動画が正常に出力されました: {output_filename}")

# --- 5. スプレッドシート連携 ---
def main():
    # 認証情報の読み込み
    gcp_key_env = os.getenv("GCP_SA_KEY")
    if not gcp_key_env:
        print("エラー: GCP_SA_KEY 環境変数が設定されていません。")
        return
        
    try:
        creds_json = json.loads(gcp_key_env)
    except json.JSONDecodeError:
        print("エラー: GCP_SA_KEY のJSONデコードに失敗しました。")
        return

    creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    
    # A2からK2までの11列（最新の1行分）を取得
    range_name = "Main_Scripts!A2:K2"
    print("スプレッドシートから最新ニュースを取得中...")
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    rows = result.get("values", [])
    
    if not rows:
        print("データが見つかりませんでした。")
        return

    create_video(rows[0])

if __name__ == "__main__":
    main()