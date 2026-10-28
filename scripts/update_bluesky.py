#!/usr/bin/env python3
"""Curated public Bluesky author feeds; no credentials or third-party packages."""
import datetime as dt
import json
import pathlib
import re
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "social.json"
# Domain handles and documented public identities; failures are skipped, never fabricated.
ACCOUNTS = [
    ("playstation.com", "OFFICIAL"),
    ("xbox.com", "OFFICIAL"),
    ("valvesoftware.com", "OFFICIAL"),
    ("remedygames.com", "OFFICIAL"),
    ("ign.com", "REPORTED"),
    ("polygon.com", "REPORTED"),
    ("nintendolife.com", "REPORTED"),
    ("gameinformer.com", "REPORTED"),
    ("jasonschreier.bsky.social", "ANALYSIS"),
    ("lucyjames.games", "ANALYSIS"),
]
TOPICS = re.compile(r"\b(game|gaming|playstation|xbox|nintendo|steam|switch|ps5|console|anime|manga|comic|film|movie|trailer|developer|studio|release|launch|review|industry|rpg|sequel|dlc|patch|update|direct|showcase|remake|remaster|indie|horror|play|episode)\b", re.I)
def fetch(handle):
    q = urllib.parse.urlencode({"actor": handle, "filter": "posts_no_replies", "limit": 35})
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + q
    req = urllib.request.Request(url, headers={"User-Agent": "PULSE-NewsRadar/1.0 (public curated reader)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=18) as res:
        return json.load(res).get("feed", [])
def main():
    old = []
    try: old = json.loads(OUT.read_text(encoding="utf-8")).get("posts", [])
    except (OSError, ValueError): pass
    now = dt.datetime.now(dt.timezone.utc)
    posts = []
    successful = 0
    for handle, label in ACCOUNTS:
        try:
            feed = fetch(handle)
            successful += 1
            print(f"{handle}: {len(feed)} feed entries")
        except Exception as exc:
            print(f"WARNING {handle}: {exc}")
            continue
        for item in feed:
            if item.get("reason") or item.get("reply"): continue
            post = item.get("post") or {}
            author = post.get("author") or {}
            # Do not accidentally include reposts or unrelated authors.
            if author.get("handle", "").lower() != handle.lower(): continue
            record = post.get("record") or {}
            text = str(record.get("text") or "").strip()
            if not text or len(text) < 35 or not TOPICS.search(text): continue
            langs = record.get("langs") or []
            if langs and "en" not in langs: continue
            if not langs and not re.search(r"\b(the|and|for|with|new|from|this|will|our|today|game|games)\b", text, re.I): continue
            uri = post.get("uri", "")
            if not uri.startswith("at://") or "/app.bsky.feed.post/" not in uri: continue
            rkey = uri.rsplit("/", 1)[-1]
            url = "https://bsky.app/profile/" + urllib.parse.quote(author.get("did", handle), safe=":") + "/post/" + urllib.parse.quote(rkey, safe="")
            published = record.get("createdAt") or post.get("indexedAt") or ""
            posts.append({"url": url, "text": text[:500], "author": author.get("displayName") or handle, "handle": handle, "avatar": author.get("avatar") or "", "label": label, "language": "en", "published": published, "platform": "Bluesky"})
    if successful == 0:
        if old:
            print("All Bluesky sources unavailable; retaining previous data.")
            return
        raise RuntimeError("All Bluesky sources unavailable; refusing empty overwrite")
    # Preserve recent posts during temporary outages, without inventing data.
    posts.extend(old)
    seen_urls = set()
    seen_texts = set()
    unique = []
    for p in sorted(posts, key=lambda x: x.get("published") or "", reverse=True):
        url = p.get("url", "")
        key = re.sub(r"[^a-z0-9]", "", p.get("text", "").lower())[:120]
        if not url or url in seen_urls or key in seen_texts: continue
        try:
            stamp = dt.datetime.fromisoformat(p.get("published", "").replace("Z", "+00:00"))
            if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=dt.timezone.utc)
            if stamp < now - dt.timedelta(days=14): continue
        except (ValueError, TypeError): continue
        seen_urls.add(url)
        seen_texts.add(key)
        unique.append(p)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": now.isoformat(), "posts": unique[:80]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {min(len(unique), 80)} Bluesky posts")
if __name__ == "__main__": main()
