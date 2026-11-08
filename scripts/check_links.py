#!/usr/bin/env python3
"""Check every resource URL (and feed URL with --feeds) and report broken ones.

Some sites block bots or regions (403/412/429/451, timeouts), so
those are reported as "blocked" warnings, not failures. Only 404/410, DNS
errors and 5xx count as broken.

Usage:
    python3 scripts/check_links.py [--feeds] [--json report.json]
Exit code 1 if anything is broken.
"""
import concurrent.futures as cf
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
BLOCKED = {401, 403, 405, 412, 418, 429, 451, 999}


def status(url):
    for method in (["-I"], []):  # HEAD first, then GET (some servers reject HEAD)
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-L", "--max-redirs", "8", "-m", "25", "-A", UA,
             "-H", "Accept-Language: en-US,en;q=0.9", "-w", "%{http_code} %{url_effective}", *method, url],
            capture_output=True, text=True)
        code, _, final = r.stdout.partition(" ")
        code = int(code or 0)
        if 200 <= code < 400:
            return code, final
    return code, final


def classify(code):
    if 200 <= code < 400:
        return "ok"
    if code in BLOCKED:
        return "blocked"
    if code == 0:
        return "unreachable"
    return "broken"


def main():
    with_feeds = "--feeds" in sys.argv
    out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    targets = []
    for p in sorted((ROOT / "data").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            targets.append((e["id"], "url", e["url"]))
            if with_feeds and "feed" in e and e["feed"]["format"] != "rsshub":
                targets.append((e["id"], "feed", e["feed"]["url"]))

    results = []
    with cf.ThreadPoolExecutor(16) as ex:
        for (rid, field, url), (code, final) in zip(targets, ex.map(lambda t: status(t[2]), targets)):
            results.append({"id": rid, "field": field, "url": url, "status": code, "final_url": final, "result": classify(code)})

    summary = {}
    for r in results:
        summary[r["result"]] = summary.get(r["result"], 0) + 1
    for r in sorted(results, key=lambda r: r["result"]):
        if r["result"] != "ok":
            print(f"{r['result']:12} {r['status']:>3}  {r['id']:40} {r['url']}")
    print(summary)
    if out_json:
        Path(out_json).write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sys.exit(1 if summary.get("broken") else 0)


if __name__ == "__main__":
    main()
