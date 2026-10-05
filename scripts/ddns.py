#!/usr/bin/env python3
"""Template: human-operated only. No API access on import or during tests."""

import ipaddress
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def select_address(interfaces, nic, prefix=None):
    candidates = set()
    network = ipaddress.ip_network(prefix) if prefix else None
    for interface in interfaces:
        if interface.get("ifname") != nic:
            continue
        for entry in interface.get("addr_info", []):
            flags = set(entry.get("flags", []))
            if entry.get("family") != "inet6" or entry.get("scope") != "global":
                continue
            excluded = {"temporary", "deprecated", "tentative", "dadfailed"}
            if flags & excluded or any(entry.get(flag) for flag in excluded):
                continue
            if entry.get("preferred_life_time") == 0 or entry.get("valid_life_time") == 0:
                continue
            addr = ipaddress.ip_address(entry["local"])
            if addr.version == 6 and addr.is_global and (network is None or addr in network):
                candidates.add(str(addr))
    if len(candidates) != 1:
        raise ValueError("Stable GUA is missing or ambiguous; configure NIC/prefix")
    return candidates.pop()


def update_record(call, address, hostname):
    record = call("GET", None)["result"]
    if record["type"] != "AAAA" or record["name"] != hostname:
        raise ValueError("Record identity mismatch")
    payload = {"type": "AAAA", "name": hostname, "content": address, "proxied": True, "ttl": 1}
    if all(record.get(key) == value for key, value in payload.items()):
        return False
    updated = call("PATCH", payload)["result"]
    if any(updated.get(key) != value for key, value in payload.items()):
        raise ValueError("Record update verification failed")
    return True


def api_call(url, token, method, payload):
    for attempt in range(3):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode() if payload else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
            if not result.get("success"):
                raise ValueError("DNS API reported failure")
            return result
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("DNS API unavailable after three attempts") from None
            time.sleep(attempt + 1)
    raise RuntimeError("DNS API unavailable")


def main():
    token = Path(os.environ["CF_TOKEN_FILE"]).read_text().strip()
    interfaces = json.loads(subprocess.check_output(["ip", "-j", "-6", "address", "show"]))
    address = select_address(interfaces, os.environ["DDNS_NIC"], os.environ.get("DDNS_PREFIX"))
    url = f"https://api.cloudflare.com/client/v4/zones/{os.environ['CF_ZONE_ID']}/dns_records/{os.environ['CF_RECORD_ID']}"
    changed = update_record(
        lambda method, payload: api_call(url, token, method, payload),
        address,
        os.environ["DDNS_HOSTNAME"],
    )
    print("DNS updated" if changed else "DNS unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Do not expose addresses, credentials, or response payloads in the journal.
        raise SystemExit(f"DDNS failed ({type(exc).__name__}); check local configuration") from None
