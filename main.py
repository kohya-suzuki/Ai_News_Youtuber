import os
import json
import requests
import gdown
import datetime
from moviepy import ImageClip, TextClip, CompositeVideoClip
# --- MoviePy v2.x 用の設定 ---
# ImageMagickのパスを環境変数に直接セットします
os.environ["IMAGEMAGICK_BINARY"] = "/usr/bin/convert"
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime



# --- 設定 ---
SPREADSHEET_ID = "1o4XVvg34BCCNyuIp5_QwZadkgkfu4rWeog50qr3Lnoo" # スプレッドシートのURLにある文字列
BUCKET_NAME = "youtube-ai-news-resouses"
FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansJP/NotoSansJP-Bold.ttf"
FONT_PATH = "NotoSansJP-Bold.ttf"

def setup_assets():
    # 日本語フォントがないと文字化けするのでダウンロード
    if not os.path.exists(FONT_PATH):
        print("Downloading Japanese font...")
        response = requests.get(FONT_URL)
        with open(FONT_PATH, 'wb') as f:
            f.write(response.content)

def get_script_from_sheets():
    # GitHub Secretsに登録したGCP_SA_KEY(JSON)を使ってシートを読み取る
    info = json.loads(os.environ.get("GCP_SA_KEY"))
    creds = Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    service = build('sheets', 'v4', credentials=creds)
    
    # シートのデータを取得（A列〜F列）
    range_name = 'シート1!A1:F10'
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    rows = result.get('values', [])
    
    # 今日の曜日を取得
    day_labels = ["日", "月", "火", "水", "木", "金", "土"]
    today_index = datetime.datetime.now().weekday()
    today_label = day_labels[today_index]
    # today_label = day_labels[datetime.now().weekday() + 1] # Pythonは月曜=0のため調整
    if datetime.now().weekday() == 6: today_label = "日" # 日曜の調整
    print(f"Targeting day: {today_label}") # ログで確認用

    for row in rows:
        if row[0] == today_label:
            return row[3] # D列（台本）を返す
    return "台本が見つかりませんでした。"

from moviepy.config import change_settings
change_settings({"IMAGEMAGICK_BINARY": r"/usr/bin/convert"})

def create_video(script_text):
    # 背景画像はGitHubに上げておくか、GCSから落とす必要があります。
    # ここでは仮にカレントディレクトリにある想定です。
    bg_image = "base_image.jpg" 
    
    if not os.path.exists(bg_image):
        # 画像がない場合、黒背景で代用（テスト用）
        from PIL import Image
        img = Image.new('RGB', (1280, 720), color = (73, 109, 137))
        img.save(bg_image)
    clip = ImageClip(bg_image).set_duration(15)
    
    # 日本語フォントを指定して文字を合成
    txt_clip = TextClip(
        script_text, 
        fontsize=40, 
        color='white', 
        font=FONT_PATH, 
        method='caption', 
        size=(1100, None),
        align='Center'
    ).set_pos('center').set_duration(15)
    
    video = CompositeVideoClip([clip, txt_clip])
    video.write_videofile("output.mp4", fps=24, codec="libx264")

if __name__ == "__main__":
    setup_assets()
    script = get_script_from_sheets()
    print(f"Creating video for: {script[:20]}...")
    create_video(script)