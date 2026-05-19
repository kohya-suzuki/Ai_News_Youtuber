import os
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================
# 設定情報
# ==========================================
# DiscordのWebhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# テストに使う動画ファイルのパス（フォルダ内にある適当なmp4ファイル名）
TEST_VIDEO_PATH = "output.mp4" 
# YouTube APIのスコア設定（動画アップロード用の権限）
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service():
    creds = None
    # 過去に認証したことがある場合、鍵（token.json）を自動ロード
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    # 鍵がない、または有効期限切れの場合、認証をやり直す
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("認証トークンの有効期限が切れているため、自動更新します...")
            creds.refresh(Request())
        else:
            print("初回認証を開始します。ブラウザが自動的に起動しますので、ログインと許可を行ってください...")
            # ここで先ほど配置した client_secrets.json を読み込みます
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 次回からブラウザを起動しなくていいように、認証情報を token.json に保存
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("次回以降の自動ログイン用に 'token.json' を保存しました。")

    return build("youtube", "v3", credentials=creds)

def upload_test_video(youtube):
    print(f"YouTubeへの限定公開アップロードを開始します... ファイル: {TEST_VIDEO_PATH}")
    
    body = {
        "snippet": {
            "title": "【テスト】AIニュース自動生成パイプライン疎通確認",
            "description": "この動画は自動投稿システムの認証およびDiscord通知のテスト動画です。",
            "tags": ["テスト", "自動化"],
            "categoryId": "25" # ニュースと政治
        },
        "status": {
            "privacyStatus": "unlisted" # 【確定要件】リンク限定公開
        }
    }

    media = MediaFileUpload(TEST_VIDEO_PATH, chunksize=-1, resumable=True, mimetype="video/mp4")
    
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    response = request.execute()
    video_id = response.get("id")
    print(f"YouTubeへのアップロードが成功しました！ Video ID: {video_id}")
    return video_id

def send_discord_notification(video_id):
    if not DISCORD_WEBHOOK_URL or "ここに" in DISCORD_WEBHOOK_URL:
        print("エラー: DISCORD_WEBHOOK_URL が正しく設定されていません。")
        return

    # 提案2に基づき、確認用URLとYouTube Studioの管理画面URLを組み立て
    watch_url = f"https://youtu.be/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    message = {
        "content": (
            "🤖 **【AIニュース動画】最新作が完成しました！**\n"
            "YouTubeへの限定公開アップロードが正常に完了しています。最終確認を行ってください。\n\n"
            f"📺 **確認用視聴URL (リンク限定公開):**\n{watch_url}\n\n"
            f"🛠️ **YouTube Studio (ここから最終公開スイッチをONにできます):**\n{studio_url}\n\n"
            "※動画内容に問題がなければ、YouTube Studioからステータスを「公開」へ切り替えてください。"
        )
    }

    print("Discordへ通知を送信中...")
    res = requests.post(DISCORD_WEBHOOK_URL, json=message)
    if res.status_code == 204:
        print("Discordへの通知送信に成功しました！スマホを確認してください。")
    else:
        print(f"Discord通知でエラーが発生しました。ステータスコード: {res.status_code}")

def main():
    if not os.path.exists(TEST_VIDEO_PATH):
        print(f"エラー: テスト用の動画ファイル '{TEST_VIDEO_PATH}' が見つかりません。")
        print("フォルダ内に何か適当なmp4ファイルを置くか、コード内の TEST_VIDEO_PATH を書き換えてください。")
        return

    try:
        # 1. YouTube API 認証
        youtube = get_youtube_service()
        # 2. アップロード実行
        video_id = upload_test_video(youtube)
        # 3. Discordへ通知
        send_discord_notification(video_id)
        
        print("\n🎉 全ての疎通テストが正常に完了しました！")
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()