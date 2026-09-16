import os
import base64

from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
]

CREDENTIALS_FILE = "credentials/credentials.json"
TOKEN_FILE = "tokens/token.json"

PROCESSED_LABEL = "BOOKING_AUTOMATED"


def get_gmail_service():

    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            print("Refreshing Google OAuth token...")

            creds.refresh(Request())

        else:

            print("Starting Google OAuth...")

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES
            )

            os.makedirs(
                "tokens",
                exist_ok=True
            )

            creds = flow.run_local_server(
                host="127.0.0.1",
                bind_addr="0.0.0.0",
                port=8080,
                open_browser=False,
                authorization_prompt_message=(
                    "\n\n"
                    "Open this URL in your browser:\n\n"
                    "{url}\n\n"
                ),
                success_message=(
                    "Authentication successful. "
                    "You can close this browser window."
                ),
            )

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

        print("OAuth token saved.")

    return build(
        "gmail",
        "v1",
        credentials=creds
    )


def get_or_create_processed_label(service):

    labels = (
        service.users()
        .labels()
        .list(
            userId="me"
        )
        .execute()
        .get(
            "labels",
            []
        )
    )

    for label in labels:

        if label["name"] == PROCESSED_LABEL:
            return label["id"]

    print(
        f"Creating Gmail label: {PROCESSED_LABEL}"
    )

    label = (
        service.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": PROCESSED_LABEL,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )

    return label["id"]


def get_new_booking_emails(
    service,
    label_id
):

    query = (
        'subject:RENTACAR '
        'is:unread '
        f'-label:{PROCESSED_LABEL}'
    )

    result = (
        service.users()
        .messages()
        .list(
            userId="me",
            q=query
        )
        .execute()
    )

    messages = result.get(
        "messages",
        []
    )

    return messages, label_id

def get_email(
    service,
    message_id
):

    return (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full"
        )
        .execute()
    )


def decode_body(data):

    return base64.urlsafe_b64decode(
        data
    ).decode(
        "utf-8",
        errors="replace"
    )


def extract_email_content(message):

    payload = message.get(
        "payload",
        {}
    )

    headers = payload.get(
        "headers",
        []
    )

    header_map = {
        h["name"].lower(): h["value"]
        for h in headers
    }

    sender = header_map.get(
        "from",
        ""
    )

    subject = header_map.get(
        "subject",
        ""
    )

    message_id = header_map.get(
        "message-id",
        ""
    )

    references = header_map.get(
        "references",
        ""
    )

    body = extract_body(
        payload
    )

    return {
        "sender": sender,
        "subject": subject,
        "body": body,
        "message_id": message_id,
        "references": references,
    }


def extract_body(payload):

    body = payload.get(
        "body",
        {}
    )

    if body.get("data"):

        return decode_body(
            body["data"]
        )

    parts = payload.get(
        "parts",
        []
    )

    for part in parts:

        mime_type = part.get(
            "mimeType"
        )

        if mime_type == "text/plain":

            data = (
                part.get("body", {})
                .get("data")
            )

            if data:

                return decode_body(
                    data
                )

        if part.get("parts"):

            nested_body = extract_body(
                part
            )

            if nested_body:
                return nested_body

    return ""


def mark_as_processed(
    service,
    message_id,
    label_id
):

    (
        service.users()
        .messages()
        .modify(
            userId="me",
            id=message_id,
            body={
                "addLabelIds": [
                    label_id
                ],
                "removeLabelIds": [
                    "UNREAD"
                ],
            },
        )
        .execute()
    )
    
def send_reply(
    service,
    original,
    response_text
):

    sender = original["sender"]

    if "<" in sender and ">" in sender:

        recipient = (
            sender
            .split("<", 1)[1]
            .split(">", 1)[0]
        )

    else:

        recipient = sender

    subject = original["subject"]

    if not subject.lower().startswith("re:"):

        subject = "Re: " + subject

    message = MIMEText(
        response_text,
        "plain",
        "utf-8"
    )

    message["To"] = recipient
    message["Subject"] = subject

    message_id = original.get(
        "message_id",
        ""
    )

    references = original.get(
        "references",
        ""
    )

    if message_id:

        message["In-Reply-To"] = message_id

        message["References"] = (
            f"{references} {message_id}"
        ).strip()

    raw = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    body = {
        "raw": raw,
        "threadId": original.get(
            "thread_id"
        ),
    }

    (
        service.users()
        .messages()
        .send(
            userId="me",
            body=body
        )
        .execute()
    )