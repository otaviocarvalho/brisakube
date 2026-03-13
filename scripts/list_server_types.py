#!/usr/bin/env python3
"""Lists available Hetzner server types with specs and monthly prices.

Usage:
    python scripts/list_server_types.py
    HCLOUD_TOKEN=xxx python scripts/list_server_types.py
"""

import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("HCLOUD_TOKEN", "")
if not TOKEN:
    print("Error: set HCLOUD_TOKEN environment variable")
    sys.exit(1)

req = urllib.request.Request(
    "https://api.hetzner.cloud/v1/server_types?per_page=50",
    headers={"Authorization": f"Bearer {TOKEN}"},
)
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)

types = []
for t in data["server_types"]:
    if t["deprecated"]:
        continue
    price = float(t["prices"][0]["price_monthly"]["gross"]) if t["prices"] else 0
    types.append((price, t["name"], t["cores"], int(t["memory"]), t["disk"]))

types.sort()
print(f"{'Name':<12} {'vCPU':>4}  {'RAM':>5}  {'Disk':>6}  {'EUR/mo':>8}")
print("-" * 45)
for price, name, cores, mem, disk in types:
    print(f"{name:<12} {cores:>4}  {mem:>4}GB  {disk:>5}GB  {price:>8.2f}")
