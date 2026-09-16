import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build

from gmail_service import get_gmail_service


load_dotenv()


SPREADSHEET_ID = os.getenv(
    "GOOGLE_SHEET_ID"
)

SHEET_RANGE = "Bookings!A:K"


def get_sheets_service():

    gmail_service = get_gmail_service()

    # The OAuth token has Sheets scope too.
    credentials = gmail_service._http.credentials

    return build(
        "sheets",
        "v4",
        credentials=credentials
    )


def append_booking(booking):

    service = get_sheets_service()

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    missing = ", ".join(
        booking.get("missing_fields", [])
    )

    status = (
        "Needs information"
        if booking.get("missing_fields")
        else "New"
    )

    row = [
        timestamp,
        booking.get("name"),
        booking.get("email"),
        booking.get("phone"),
        booking.get("pickup_date"),
        booking.get("return_date"),
        booking.get("car_category"),
        booking.get("language"),
        missing,
        status,
    ]

    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=SHEET_RANGE,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={
            "values": [row]
        }
    ).execute()