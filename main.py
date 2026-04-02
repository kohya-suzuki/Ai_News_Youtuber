
import os
import json
import requests
import datetime
from moviepy import ImageClip, TextClip, CompositeVideoClip
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
# OSにインストールしたNoto Sans CJKのパスを指定
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# --- 環境設定 ---
SPREADSHEET_ID = "1o4XVvg34BCCNyuIp5_QwZadkgkfu4rWeog50qr3Lnoo" # スプレッドシートのURLにある文字列
# 2. ImageMagickのパス設定（MoviePy v2.x用）
os.environ["IMAGEMAGICK_BINARY"] = "/usr/bin/convert"

FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/unhinted/otf/NotoSansJP/NotoSansJP-Bold.otf"
FONT_PATH = "NotoSansJP-Bold.otf"

def setup_assets():
    pass

def create_video(script_text):
    # テキスト設定
    txt_clip = TextClip(
        text=script_text,
        font_size=40,
        color='white',
        font=FONT_PATH, # OSのフォントを参照
        method='caption',
        size=(1100, None)
    ).with_duration(10).with_position('center')

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
        # A列が一致し、かつD列(index 3)までデータが存在するかチェック
        if len(row) > 3 and row[0] == today_label:
            script = row[3] # D列: 台本
            if script: # 台本が空文字でないか
                print(f"Found script for {today_label}")
                return script
    
    # 見つからない場合の詳細ログ
    print(f"Debug: Rows found in sheet: {rows}")
    raise ValueError(f"シートの '{today_label}' 行に台本(D列)が見つかりません。GASは実行されましたか？")

def create_video(script_text):
    # --- フォントパスの確定 ---
    # Ubuntuの標準的なNoto Sans CJKのパスを複数候補に挙げます
    possible_fonts = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "NotoSansCJK-Regular" # 名前指定
    ]
    font_to_use = None
    for f in possible_fonts:
        if os.path.exists(f):
            font_to_use = f
            break
    
    if not font_to_use:
        # 万が一見つからない場合は、システムフォントに任せる（エラー回避）
        font_to_use = "DejaVu-Sans-Book"
        print("Warning: Noto Font not found, using fallback.")
    
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
    # create_video 関数内の txt_clip 部分
    txt_clip = TextClip(
        text=script_text,
        font_size=40,
        color='white',
        font=font_to_use, # 確定したパスを使用
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