#!/usr/bin/env python3
"""Fill machine-resolvable fields in data/*.json from the network.

  youtube  -> ids.youtube_channel_id, image, feed (YouTube channel RSS)
  podcast  -> ids.apple_podcast_id, url, image, feed (the show's real RSS URL
              from the iTunes API). Entries without an Apple id are looked up
              by name; fuzzy matches are listed so they can be checked by hand.
  website  -> feed (RSS/Atom advertised in the page head, verified to parse)

Only fills missing fields unless --force is given. Entries that cannot be
resolved are listed at the end so they can be fixed or removed by hand.

Extra passes (slower, opt-in):
  --transcripts  mark podcasts whose feed lists <podcast:transcript> as subtitles: free
  --captions     mark YouTube channels whose latest video has human-made English captions

Usage:
    python3 scripts/enrich.py [--force] [--only youtube|podcast|website] [--transcripts] [--captions]

Uses curl (preinstalled on macOS and GitHub runners) so it works without
Python certificate setup.
"""
import concurrent.futures as cf
import difflib
import html as htmllib
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def curl(url, *extra, limit=None):
    args = ["curl", "-sL", "-m", "25", "-A", UA, "-H", "Accept-Language: en", "-H", "Cookie: CONSENT=YES+1", *extra]
    if limit:
        args += ["-r", f"0-{limit}"]
    r = subprocess.run([*args, url], capture_output=True)
    return r.stdout.decode("utf-8", "ignore")


def norm(s):
    s = re.sub(r"\(.*?\)|podcast|the |: .*$", "", s.lower())
    return re.sub(r"[^a-z0-9]", "", s)


# ── YouTube ─────────────────────────────────────────────────────────────────

def youtube(e):
    page = curl(e["url"])
    m = re.search(r'"externalId":"(UC[\w-]{22})"', page) or re.search(r'<meta itemprop="identifier" content="(UC[\w-]{22})"', page)
    if not m:
        return None
    cid = m.group(1)
    e.setdefault("ids", {})["youtube_channel_id"] = cid
    img = re.search(r'<meta property="og:image" content="([^"]+)"', page)
    if img:
        e["image"] = img.group(1)
    e["feed"] = {"format": "youtube", "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"}
    title = re.search(r'<meta property="og:title" content="([^"]+)"', page)
    return htmllib.unescape(title.group(1)) if title else ""


def captions(e):
    """True when the newest video has an English caption track that is not auto-generated."""
    feed = curl(e["feed"]["url"])
    vids = re.findall(r"<yt:videoId>([\w-]{11})</yt:videoId>", feed)[:2]
    for vid in vids:
        page = curl(f"https://www.youtube.com/watch?v={vid}")
        m = re.search(r'"captionTracks":(\[.*?\])', page)
        if not m:
            continue
        try:
            tracks = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if any(t.get("languageCode", "").startswith("en") and t.get("kind") != "asr" for t in tracks):
            return True
    return False


# ── Podcasts ────────────────────────────────────────────────────────────────

def apply_itunes(e, r):
    e.setdefault("ids", {})["apple_podcast_id"] = str(r["collectionId"])
    e["feed"] = {"format": "podcast", "url": r["feedUrl"]}
    art = r.get("artworkUrl600") or r.get("artworkUrl100")
    if art:
        e["image"] = art
    if "podcasts.apple.com" in e["url"] and "/id" not in e["url"]:
        e["url"] = r["collectionViewUrl"].split("?")[0]


def itunes_json(url):
    for _ in range(4):
        try:
            return json.loads(curl(url))
        except json.JSONDecodeError:
            time.sleep(15)
    return {}


def podcasts_by_id(entries):
    """iTunes lookup accepts many comma-separated ids per request."""
    by_id = {e["ids"]["apple_podcast_id"]: e for e in entries}
    ids, done = list(by_id), set()
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        for r in itunes_json("https://itunes.apple.com/lookup?entity=podcast&id=" + ",".join(chunk)).get("results", []):
            e = by_id.get(str(r.get("collectionId")))
            if e and r.get("feedUrl"):
                apply_itunes(e, r)
                done.add(str(r["collectionId"]))
        time.sleep(3)
    return [by_id[p] for p in ids if p not in done]


def podcast_by_name(e):
    """Search iTunes by name. Returns (status, matched name): exact, fuzzy or None."""
    term = urllib.parse.quote(e.get("_search") or e["name"])
    results = [r for r in itunes_json(f"https://itunes.apple.com/search?media=podcast&entity=podcast&limit=10&term={term}").get("results", []) if r.get("feedUrl")]
    time.sleep(3)
    if not results:
        return None, None
    want = norm(e["name"])
    for r in results:
        if norm(r["collectionName"]) == want:
            apply_itunes(e, r)
            return "exact", r["collectionName"]
    best = max(results, key=lambda r: difflib.SequenceMatcher(None, want, norm(r["collectionName"])).ratio())
    if difflib.SequenceMatcher(None, want, norm(best["collectionName"])).ratio() >= 0.75:
        apply_itunes(e, best)
        return "fuzzy", best["collectionName"]
    return None, results[0]["collectionName"]


def has_transcripts(e):
    return "<podcast:transcript" in curl(e["feed"]["url"], limit=400_000)


# ── Websites ────────────────────────────────────────────────────────────────

FEED_LINK = re.compile(r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]*>', re.I)


def website(e):
    """Discover an RSS/Atom feed advertised in the page <head>, and keep it only if it parses as a feed."""
    page = curl(e["url"])
    for m in FEED_LINK.finditer(page):
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if not href:
            continue
        url = href.group(1).replace("&amp;", "&")
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = re.match(r"https?://[^/]+", e["url"]).group(0) + url
        elif not url.startswith("http"):
            continue
        # Comment feeds and wiki change logs are not content feeds.
        if any(s in url for s in ("comments", "Special:RecentChanges", "featuredfeed")):
            continue
        body = curl(url)[:2000]
        if "<rss" in body or "<feed" in body or "<rdf:RDF" in body:
            e["feed"] = {"format": m.group(1).lower(), "url": url}
            return True
    return False


def main():
    force = "--force" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    files = {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(DATA.glob("*.json"))}
    entries = [e for items in files.values() for e in items]

    def todo(kind):
        return [e for e in entries if e["type"] == kind and (force or "feed" not in e) and only in (None, kind)]

    failed, review = [], []
    yt = todo("youtube")
    with cf.ThreadPoolExecutor(6) as ex:
        for e, title in zip(yt, ex.map(youtube, yt)):
            if title is None:
                failed.append(("youtube", e["id"], e["url"]))
            elif norm(title) != norm(e["name"]) and not (norm(title) in norm(e["name"]) or norm(e["name"]) in norm(title)):
                review.append(("youtube", e["id"], f"{e['name']!r} -> channel {title!r}"))

    pods = todo("podcast")
    with_id = [e for e in pods if "apple_podcast_id" in e.get("ids", {})]
    for e in podcasts_by_id(with_id) if with_id else []:
        failed.append(("podcast", e["id"], e["url"]))
    for e in (e for e in pods if "apple_podcast_id" not in e.get("ids", {})):
        status, matched = podcast_by_name(e)
        if status is None:
            failed.append(("podcast", e["id"], f"no match (top result: {matched})"))
        elif status == "fuzzy":
            review.append(("podcast", e["id"], f"{e['name']!r} -> {matched!r}"))

    # Websites without a discoverable feed are normal, so they are not reported.
    sites = todo("website") + todo("newsletter")
    with cf.ThreadPoolExecutor(8) as ex:
        found = sum(ex.map(website, sites))

    if "--transcripts" in sys.argv:
        cands = [e for e in entries if e["type"] == "podcast" and "feed" in e and "subtitles" not in e]
        with cf.ThreadPoolExecutor(8) as ex:
            for e, ok in zip(cands, ex.map(has_transcripts, cands)):
                if ok:
                    e["subtitles"] = "free"
        print(f"transcripts: {sum(e.get('subtitles') == 'free' for e in cands)} of {len(cands)} podcasts")
    if "--captions" in sys.argv:
        cands = [e for e in entries if e["type"] == "youtube" and "feed" in e and "subtitles" not in e]
        with cf.ThreadPoolExecutor(4) as ex:
            for e, ok in zip(cands, ex.map(captions, cands)):
                if ok:
                    e["subtitles"] = "free"
        print(f"captions: {sum(e.get('subtitles') == 'free' for e in cands)} of {len(cands)} channels")

    for e in entries:
        e.pop("_search", None)
    for p, items in files.items():
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"youtube {len(yt)}, podcast {len(pods)}, websites {len(sites)} ({found} feeds found) processed; "
          f"{len(failed)} unresolved, {len(review)} to review")
    for f in failed:
        print("  UNRESOLVED", *f)
    for r in review:
        print("  REVIEW    ", *r)


if __name__ == "__main__":
    main()
