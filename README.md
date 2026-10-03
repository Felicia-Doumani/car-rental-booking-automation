# Car Rental Booking Automation

A Python worker that processes car rental enquiries received through Gmail. It uses OpenAI to extract booking details, records requests in Google Sheets, and automatically sends replies in the customer's language.

Its purpose is to reduce manual inbox work, organize rental requests, and provide consistent acknowledgements, economy-car quotes, and requests for missing information. The reply instructions are tailored to **Meltemi Car Rental**.

The application does not check fleet availability, reserve vehicles, take payments, or integrate with a reservation system. Replies are sent automatically without human review; receiving a request does not confirm a booking.

## Architecture and workflow

1. Authenticate with Google using OAuth credentials shared by Gmail and Sheets.
2. Create or locate the Gmail label `BOOKING_AUTOMATED`.
3. Poll Gmail using the query `subject:RENTACAR is:unread -label:BOOKING_AUTOMATED`.
4. Read each matching message's sender, subject, body, and threading headers.
5. Ask `gpt-5-mini` to extract booking details as JSON, then replace the extracted email address with the actual `From` address.
6. Append a row to Google Sheets.
7. Calculate eligible economy-car pricing and ask `gpt-5-mini` to generate a reply.
8. Apply the processed label and remove `UNREAD` from the original message.
9. Send a plain-text reply in the original Gmail thread.

Each successfully processed request uses two OpenAI calls. Message-level exceptions are logged to standard output, and processing continues with other messages. Polling errors are logged before the worker waits and tries again.

| File | Responsibility |
| --- | --- |
| `app.py` | Entry point, polling loop, and processing sequence. |
| `gmail_service.py` | OAuth, Gmail searches, MIME body extraction, labels, and threaded replies. |
| `ai_extractor.py` | OpenAI client and structured extraction prompt. |
| `responder.py` | Rental-day calculation, economy pricing, and reply instructions. |
| `sheets_service.py` | Sheets authentication and row appends. |
| `email_parser.py` | Empty placeholder; parsing currently lives in `gmail_service.py`. |
| `requirements.txt` | Python dependencies, without version pins. |
| `Dockerfile` | Python 3.12 image running `python -u app.py`. |
| `docker-compose.yml` | Worker service, environment file, OAuth port, and credential/token mounts. |

## Prerequisites

- Python 3.12 to match the container environment, or Docker with Compose.
- An OpenAI API key with access to the configured model (`gpt-5-mini`).
- A Google Cloud project with the Gmail API and Google Sheets API enabled.
- An OAuth consent screen and a **Desktop app** OAuth client. If the consent app is in testing mode, add the mailbox account as a test user.
- A Gmail account to authorize and a Google spreadsheet that account can edit.
- Network access to Google and OpenAI APIs.

The application requests these OAuth scopes:

```text
https://www.googleapis.com/auth/gmail.modify
https://www.googleapis.com/auth/gmail.send
https://www.googleapis.com/auth/spreadsheets
```

## Configuration

Create `.env` in the repository root:

```dotenv
OPENAI_API_KEY=your-openai-api-key
GOOGLE_SHEET_ID=your-google-spreadsheet-id
POLL_SECONDS=30
```

| Variable | Required | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | Key used by both OpenAI clients. |
| `GOOGLE_SHEET_ID` | Yes | ID from `https://docs.google.com/spreadsheets/d/<ID>/edit`. |
| `POLL_SECONDS` | No | Integer polling interval in seconds, default `30`. Use a positive value. |

Download the Google OAuth client JSON to `credentials/credentials.json`. The worker saves the reusable OAuth token to `tokens/token.json`. These paths are relative to the working directory; run local commands from the repository root.

Keep `.env`, OAuth credentials, and tokens out of version control. The token grants access to the authorized Google account.

### Spreadsheet layout

Create a worksheet named **Bookings** and add the following headers in row 1, in this order. The application does not create the spreadsheet, worksheet, or headers.

| Column | Suggested header | Stored value |
| --- | --- | --- |
| A | Timestamp | UTC processing timestamp in ISO format. |
| B | Name | Extracted customer name. |
| C | Email | Actual sender address. |
| D | Phone | Extracted phone number. |
| E | Pickup date | Extracted date, preferably `YYYY-MM-DD`. |
| F | Return date | Extracted date, preferably `YYYY-MM-DD`. |
| G | Car category | Extracted category. |
| H | Language | Extracted message language. |
| I | Missing fields | Comma-separated fields identified by the model. |
| J | Status | `Needs information` if missing fields exist; otherwise `New`. |

The append range is `Bookings!A:K`, but each row has ten values occupying A–J; K is unused. Values use `USER_ENTERED`, so Sheets may interpret dates, numbers, and formula-like text rather than storing everything literally.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p credentials tokens
python -u app.py
```

Prepare `.env`, the OAuth client JSON, and the spreadsheet before starting the worker. On the first run, open the Google authorization URL printed in the terminal and authorize the intended account.

The OAuth callback listens on port `8080` and uses `127.0.0.1`. Your browser must be able to reach that address on the worker's machine. Forward port 8080 when authorizing a remote worker. The application does not open a browser automatically.

Subsequent starts reuse the saved token. Expired tokens are refreshed when a refresh token is available. If scopes change, reauthorize with a token containing the new scopes. Stop the worker with `Ctrl+C`.

## Run with Docker Compose

Prepare `.env`, `credentials/credentials.json`, and the `Bookings` worksheet, then start:

```bash
mkdir -p credentials tokens
docker compose up --build
```

Compose mounts `credentials/` read-only and `tokens/` read-write. Port `8080` is published for initial OAuth authorization; the worker has no web application or dashboard. Complete the consent flow using the URL in the container logs.

After authorization, run in the background and view logs:

```bash
docker compose up -d
docker compose logs -f booking-automation
```

Stop the service:

```bash
docker compose down
```

The token persists in the host's `tokens/` directory. The current Compose file has no restart policy.

## Extraction and pricing

The extraction prompt requests this JSON shape:

```json
{
  "name": null,
  "email": null,
  "phone": null,
  "pickup_date": null,
  "return_date": null,
  "car_category": null,
  "language": null,
  "missing_fields": []
}
```

It supports multilingual enquiries and requests categories such as `economy`, `compact`, `intermediate`, `SUV`, `luxury`, `van`, `automatic`, `manual`, and `unknown`. JSON output mode is enabled, but there is no application-level schema validation or enforcement of category values.

Python calculates pricing only when the lowercased category equals `economy` and both dates parse as ISO dates with the return date later than pickup:

```text
rental_days = (return_date - pickup_date).days
total_price = rental_days × €35
```

For example, 2026-09-20 through 2026-09-25 is five days and a €175 quote. Times of day, same-day pricing, and rounding rules are not supported. Invalid or non-positive intervals produce no calculated price. Other categories have no configured price.

The reply prompt asks the model to use the customer's language, request missing booking details, and distinguish quotes from confirmed bookings. It describes these economy-rate inclusions: full insurance with no excess, second driver, airport pickup and drop-off, full-to-full fuel, 24/7 support, and no credit card deposit. These are hardcoded business instructions, not information retrieved from an external service. When the category is missing, the prompt asks for an economy reference rate, but Python supplies no calculated total for that case.

## Customization

| Setting | Location |
| --- | --- |
| Gmail subject filter and unread requirement | Query in `get_new_booking_emails()` in `gmail_service.py`. |
| Processed label | `PROCESSED_LABEL` in `gmail_service.py`. |
| Extraction fields and rules | `SYSTEM_PROMPT` in `ai_extractor.py`. |
| Company name, reply style, inclusions, and business rules | `SYSTEM_PROMPT` in `responder.py`. |
| Economy rate | `PRICE_PER_DAY` in `responder.py`; update the prompt's hardcoded €35 references too. |
| OpenAI model | Model argument in both `ai_extractor.py` and `responder.py`. |
| Worksheet and columns | `SHEET_RANGE` and row definition in `sheets_service.py`. |

## Operational limitations

- **Processing is not transactional.** A row is saved before reply generation and labeling. Failures before labeling can create duplicate rows on later polls. Labeling happens before sending, so a send failure leaves the message excluded from subsequent polls even though no reply was sent. The label does not guarantee exactly-once processing or coordinate multiple workers.
- **Recovery needs inspection.** Check logs, the spreadsheet, and the Gmail thread before retrying. Removing `BOOKING_AUTOMATED` and marking a message unread makes it eligible again and can create duplicate rows or replies.
- **Email parsing is limited.** The parser reads inline body data and recursively searches multipart messages for plain text. It does not fetch attachments or explicitly convert multipart HTML-only messages to text. Top-level HTML may be passed to the model as raw HTML.
- **Pagination is not implemented.** Each poll fetches only one page of Gmail search results.
- **AI behavior is governed by prompts.** Extracted facts and generated replies are not validated. There is no prompt-injection defense or approval queue. The extractor asks the model to infer the current year for some dates, but the actual current date is not supplied.
- **Customer data is shared and logged.** Sender, subject, and body are sent to OpenAI for extraction. Structured booking data is sent for reply generation and saved to Sheets. Sender details, extracted data, and generated replies are printed in logs.
- **Operational tooling is minimal.** There is no automated test suite, health endpoint, durable job queue, or explicit retry/backoff policy. Dependencies are unpinned.

## Verify the setup

Use a test mailbox and spreadsheet. Send an unread email with `RENTACAR` in its subject and include a name, phone number, explicit future pickup/return dates, and an economy-car request. After a polling interval, verify:

1. A row appears in `Bookings` with the actual sender address.
2. The original message is read and labeled `BOOKING_AUTOMATED`.
3. A reply appears in the original Gmail thread with the expected quote.

Also try missing dates or a missing phone number to inspect follow-up wording. These checks use live Google and OpenAI services and send real emails.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No emails processed | Message is unread, subject matches `RENTACAR`, processed label is absent, and the correct account was authorized. |
| OAuth callback fails | OAuth client type, consent/test-user settings, port 8080 availability, and browser access to the callback address. |
| Google permission error | Both APIs are enabled, the token includes the requested scopes, and the account can edit the spreadsheet. |
| Sheet append fails | Spreadsheet ID is correct and the worksheet is named `Bookings`. |
| OpenAI request fails | API key, account/model access, and network connectivity. |
| Labeled message has no reply | Inspect logs for a send failure after labeling and check the Gmail thread before retrying. |
