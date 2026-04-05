


import os
import re
import requests
import json
from moviepy import ImageClip, TextClip, CompositeVideoClip, ColorClip, vfx
from PIL import Image, ImageDraw
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# --- 設定（微調整ポイント） ---
PEXELS_API_KEY = os.getenv("N86mofyZkk3D1qcI5MsdGK43NCflaHGy7yV2NfR2r62y7KgIMdAXhV2b")
SPREADSHEET_ID = os.getenv("1o4XVvg34BCCNyuIp5_QwZadkgkfu4rWeog50qr3Lnoo")
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# ロボットの目の座標 (base_image.jpg の左上からのピクセル数)
EYE_LEFT_POS = (740, 435) 
EYE_RIGHT_POS = (775, 435)
EYE_SIZE = 12

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
COL_WIDTH = SCREEN_WIDTH // 3

# --- 1. 閉じ目画像を生成 ---
def create_closed_eye_image(base_img_path):
    with Image.open(base_img_path) as img:
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        bg_color = img.getpixel((EYE_LEFT_POS[0], EYE_LEFT_POS[1] - 30)) 
        draw.ellipse([EYE_LEFT_POS[0]-EYE_SIZE, EYE_LEFT_POS[1]-EYE_SIZE, 
                      EYE_LEFT_POS[0]+EYE_SIZE, EYE_LEFT_POS[1]+EYE_SIZE], fill=bg_color)
        draw.ellipse([EYE_RIGHT_POS[0]-EYE_SIZE, EYE_RIGHT_POS[1]-EYE_SIZE, 
                      EYE_RIGHT_POS[0]+EYE_SIZE, EYE_RIGHT_POS[1]+EYE_SIZE], fill=bg_color)
        img.save("closed_eye.jpg")
    return "closed_eye.jpg"

# --- 2. Pexels画像取得 ---
def get_pexels_image(keyword, index):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/v1/search?query={keyword}&per_page=1"
    try:
        res = requests.get(url, headers=headers).json()
        img_url = res['photos'][0]['src']['large']
        img_data = requests.get(img_url).content
        path = f"news_{index}.jpg"
        with open(path, 'wb') as f:
            f.write(img_data)
        return path
    except:
        return "base_image.jpg" # 失敗時はデフォルト

# --- 3. スクリプト解析 ---
def parse_script(full_script):
    parts = re.split(r'\[WAIT(\d+\.?\d*)\]', full_script)
    clean_text = ""
    timing_points = [0.0]
    current_time = 0
    
    # 読み上げ速度: 1秒間に5文字と仮定してタイミングを計算
    for i in range(0, len(parts), 2):
        text_part = parts[i]
        clean_text += text_part
        duration = len(text_part) / 5.0
        current_time += duration
        timing_points.append(current_time)
        if i + 1 < len(parts):
            wait_time = float(parts[i+1])
            current_time += wait_time
            timing_points.append(current_time)
            
    return clean_text, timing_points, current_time

# --- 4. メイン合成 ---
def create_video(row_data):
    # row_data: [取得日時, 動画ID, AIモデル名, 台本, 要約リスト, 画像KW, 背景パス, ...]
    ai_name = row_data[2]
    full_script = row_data[3]
    summaries = row_data[4].split('\n')
    keywords = row_data[5].split(',')
    
    # 修正ポイント：特定のファイル名ではなく、共通のベース画像を指定
    bg_path = "base_ai_robot.jpg" 

    if not os.path.exists(bg_path):
        # 万が一ファイル名が違っても動くように、以前の base_image.jpg も予備で残す
        bg_path = "base_image.jpg" if os.path.exists("base_image.jpg") else ""

    if not bg_path:
        raise Exception("背景画像 (base_ai_robot.jpg) が見つかりません。")

    clean_text, timings, total_duration = parse_script(full_script)
    
    # 背景（じわじわズーム）
    bg = ImageClip(bg_path).with_duration(total_duration).with_effects([vfx.Resize(lambda t: 1 + 0.02 * t / total_duration)])

    # 瞬き（ベース画像を使って閉じ目を作成）
    closed_path = create_closed_eye_image(bg_path)

    # Powered by (頭上)
    pwr_text = TextClip(text=f"Powered by {ai_name}", font_size=30, color='gray', font=FONT_PATH).with_position((720, 350)).with_duration(total_duration)

    # 左側：要約リスト / 中央：関連画像
    news_elements = []
    # WAITタグの並びからニュース1,2,3の開始時間を特定 (テンプレートの[WAIT]位置に依存)
    # 挨拶[WAIT0.5](1) -> 愚痴[WAIT1.0](3) -> ニュース1開始
    news_starts = [timings[4], timings[8], timings[12]] 
    
    for i, summary in enumerate(summaries[:3]):
        y_pos = 150 + (i * 120)
        start_t = news_starts[i]
        end_t = news_starts[i+1] if i < 2 else total_duration

        # 通常の要約文
        base_txt = TextClip(text=f"  {summary}", font_size=24, color='white', font=FONT_PATH, size=(COL_WIDTH-60, None), method='caption').with_position((30, y_pos)).with_duration(total_duration).with_opacity(0.4)
        news_elements.append(base_txt)
        
        # 強調（黄色 + ▶︎）
        active_txt = TextClip(text=f"▶ {summary}", font_size=24, color='yellow', font=FONT_PATH, size=(COL_WIDTH-60, None), method='caption').with_position((30, y_pos)).with_start(start_t).with_duration(end_t - start_t)
        news_elements.append(active_txt)

        # 中央画像
        img_path = get_pexels_image(keywords[i].strip(), i)
        news_img = ImageClip(img_path).with_size(width=COL_WIDTH-60).with_position('center').with_start(start_t).with_duration(end_t - start_t).with_effects([vfx.FadeIn(0.5)])
        news_elements.append(news_img)

    final_video = CompositeVideoClip([bg] + blink_clips + [pwr_text] + news_elements, size=(SCREEN_WIDTH, SCREEN_HEIGHT))
    final_video.write_videofile("output.mp4", fps=24, codec="libx264")

# --- 5. スプレッドシート連携 ---
def main():
    # 認証
    creds_json = json.loads(os.getenv("GCP_SA_KEY"))
    creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    
    # 2行目を取得
    range_name = "Main_Scripts!A2:G2"
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
    rows = result.get("values", [])
    
    if not rows:
        print("No data found.")
        return

    create_video(rows[0])

if __name__ == "__main__":
    main()