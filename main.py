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
import requests


def main():
    # 引数をチェック。足りなければsummary扱い
    if len(sys.argv) < 2:
        sys.argv.append("summary")

    # 外部ファイルから設定を読み込み、変数設定する
    # ファイルがなければ終了
    if not os.path.exists("config.json"):
        print("config.jsonがありません。")
        sys.exit(1)
    # ファイルが不正なら終了
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except JSONDecodeError:
        print("config.jsonが不正です。")
        sys.exit(1)
    # カレンダーID、Webhook URL、S3エンドポイントを取得する
    calendar_ids = config["calendar_ids"]
    discord_webhook_url = config["discord_webhook_url"]
    s3_endpoint = config["s3_endpoint"]

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
    # 保存されているsyncTokenがあれば取得する
    # ファイルがない場合は、初回として扱う
    if not os.path.exists("synctoken.json"):
        sync_token_json = None
    try:
        with open("synctoken.json", "r") as f:
            st = json.load(f)
        sync_token_json = st["sync_token"]
    except JSONDecodeError:
        sync_token_json = None

    # カレンダーIDの数だけループ
    for calendar_id in calendar_ids:
        # カレンダーIDのsync_tokenがあれば、それを使って予定の差分を取得
        # なければ、全件取得
        if sync_token_json:
            for calendar in sync_token_json["calendars"]:
                if calendar["calendar_id"] == calendar_id:
                    sync_token = calendar["sync_token"]
                    break
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    syncToken=sync_token,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        else:
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=datetime.datetime.now()
                    .replace(hour=0, minute=0, second=0, microsecond=0)
                    .isoformat()
                    + "+09:00",
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        events = events_result.get("items", [])

        # 予定がなければ、次のカレンダーIDへ
        if not events:
            continue

        # 予定があれば、差分の文字列を整形する
        change = "【" + calendar_id + "】\n"
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            change += start[11:16] + " " + event["summary"] + "\n"

        # 空行を追加
        change += "\n"

    # 一覧を返す
    return change


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
