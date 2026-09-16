import os
import time

from dotenv import load_dotenv

from gmail_service import (
    get_gmail_service,
    get_or_create_processed_label,
    get_new_booking_emails,
    get_email,
    extract_email_content,
    mark_as_processed,
    send_reply
)

from ai_extractor import extract_booking
from responder import generate_reply
from sheets_service import append_booking


load_dotenv()

POLL_SECONDS = int(
    os.getenv("POLL_SECONDS", "30")
)


def process_message(
    gmail,
    message_id,
    label_id
):

    print(
        f"\nProcessing email: {message_id}",
        flush=True
    )

    message = get_email(
        gmail,
        message_id
    )

    email = extract_email_content(
        message
    )

    email["thread_id"] = message.get(
        "threadId"
    )

    print(
        f"From: {email['sender']}",
        flush=True
    )

    print(
        f"Subject: {email['subject']}",
        flush=True
    )

    # AI extraction
    booking = extract_booking(
        email
    )

    print(
        "Extracted booking:",
        flush=True
    )

    print(
        booking,
        flush=True
    )

    # Always use the actual sender's email address
    sender = email["sender"]

    if "<" in sender and ">" in sender:

        sender_email = (
            sender
            .split("<", 1)[1]
            .split(">", 1)[0]
            .strip()
        )

    else:

        sender_email = sender.strip()

    booking["email"] = sender_email

    print(
        f"Sender email: {sender_email}",
        flush=True
    )

    # Save to Google Sheets
    append_booking(
        booking
    )

    print(
        "Saved to Google Sheets.",
        flush=True
    )

    # Generate response
    reply = generate_reply(
        booking
    )

    print(
        "Generated reply:",
        flush=True
    )

    print(
        reply,
        flush=True
    )

    # Mark as processed BEFORE sending
    # to prevent duplicate replies
    mark_as_processed(
        gmail,
        message_id,
        label_id
    )

    print(
        "Marked as processed.",
        flush=True
    )

    # Send Gmail reply
    send_reply(
        gmail,
        email,
        reply
    )

    print(
        "Reply sent.",
        flush=True
    )


def main():

    print(
        "Booking automation started.",
        flush=True
    )

    gmail = get_gmail_service()

    print(
        "Gmail service connected.",
        flush=True
    )

    label_id = get_or_create_processed_label(
        gmail
    )

    print(
        f"Processed label ready: {label_id}",
        flush=True
    )

    while True:

        try:

            messages, label_id = (
                get_new_booking_emails(
                    gmail,
                    label_id
                )
            )

            if not messages:

                print(
                    "No new booking emails.",
                    flush=True
                )

            else:

                print(
                    f"Found {len(messages)} "
                    f"new booking email(s).",
                    flush=True
                )

                for message in messages:

                    try:

                        process_message(
                            gmail,
                            message["id"],
                            label_id
                        )

                    except Exception as error:

                        print(
                            f"ERROR processing "
                            f"{message['id']}: "
                            f"{error}",
                            flush=True
                        )

            time.sleep(
                POLL_SECONDS
            )

        except Exception as error:

            print(
                f"Worker error: {error}",
                flush=True
            )

            time.sleep(
                POLL_SECONDS
            )


if __name__ == "__main__":
    main()