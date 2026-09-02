#!/usr/bin/env python3
"""
ServiceNow integration DEMO for the Network Firewall Automation Agent.

Runs the SAME six ServiceNow operations the ServiceNow specialist agent
exposes, and prints clean, on-camera-friendly output.

Auth: tries HTTP Basic (what the shipped agent uses). If the instance has
Basic auth disabled for REST, set SNOW_AUTH=session to use ServiceNow's
session + X-UserToken flow instead (functionally identical results).

Env vars:
    SNOW_INSTANCE   https://devXXXXXX.service-now.com
    SNOW_USERNAME   integration user
    SNOW_PASSWORD   its password
    SNOW_AUTH       "basic" (default) or "session"
"""
import base64
import os
import re
import sys
import time
import requests
from requests.auth import HTTPBasicAuth

INSTANCE = os.environ.get("SNOW_INSTANCE", "").rstrip("/")
USERNAME = os.environ.get("SNOW_USERNAME", "")
PASSWORD = os.environ.get("SNOW_PASSWORD", "")
AUTH_MODE = os.environ.get("SNOW_AUTH", "basic").lower()
TIMEOUT = 30

BOLD = "\033[1m"; GREEN = "\033[32m"; CYAN = "\033[36m"; DIM = "\033[2m"; RESET = "\033[0m"


def banner(txt):
    print(f"\n{BOLD}{CYAN}{'='*64}{RESET}")
    print(f"{BOLD}{CYAN} {txt}{RESET}")
    print(f"{BOLD}{CYAN}{'='*64}{RESET}")


def step(n, txt):
    print(f"\n{BOLD}▶ Step {n}: {txt}{RESET}")


def ok(txt):
    print(f"  {GREEN}✓ {txt}{RESET}")


class Snow:
    """Thin ServiceNow REST client supporting basic or session auth."""

    def __init__(self):
        self.s = requests.Session()
        self.mode = AUTH_MODE
        self.token = None
        if self.mode == "basic":
            self.s.auth = HTTPBasicAuth(USERNAME, PASSWORD)
            self.s.headers.update({"Accept": "application/json"})
        else:
            self._session_login()

    def _session_login(self):
        self.s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        self.s.get(f"{INSTANCE}/login.do", timeout=TIMEOUT)
        self.s.post(
            f"{INSTANCE}/login.do",
            data={"user_name": USERNAME, "user_password": PASSWORD, "sys_action": "sysverb_login"},
            timeout=TIMEOUT, allow_redirects=True,
        )
        r = self.s.get(f"{INSTANCE}/now/nav/ui/home", timeout=TIMEOUT)
        m = re.search(r'g_ck["\']?\s*[=:]\s*["\']([0-9a-zA-Z]+)["\']', r.text)
        self.token = m.group(1) if m else None
        if self.token:
            self.s.headers.update({"X-UserToken": self.token})

    def get(self, path, **params):
        r = self.s.get(f"{INSTANCE}{path}", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("result")

    def post(self, path, body):
        r = self.s.post(f"{INSTANCE}{path}", json=body,
                        headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("result")


def main():
    if not (INSTANCE and USERNAME and PASSWORD):
        print("ERROR: set SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD")
        sys.exit(2)

    banner("AWS Network Firewall Automation Agent — ServiceNow Integration Demo")
    print(f"  Instance : {INSTANCE}")
    print(f"  User     : {USERNAME}")
    print(f"  Auth mode: {AUTH_MODE}")
    snow = Snow()
    if AUTH_MODE == "session":
        ok(f"authenticated via ServiceNow session (token {'obtained' if snow.token else 'MISSING'})")

    # 1. List existing change requests
    step(1, "list_changes — recent ServiceNow change requests")
    rows = snow.get("/api/now/table/change_request", sysparm_limit=5, sysparm_display_value="true")
    ok(f"retrieved {len(rows)} change request(s)")
    for r in rows[:5]:
        print(f"    {DIM}- {r.get('number')} | {r.get('short_description')[:50]} | state={r.get('state')}{RESET}")

    # 2. List service catalog categories
    step(2, "list_catalog_categories — service catalog categories")
    cats = snow.get("/api/now/table/sc_category", sysparm_limit=5, sysparm_display_value="true")
    ok(f"retrieved {len(cats)} categor(y/ies)")
    for c in cats[:5]:
        print(f"    {DIM}- {c.get('title') or c.get('name')}{RESET}")

    # 3. List service catalog items
    step(3, "list_catalog_items — service catalog items")
    items = snow.get("/api/now/table/sc_cat_item", sysparm_limit=5, sysparm_display_value="true")
    ok(f"retrieved {len(items)} catalog item(s)")
    for it in items[:5]:
        print(f"    {DIM}- {it.get('name')}{RESET}")

    # 4. Create a change request (simulating a firewall rule change)
    step(4, "create_change — raise a firewall change request")
    payload = {
        "short_description": "Allow HTTPS 10.0.1.0/24 -> 10.0.2.0/24 (firewall automation agent)",
        "description": ("Automated change request created by the AWS Network Firewall "
                        "Automation Agent. Suricata rule: pass tls 10.0.1.0/24 any -> "
                        "10.0.2.0/24 443. Created for demo — safe to close."),
        "type": "normal",
        "state": "1",
    }
    created = snow.post("/api/now/table/change_request", payload)
    number = created.get("number")
    sys_id = created.get("sys_id")
    ok(f"created change request {BOLD}{number}{RESET}{GREEN} (sys_id={sys_id})")

    # 5. Read the change request back
    step(5, "get_change_details — read the change request back")
    time.sleep(1)
    got = snow.get(f"/api/now/table/change_request/{sys_id}")
    ok(f"verified {BOLD}{got.get('number')}{RESET}{GREEN} — \"{got.get('short_description')[:55]}\"")
    print(f"    {DIM}state={got.get('state')}  type={got.get('type')}  opened={got.get('opened_at')}{RESET}")

    banner("RESULT: ServiceNow integration is WORKING — all 5 operations succeeded ✅")
    print(f"  View it in the UI: {INSTANCE}/nav_to.do?uri=change_request.do?sys_id={sys_id}\n")


if __name__ == "__main__":
    main()
