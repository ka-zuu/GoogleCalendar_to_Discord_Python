# Googleカレンダーから予定を取得して、Discordに投稿する
# 1. 毎朝1回、サマリを送信する
# 2. 30分に1回、予定の変更を送信する

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import datetime
import sys
import json
import os
from dotenv import load_dotenv


def main():
    # カレンダーID、Webhook URL、S3エンドポイントを取得する
    load_dotenv()
    calendar_ids = os.getenv("calendar_ids").split(",")
    discord_webhook_url = os.getenv("discord_webhook_url")
    s3_endpoint = os.getenv("s3_endpoint")

    # 今日の日付
    today = (
        datetime.datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
        + "+09:00"
    )

    # Googleの認証情報を取得してオブジェクト作成
    creds = Credentials.from_service_account_file(
        "credentials.json", scopes=["https://www.googleapis.com/auth/calendar.events"]
    )
    service = build("calendar", "v3", credentials=creds)

    # 引数によって処理を分岐
    if sys.argv[1] == "summary":
        # カレンダーから今日の予定を取得して、Discordに送信するための要約を作成
        message = get_summary(service, calendar_ids)
    elif sys.argv[1] == "change":
        # カレンダーから予定の差分を取得して、Discordに送信するための一覧を作成
        message = get_change(service, calendar_ids)

    # Discordに送信
    #send_discord(message, discord_webhook_url)
    print(message)


# カレンダーから今日の予定を取得して、要約を作成する関数
def get_summary(service, calendar_ids):
    summary = ""
    # カレンダーIDの数だけループ
    for calendar_id in calendar_ids:
        # カレンダーIDから予定リストを取得
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=datetime.datetime.now()
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
                + "+09:00",
                timeMax=datetime.datetime.now()
                .replace(hour=23, minute=59, second=59, microsecond=0)
                .isoformat()
                + "+09:00",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        summary += "【" + calendar_id + "】\n"

        # 予定がなければ、次のカレンダーIDへ
        if not events:
            summary += "予定はありません。\n\n"
            continue

        # 予定があれば、要約を作成
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary += start[11:16] + " " + event["summary"] + "\n"

        # 空行を追加
        summary += "\n"

    # 要約を返す
    return summary


# カレンダーから予定の差分を取得して、一覧を作成する関数
def get_change(service, calendar_ids):
    changes = {"added": [], "deleted": []}
    sync_tokens = {}

    # 保存されているsyncTokenがあれば取得する
    if os.path.exists("synctoken.json"):
        with open("synctoken.json", "r") as f:
            sync_tokens = json.load(f)

    # カレンダーIDの数だけループ
    for calendar_id in calendar_ids:
        page_token = None
        while True:
            # カレンダーIDのsync_tokenがあれば、それを使って予定の差分を取得
            # なければ、全件取得
            if calendar_id in sync_tokens:
                events_result = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        syncToken=sync_tokens[calendar_id],
                        singleEvents=True,
                        orderBy="startTime",
                        pageToken=page_token,
                    )
                    .execute()
                )
            else:
                events_result = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin="1970-01-01T00:00:00Z",
                        singleEvents=True,
                        orderBy="startTime",
                        pageToken=page_token,
                    )
                    .execute()
                )

            # 追加された予定を取得
            for event in events_result.get("items", []):
                if "status" in event and event["status"] == "cancelled":
                    changes["deleted"].append(event)
                else:
                    changes["added"].append(event)

            # 次のページがあれば、ページトークンを更新
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break

        # syncTokenを保存
        sync_tokens[calendar_id] = events_result.get("nextSyncToken")

    # syncTokenをファイルに保存
    with open("synctoken.json", "w") as f:
        json.dump(sync_tokens, f)

    # 追加された予定を文字列化
    added_events = "追加された予定：\n"
    for event in changes["added"]:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        added_events += f"{start},{end},{event['summary']}\n"

    # 削除された予定を文字列化
    deleted_events = "削除された予定：\n"
    for event in changes["deleted"]:
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        deleted_events += f"{start},{end},{event['summary']}\n"

    # 一覧を返す
    return added_events + "\n" + deleted_events


# Discordに送信する関数
def send_discord(message, discord_webhook_url):
    # メッセージがなければ終了
    if not message:
        return

    # メッセージを整形
    payload = {"content": message}

    # Discordに送信
    try:
        requests.post(discord_webhook_url, data=json.dumps(payload))
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
