import json
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


SYSTEM_PROMPT = """
You process incoming car rental booking requests.

The customer may write in ANY language.

Extract booking information from the email.

NEVER invent information.
NEVER guess dates.
NEVER guess phone numbers.
NEVER invent car availability.
NEVER invent prices.

Return ONLY valid JSON:

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

Rules:

- Dates must use YYYY-MM-DD when possible.
- Use the current year when the customer clearly refers
  to a future date without specifying a year.
- car_category should be a simple category:
  economy, compact, intermediate, SUV, luxury, van,
  automatic, manual, unknown.
- language should be the language of the customer's message.
- missing_fields should contain only information that is
  necessary to properly handle the booking request.
"""


def extract_booking(email):

    prompt = f"""
FROM:
{email["sender"]}

SUBJECT:
{email["subject"]}

MESSAGE:
{email["body"]}
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return json.loads(
        response.choices[0].message.content
    )