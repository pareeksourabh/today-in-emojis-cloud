#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-driven daily emoji generator for Today in Emojis.

- Fetch up to 10 headlines per RSS source (balanced sampling; max 40 total)
- Ask an LLM (OpenAI) to select 5 important, diverse items and assign 1 emoji each
- Strictly validate response; retry once; safe fallback if needed
- Write data/today.json and append data/history.json

Secret:
- OPENAI_API_KEY
"""

import os, sys, json, random, datetime, time, http.client, re, html
from typing import List, Dict, Any
from urllib.request import urlopen, Request

try:
    import feedparser  # pip install feedparser
except Exception:
    print("Missing dependency 'feedparser'. Install it first: pip install feedparser", file=sys.stderr)
    sys.exit(1)

# -----------------------
# Config
# -----------------------
RSS_SOURCES = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com&ceid=US:en&hl=en-US&gl=US",  # Reuters via Google News
    "https://www.theguardian.com/world/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",  # NY Times World
]
PER_SOURCE_LIMIT = 10     # up to 10 from each source
MAX_ITEMS = 40            # cap after merge
PICK_COUNT = 5            # final emojis count

OUTPUT_TODAY = "public/data/today.json"
OUTPUT_HISTORY = "data/history.json"

USER_AGENT = "Mozilla/5.0 (compatible; TodayInEmojis/1.0; +https://github.com)"
TIMEOUT = 25

# OpenAI model
OPENAI_MODEL = "gpt-4o-mini"

# -----------------------
# Helpers
# -----------------------
def fetch_feed_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()

def clean_summary(text: str) -> str:
    """Strip HTML and compact whitespace for short summaries."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 240:
        text = text[:237].rstrip() + "..."
    return text

def collect_headlines() -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for url in RSS_SOURCES:
        try:
            data = fetch_feed_bytes(url)
            feed = feedparser.parse(data)
            count = 0
            for e in feed.get("entries", []):
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                summary_raw = (
                    e.get("summary")
                    or (e.get("summary_detail") or {}).get("value")
                    or e.get("description")
                    or ""
                )
                summary = clean_summary(summary_raw)
                if not title or not link:
                    continue
                entries.append({"title": title, "url": link, "summary": summary})
                count += 1
                if count >= PER_SOURCE_LIMIT:
                    break
        except Exception as ex:
            print(f"[warn] RSS fetch failed: {url} -> {ex}", file=sys.stderr)
            continue

    # Shuffle to avoid ordering bias; then cap overall to MAX_ITEMS
    random.shuffle(entries)
    return entries[:MAX_ITEMS]

def unique_urls(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        u = it.get("url")
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def safe_defaults() -> Dict[str, Any]:
    return {
        "date": datetime.date.today().isoformat(),
        "emojis": [
            {"char": "🌍", "label": "world", "url": "", "title": "", "summary": ""},
            {"char": "💡", "label": "insight", "url": "", "title": "", "summary": ""},
            {"char": "🤝", "label": "together", "url": "", "title": "", "summary": ""},
            {"char": "🌱", "label": "growth", "url": "", "title": "", "summary": ""},
            {"char": "😐", "label": "neutral", "url": "", "title": "", "summary": ""},
        ],
        "source": "fallback",
    }

def normalize_json_text(raw: str) -> str:
    """Normalize JSON-like strings from LLMs by stripping fences and whitespace."""
    if not isinstance(raw, str):
        raise ValueError("LLM response is not text")
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if not candidate:
                continue
            if candidate.lower().startswith("json"):
                candidate = candidate[4:].strip()
            if candidate:
                return candidate
        return ""
    if text and text[0] not in "[{":
        for marker in ("[", "{"):
            idx = text.find(marker)
            if idx != -1:
                return text[idx:].strip()
        return text
    return text

def validate_response(raw: str, allowed_urls: List[str], headlines: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Expect STRICT JSON (no prose):
    [
      {"emoji": "💹", "label": "markets", "url": "<one of allowed_urls>"},
      ... x5
    ]
    """
    print(f"[debug] Validating response (length: {len(raw)} chars)", file=sys.stderr)

    cleaned = normalize_json_text(raw)
    print(f"[debug] Cleaned JSON (first 300 chars): {cleaned[:300]}", file=sys.stderr)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as ex:
        print(f"[debug] JSON parse error at position {ex.pos}: {ex.msg}", file=sys.stderr)
        print(f"[debug] Context around error: {cleaned[max(0,ex.pos-50):ex.pos+50]}", file=sys.stderr)
        raise ValueError(f"Invalid JSON: {ex.msg} (char {ex.pos})") from ex

    if isinstance(data, dict):
        selections = data.get("selections")
        if not isinstance(selections, list):
            print(f"[debug] Data is dict but missing 'selections'. Keys: {list(data.keys())}", file=sys.stderr)
            raise ValueError("JSON object missing 'selections' list")
        data = selections

    if not isinstance(data, list):
        raise ValueError(f"Expected a list, got {type(data)}")

    if len(data) != PICK_COUNT:
        print(f"[debug] Got {len(data)} items instead of {PICK_COUNT}", file=sys.stderr)
        raise ValueError(f"Expected {PICK_COUNT} items, got {len(data)}")

    # Create URL to title/summary mapping
    url_to_title = {h["url"]: h["title"] for h in headlines}
    url_to_summary = {h["url"]: h.get("summary", "") for h in headlines}

    seen_urls = set()
    results: List[Dict[str, str]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Item {i} not an object")
        emoji = item.get("emoji")
        label = item.get("label")
        url = item.get("url")
        if not (isinstance(emoji, str) and 1 <= len(emoji) <= 4):
            raise ValueError(f"Item {i} invalid emoji: {repr(emoji)}")
        if isinstance(label, str):
            label = label.strip()
            if len(label) > 48:
                label = label[:48].rstrip()
        if not (isinstance(label, str) and 1 <= len(label) <= 48):
            raise ValueError(f"Item {i} invalid label: {repr(label)}")
        if not (isinstance(url, str) and url in allowed_urls):
            print(f"[debug] Item {i} URL '{url[:100]}' not in allowed set", file=sys.stderr)
            raise ValueError(f"Item {i} url not in allowed set")
        if url in seen_urls:
            raise ValueError(f"Duplicate url at item {i}")
        seen_urls.add(url)

        # Get the original headline title from the URL
        title = url_to_title.get(url, label)
        summary = url_to_summary.get(url, "")
        results.append({"char": emoji, "label": label, "url": url, "title": title, "summary": summary})

    print(f"[debug] Validation successful: {len(results)} items", file=sys.stderr)
    return results

def to_today_json(items: List[Dict[str, str]]) -> Dict[str, Any]:
    now = datetime.datetime.utcnow()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "emojis": items,
        "source": "ai-openai",
    }

# -----------------------
# LLM call
# -----------------------
def openai_call(headlines: List[Dict[str, str]]) -> str:
    """Call the OpenAI Responses API via HTTPS with a strict JSON schema."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    items = [{"idx": i + 1, "title": h["title"], "url": h["url"]} for i, h in enumerate(headlines)]
    allowed_urls = [h["url"] for h in headlines]

    system = (
        "You select the day's 5 most important and diverse news items from a provided list, "
        "assign exactly one fitting emoji to each, and respond using the required JSON schema."
    )
    user_payload = {
        "task": (
            "Review the provided headlines, pick 5 unique items that cover different topics, "
            "assign a single emoji to each, craft a short lowercase label (<=48 chars), "
            "and copy the exact URL from the allowed list."
        ),
        "headlines": items,
        "allowed_urls": allowed_urls,
        "rules": [
            "Return JSON only.",
            "Use the provided schema exactly.",
            "Do not include explanations or additional properties."
        ],
    }

    schema = {
        "type": "object",
        "properties": {
            "selections": {
                "type": "array",
                "minItems": PICK_COUNT,
                "maxItems": PICK_COUNT,
                "items": {
                    "type": "object",
                    "required": ["emoji", "label", "url"],
                    "additionalProperties": False,
                    "properties": {
                        "emoji": {"type": "string", "minLength": 1, "maxLength": 4},
                        "label": {"type": "string", "minLength": 1, "maxLength": 48},
                        "url": {"type": "string", "enum": allowed_urls},
                    },
                },
            }
        },
        "required": ["selections"],
        "additionalProperties": False,
    }

    body = json.dumps({
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "max_tokens": 1000,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "emoji_selection",
                "schema": schema,
                "strict": True,
            }
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    })

    conn = http.client.HTTPSConnection("api.openai.com", timeout=30)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    conn.request("POST", "/v1/chat/completions", body=body.encode("utf-8"), headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()

    if resp.status < 200 or resp.status >= 300:
        error_msg = data.decode('utf-8', 'ignore')
        print(f"[debug] OpenAI API error {resp.status}: {error_msg[:500]}", file=sys.stderr)
        raise RuntimeError(f"OpenAI error {resp.status}: {error_msg[:200]}")

    # Parse the response
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as e:
        raw_text = data.decode('utf-8', 'ignore')
        print(f"[debug] Failed to parse OpenAI response. Raw data (first 1000 chars): {raw_text[:1000]}", file=sys.stderr)
        raise RuntimeError(f"Failed to parse OpenAI response: {e}")

    # Debug: show full response structure
    print(f"[debug] OpenAI response keys: {list(payload.keys())}", file=sys.stderr)

    # Extract text from Chat Completions response
    choices = payload.get("choices", [])
    if not choices:
        snippet = json.dumps(payload, ensure_ascii=False)[:1000]
        print(f"[debug] No choices in OpenAI response. Full payload: {snippet}", file=sys.stderr)
        raise RuntimeError("OpenAI response missing choices")

    message = choices[0].get("message", {})
    text = message.get("content", "").strip()

    if not text:
        snippet = json.dumps(payload, ensure_ascii=False)[:1000]
        print(f"[debug] Empty content in OpenAI response. Full payload: {snippet}", file=sys.stderr)
        raise RuntimeError("OpenAI response empty")

    print(f"[debug] Extracted text length: {len(text)} chars", file=sys.stderr)
    print(f"[debug] First 200 chars: {text[:200]}", file=sys.stderr)

    return text

# -----------------------
# Main
# -----------------------
def main():
    headlines = unique_urls(collect_headlines())
    if not headlines:
        print("[warn] No headlines, writing safe defaults.")
        os.makedirs(os.path.dirname(OUTPUT_TODAY), exist_ok=True)
        with open(OUTPUT_TODAY, "w", encoding="utf-8") as f:
            json.dump(safe_defaults(), f, ensure_ascii=False, indent=2)
        return 0

    allowed_urls = [h["url"] for h in headlines]

    # Call LLM with one retry on validation failure
    tries = 0
    results = None
    while tries < 2 and results is None:
        tries += 1
        try:
            raw = openai_call(headlines)
            items = validate_response(raw, allowed_urls, headlines)
            results = items
        except Exception as e:
            print(f"[warn] LLM parse/validation failed (try {tries}): {e}", file=sys.stderr)
            time.sleep(2)

    if results is None:
        print("[warn] Falling back to safe defaults.", file=sys.stderr)
        data = safe_defaults()
    else:
        data = to_today_json(results)

    # Write today.json
    os.makedirs(os.path.dirname(OUTPUT_TODAY), exist_ok=True)
    with open(OUTPUT_TODAY, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Append history.json
    try:
        hist = []
        if os.path.exists(OUTPUT_HISTORY):
            with open(OUTPUT_HISTORY, "r", encoding="utf-8") as f:
                hist = json.load(f)
                if not isinstance(hist, list):
                    hist = []
        hist.append({
            "date": datetime.date.today().isoformat(),
            "emojis": data["emojis"],
            "meta": {"provider": "openai", "total_candidates": len(headlines)}
        })
        with open(OUTPUT_HISTORY, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] Could not append history: {e}", file=sys.stderr)

    # Console log
    print("[info] Selected:")
    for it in data["emojis"]:
        print(f" - {it['char']} {it['label']}: {it['url']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
