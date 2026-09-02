#!/usr/bin/env python3
"""
Lab test harness for the ServiceNow specialist agent.

Exercises the SAME ServiceNow Table API calls used by
agent/src/subagent/servicenow_agent.py, but reads connection
details from environment variables so no credentials touch the code.

Env vars required:
    SNOW_INSTANCE   e.g. https://devXXXXXX.service-now.com
    SNOW_USERNAME   e.g. admin
    SNOW_PASSWORD   the instance password

Run:
    SNOW_INSTANCE=... SNOW_USERNAME=... SNOW_PASSWORD=... .venv/bin/python servicenow_lab_test.py
"""

import base64
import os
import sys
import requests

INSTANCE = os.environ.get("SNOW_INSTANCE", "").rstrip("/")
USERNAME = os.environ.get("SNOW_USERNAME", "")
PASSWORD = os.environ.get("SNOW_PASSWORD", "")

TIMEOUT = 30


def _fail(msg):
    print(f"  ✗ {msg}")


def _ok(msg):
    print(f"  ✓ {msg}")


def auth_headers():
    creds = f"{USERNAME}:{PASSWORD}"
    enc = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {enc}"}


def create_change_request(short_description, description=None, change_type="normal"):
    headers = auth_headers()
    headers["Content-Type"] = "application/json"
    data = {"short_description": short_description, "type": change_type, "state": "1"}
    if description:
        data["description"] = description
    url = f"{INSTANCE}/api/now/table/change_request"
    r = requests.post(url, headers=headers, json=data, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def list_change_requests(limit=10, state=None):
    headers = auth_headers()
    params = {"sysparm_limit": limit, "sysparm_display_value": "true"}
    if state:
        params["sysparm_query"] = f"state={state}"
    url = f"{INSTANCE}/api/now/table/change_request"
    r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_change_request(change_id):
    headers = auth_headers()
    url = f"{INSTANCE}/api/now/table/change_request/{change_id}"
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def list_catalog_items(limit=10, category=None):
    headers = auth_headers()
    params = {"sysparm_limit": limit, "sysparm_display_value": "true"}
    if category:
        params["sysparm_query"] = f"category={category}"
    url = f"{INSTANCE}/api/now/table/sc_cat_item"
    r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def list_catalog_categories(limit=10):
    headers = auth_headers()
    params = {"sysparm_limit": limit, "sysparm_display_value": "true"}
    url = f"{INSTANCE}/api/now/table/sc_category"
    r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def main():
    if not (INSTANCE and USERNAME and PASSWORD):
        print("ERROR: SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD must all be set.")
        sys.exit(2)

    # Never print the password; show only that it is set and its length.
    print(f"Instance : {INSTANCE}")
    print(f"Username : {USERNAME}")
    print(f"Password : set ({len(PASSWORD)} chars)")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test 1: list change requests (also validates auth + connectivity)
    print("\n[1] list_changes (GET change_request)")
    try:
        res = list_change_requests(limit=5)
        rows = res.get("result", [])
        _ok(f"auth OK, retrieved {len(rows)} change request(s)")
        for row in rows[:3]:
            print(f"      - {row.get('number')} | {row.get('short_description')} | state={row.get('state')}")
        passed += 1
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        _fail(f"HTTP {code}: {e}")
        if code == 401:
            print("      -> authentication failed; check username/password.")
        failed += 1
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")
        failed += 1

    # Test 2: list catalog categories
    print("\n[2] list_catalog_categories (GET sc_category)")
    try:
        res = list_catalog_categories(limit=5)
        rows = res.get("result", [])
        _ok(f"retrieved {len(rows)} category(ies)")
        for row in rows[:3]:
            print(f"      - {row.get('title') or row.get('name')}")
        passed += 1
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")
        failed += 1

    # Test 3: list catalog items
    print("\n[3] list_catalog_items (GET sc_cat_item)")
    try:
        res = list_catalog_items(limit=5)
        rows = res.get("result", [])
        _ok(f"retrieved {len(rows)} catalog item(s)")
        for row in rows[:3]:
            print(f"      - {row.get('name')}")
        passed += 1
    except Exception as e:
        _fail(f"{type(e).__name__}: {e}")
        failed += 1

    # Test 4: create a change request (WRITE), then read it back
    print("\n[4] create_change (POST change_request) + get_change_details")
    try:
        res = create_change_request(
            short_description="[LAB TEST] Firewall automation agent connectivity test",
            description="Automated lab test of the ServiceNow agent. Safe to delete.",
            change_type="normal",
        )
        created = res.get("result", {})
        number = created.get("number")
        sys_id = created.get("sys_id")
        _ok(f"created change request {number} (sys_id={sys_id})")
        passed += 1

        # read it back
        try:
            got = get_change_request(sys_id)
            got_num = got.get("result", {}).get("number")
            _ok(f"get_change_details returned {got_num}")
            passed += 1
        except Exception as e:
            _fail(f"get_change_details failed: {type(e).__name__}: {e}")
            failed += 1
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        _fail(f"create HTTP {code}: {e}")
        failed += 1
    except Exception as e:
        _fail(f"create failed: {type(e).__name__}: {e}")
        failed += 1

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
