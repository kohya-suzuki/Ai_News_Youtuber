
import os
import json
import requests
import datetime
from moviepy import ImageClip, TextClip, CompositeVideoClip
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# --- 環境設定 ---
# 1. スプレッドシートIDをあなたのものに書き換えてください
SPREADSHEET_ID = "1o4XVvg34BCCNyuIp5_QwZadkgkfu4rWeog50qr3Lnoo" # スプレッドシートのURLにある文字列
# 2. ImageMagickのパス設定（MoviePy v2.x用）
os.environ["IMAGEMAGICK_BINARY"] = "/usr/bin/convert"

FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansJP/NotoSansJP-Bold.ttf"
FONT_PATH = "NotoSansJP-Bold.ttf"

def setup_assets():
    """日本語フォントをダウンロード"""
    if not os.path.exists(FONT_PATH):
        print("Downloading Japanese font...")
        response = requests.get(FONT_URL)
        with open(FONT_PATH, 'wb') as f:
            f.write(response.content)

def get_script_from_sheets():
    """スプレッドシートから今日の台本を取得"""
    info = json.loads(os.environ.get("GCP_SA_KEY"))
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    service = build('sheets', 'v4', credentials=creds)
    
    # A列〜F列を取得
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='台本一覧!A1:F20').execute()
    rows = result.get('values', [])
    
    # 日本時間 (UTC+9) で曜日を判定
    day_labels = ["月", "火", "水", "木", "金", "土", "日"]
    now_jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_label = day_labels[now_jst.weekday()]
    
    print(f"Searching for: {today_label}")

    for row in rows:
        if len(row) > 0 and row[0] == today_label:
            script = row[3] # D列: 台本
            print(f"Found script for {today_label}")
            return script
    raise ValueError(f"シートに '{today_label}' という曜日が見つかりません。")

def create_video(script_text):
    """動画ファイルを合成"""
    bg_image = "base_image.jpg"
    
    # 画像がない場合の予備処理
    if not os.path.exists(bg_image):
        from PIL import Image
        print("base_image.jpg not found. Creating placeholder...")
        img = Image.new('RGB', (1280, 720), color=(30, 30, 30))
        img.save(bg_image)

    # 背景設定
    clip = ImageClip(bg_image).with_duration(10)
    
    # テキスト設定（日本語フォント指定）
    txt_clip = TextClip(
        text=script_text,
        font_size=40,
        color='white',
        font=FONT_PATH,
        method='caption',
        size=(1100, None)
    ).with_duration(10).with_position('center')
    
    video = CompositeVideoClip([clip, txt_clip])
    video.write_videofile("output.mp4", fps=24, codec="libx264")
    print("Video creation successful: output.mp4")

if __name__ == "__main__":
    setup_assets()
    try:
        script = get_script_from_sheets()
        create_video(script)
    except Exception as e:
        print(f"Error occurred: {e}")
        exit(1)