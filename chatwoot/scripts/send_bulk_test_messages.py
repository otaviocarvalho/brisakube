#!/usr/bin/env python3
"""Send test messages from 5 distinct contacts to simulate customer conversations."""

import json
import sys
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "https://chat.46-225-43-58.sslip.io/api/v1/accounts/1"
INBOX_ID = 1

CONTACTS = [
    {"name": "Ana Souza",    "email": "ana.souza@example.com",    "message": "Oi, preciso de ajuda com meu pedido!"},
    {"name": "Carlos Lima",  "email": "carlos.lima@example.com",  "message": "Bom dia! Não consigo acessar minha conta."},
    {"name": "Fernanda Reis","email": "fernanda.reis@example.com","message": "Olá, gostaria de saber o prazo de entrega."},
    {"name": "Ricardo Alves","email": "ricardo.alves@example.com","message": "Tive um problema com o pagamento, podem me ajudar?"},
    {"name": "Juliana Costa","email": "juliana.costa@example.com","message": "Boa tarde! Quero cancelar minha assinatura."},
]


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
        return result["payload"][0]["id"]
    contact = api(token, "POST", "/contacts", {"name": name, "email": email})
    if "id" in contact:
        return contact["id"]
    # Creation failed (e.g. duplicate) — search again
    result = api(token, "GET", f"/contacts/search?q={urllib.parse.quote(email)}")
    return result["payload"][0]["id"]


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <api_access_token>")
        sys.exit(1)

    token = sys.argv[1]

    for c in CONTACTS:
        contact_id = get_or_create_contact(token, c["name"], c["email"])
        conv = api(token, "POST", "/conversations", {
            "inbox_id": INBOX_ID,
            "contact_id": contact_id,
        })
        conv_id = conv["id"]
        msg = api(token, "POST", f"/conversations/{conv_id}/messages", {
            "content": c["message"],
            "message_type": "incoming",
        })
        print(f"[conv={conv_id}] {c['name']}: {msg['content']}")

    print(f"\nDone! View at: https://chat.46-225-43-58.sslip.io/app/accounts/1/mentions")


if __name__ == "__main__":
    main()
