#!/usr/bin/env python3
"""Validate data/*.json and build the published JSON API into dist/.

Usage:
    python3 scripts/build.py           # validate + write dist/
    python3 scripts/build.py --check   # validate only, fail if dist/ or README.md is stale

Also regenerates the resource list inside README.md and the GitHub Pages
site at dist/index.html (see scripts/render.py).

No third-party dependencies.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import render

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
API_VERSION = "v1"
SCHEMA_VERSION = 1

ENUMS = {
    "type": ["website", "youtube", "podcast", "app", "newsletter"],
    "level": ["beginner", "intermediate", "advanced"],
    "region": ["us", "gb", "au", "ca", "ie", "nz", "in", "za", "sg", "global"],
    "pricing": ["free", "freemium", "paid"],
    "platforms": ["web", "ios", "android"],
    "feed_format": ["rss", "atom", "youtube", "podcast"],
    "login": ["none", "partial", "required"],
    "subtitles": ["free", "paid"],
}
REQUIRED = ["id", "name", "url", "description", "category", "type", "level", "region", "pricing"]
OPTIONAL = ["tags", "for_learners", "platforms", "login", "subtitles", "recommended", "feed", "ids", "image", "notes"]
KEY_ORDER = REQUIRED + OPTIONAL
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
URL_RE = re.compile(r"^https?://[^\s]+$")


def load_categories():
    cats = json.loads((ROOT / "categories.json").read_text(encoding="utf-8"))
    return cats, {c["id"]: c for c in cats}


def validate(entry, where, cat_ids, errors):
    def err(msg):
        errors.append(f"{where} [{entry.get('id', '?')}]: {msg}")

    for k in REQUIRED:
        if k not in entry or entry[k] in ("", None, []):
            err(f"missing '{k}'")
    for k in entry:
        if k not in REQUIRED and k not in OPTIONAL:
            err(f"unknown key '{k}'")
    if not ID_RE.match(entry.get("id", "")):
        err("id must be lowercase a-z0-9 and dashes")
    if not URL_RE.match(entry.get("url", "")):
        err("url must be http(s)")
    if entry.get("category") not in cat_ids:
        err(f"category '{entry.get('category')}' not in categories.json")
    for k in ("type", "region", "pricing", "login", "subtitles"):
        if k in entry and entry[k] not in ENUMS[k]:
            err(f"{k} '{entry[k]}' not one of {ENUMS[k]}")
    for k in ("level", "platforms"):
        v = entry.get(k, [])
        if not isinstance(v, list) or any(x not in ENUMS[k] for x in v):
            err(f"{k} must be a list of {ENUMS[k]}")
    for k in ("for_learners", "recommended"):
        if k in entry and not isinstance(entry[k], bool):
            err(f"{k} must be true or false")
    if entry.get("recommended") and entry.get("login", "none") != "none":
        err("recommended entries must open without an account (login: none)")
    if any(not TAG_RE.match(t) for t in entry.get("tags", [])):
        err("tags must be lowercase kebab-case")
    feed = entry.get("feed")
    if feed is not None:
        if feed.get("format") not in ENUMS["feed_format"] or not URL_RE.match(feed.get("url", "")):
            err("feed needs {format, url}")
    if len(entry.get("description", "")) > 300:
        err("description longer than 300 chars")


def normalize(entry):
    entry.setdefault("tags", [])
    entry.setdefault("for_learners", False)
    entry.setdefault("platforms", ["web"])
    entry.setdefault("login", "none")
    entry.setdefault("recommended", False)
    entry["level"] = [l for l in ENUMS["level"] if l in entry["level"]]
    entry["tags"] = sorted(set(entry["tags"]))
    return {k: entry[k] for k in KEY_ORDER if k in entry}


def main():
    check_only = "--check" in sys.argv
    cats, cat_map = load_categories()
    errors, resources, seen_ids, seen_urls = [], [], {}, {}

    for path in sorted(DATA.glob("*.json")):
        items = json.loads(path.read_text(encoding="utf-8"))
        if path.stem not in cat_map:
            errors.append(f"{path.name}: file name must match a category id")
        for i, e in enumerate(items):
            where = f"{path.name}#{i}"
            validate(e, where, cat_map, errors)
            if e.get("category") != path.stem:
                errors.append(f"{where}: category '{e.get('category')}' does not match file")
            if e.get("id") in seen_ids:
                errors.append(f"{where}: duplicate id '{e['id']}' (also in {seen_ids[e['id']]})")
            seen_ids[e.get("id")] = where
            url_key = e.get("url", "").rstrip("/").lower()
            if url_key in seen_urls and seen_urls[url_key][1] == e.get("category"):
                errors.append(f"{where}: duplicate url in same category (also {seen_urls[url_key][0]})")
            seen_urls.setdefault(url_key, (where, e.get("category")))
            resources.append(normalize(dict(e)))

    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        sys.exit(1)

    order = {c["id"]: i for i, c in enumerate(cats)}
    resources.sort(key=lambda r: (order[r["category"]], r["name"].lower()))
    by_cat = {}
    for r in resources:
        by_cat.setdefault(r["category"], []).append(r)

    out = DIST / API_VERSION
    files = {}

    def emit(rel, payload):
        files[f"dist/{API_VERSION}/{rel}"] = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n"

    # Content hash: changes only when the data changes, so clients can cache on it
    # and rebuilding without edits is a no-op.
    data_version = hashlib.sha256(json.dumps([cats, resources], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]

    facets = {
        "types": sorted({r["type"] for r in resources}),
        "levels": ENUMS["level"],
        "regions": sorted({r["region"] for r in resources}),
        "pricing": ENUMS["pricing"],
        "login": ENUMS["login"],
        "subtitles": ENUMS["subtitles"],
        "tags": sorted({t for r in resources for t in r["tags"]}),
    }
    emit("index.json", {
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "data_version": data_version,
        "count": len(resources),
        "endpoints": {
            "all": "all.json",
            "feeds": "feeds.json",
            "category": "categories/{id}.json",
        },
        "categories": [
            {**c, "count": len(by_cat.get(c["id"], [])), "path": f"categories/{c['id']}.json"}
            for c in cats
        ],
        "facets": facets,
    })
    emit("all.json", {"data_version": data_version, "count": len(resources), "resources": resources})
    feeds = [
        {"id": r["id"], "name": r["name"], "category": r["category"], "type": r["type"], "feed": r["feed"], **({"image": r["image"]} if "image" in r else {})}
        for r in resources if "feed" in r
    ]
    emit("feeds.json", {"data_version": data_version, "count": len(feeds), "feeds": feeds})
    for c in cats:
        items = by_cat.get(c["id"], [])
        emit(f"categories/{c['id']}.json", {"category": c, "data_version": data_version, "count": len(items), "resources": items})

    files["dist/index.html"] = render.render_html(cats, by_cat, data_version)
    files.update(render.readme_icons(cats))
    readme = ROOT / "README.md"
    current = readme.read_text(encoding="utf-8") if readme.exists() else ""
    files["README.md"] = render.splice_readme(current, render.render_markdown(cats, by_cat))

    if check_only:
        stale = [rel for rel, body in files.items() if not (ROOT / rel).exists() or (ROOT / rel).read_text(encoding="utf-8") != body]
        if stale:
            print("Generated files are out of date, run: python3 scripts/build.py", file=sys.stderr)
            print("\n".join("  " + s for s in stale), file=sys.stderr)
            sys.exit(1)
        print(f"OK: {len(resources)} resources, generated files up to date")
        return

    for rel, body in files.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    print(f"Built {len(resources)} resources in {len(by_cat)} categories ({len(feeds)} with feeds) -> {out}")


if __name__ == "__main__":
    main()
