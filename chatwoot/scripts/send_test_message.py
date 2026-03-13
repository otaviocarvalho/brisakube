#!/usr/bin/env python3
"""Send a test incoming message to Chatwoot to simulate a customer conversation."""

import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "https://chat.46-225-43-58.sslip.io/api/v1/accounts/1"
INBOX_ID = 1


def api(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "api_access_token": token,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


def get_or_create_contact(token: str, name: str, email: str) -> int:
    result = api(token, "GET", f"/contacts/search?q={urllib.parse.quote(email)}")
    if result["payload"]:
        contact_id = result["payload"][0]["id"]
        print(f"Using existing contact: {name} (id={contact_id})")
        return contact_id
    contact = api(token, "POST", "/contacts", {"name": name, "email": email})
    if "id" in contact:
        print(f"Created contact: {name} (id={contact['id']})")
        return contact["id"]
    result = api(token, "GET", f"/contacts/search?q={urllib.parse.quote(email)}")
    contact_id = result["payload"][0]["id"]
    print(f"Using existing contact: {name} (id={contact_id})")
    return contact_id


def main():
    parser = argparse.ArgumentParser(description="Send a test message to Chatwoot")
    parser.add_argument("--token", required=True, help="Chatwoot API access token")
    parser.add_argument("--name", default="Customer Test", help="Contact name")
    parser.add_argument("--email", default="customer@example.com", help="Contact email")
    parser.add_argument("--message", default="Oi, preciso de ajuda!", help="Message content")
    args = parser.parse_args()

    contact_id = get_or_create_contact(args.token, args.name, args.email)

    conv = api(args.token, "POST", "/conversations", {
        "inbox_id": INBOX_ID,
        "contact_id": contact_id,
    })
    conv_id = conv["id"]
    print(f"Created conversation id={conv_id}")

    msg = api(args.token, "POST", f"/conversations/{conv_id}/messages", {
        "content": args.message,
        "message_type": "incoming",
    })
    print(f"Sent message id={msg['id']}: {msg['content']}")
    print(f"\nView at: https://chat.46-225-43-58.sslip.io/app/accounts/1/conversations/{conv_id}")


if __name__ == "__main__":
    main()
