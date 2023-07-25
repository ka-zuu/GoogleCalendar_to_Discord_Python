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
    # 外部ファイルから設定を読み込み、変数設定
    load_dotenv()
    # カレンダーID、Webhook URL、S3エンドポイントを取得する
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

    # カレンダーIDの数だけループ
    for calendar_id in calendar_ids:
        # カレンダーIDから予定を取得
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=today,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(start, event["summary"])


if __name__ == "__main__":
    main()
