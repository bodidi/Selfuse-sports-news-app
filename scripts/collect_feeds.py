#!/usr/bin/env python3
"""零依赖 RSS/Atom 聚合器：读取 sources.json，输出 PWA 使用的 feed.json。"""
from __future__ import annotations
import email.utils, hashlib, html, json, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "public" / "data" / "sources.json"
FEED_PATH = ROOT / "public" / "data" / "feed.json"
USER_AGENT = "SidelinePersonalReader/1.0 (+personal RSS reader)"
TAG_RE, SPACE_RE = re.compile(r"<[^>]+>"), re.compile(r"\s+")

def clean_text(value: str | None) -> str:
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", value or ""))).strip()

def first_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() in names and child.text:
            return child.text.strip()
    return ""

def entry_link(element: ET.Element) -> str:
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() == "link":
            return child.attrib.get("href") or (child.text or "").strip()
    return ""

def normalize_date(value: str) -> str:
    if not value: return datetime.now(timezone.utc).isoformat()
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).isoformat()
    except (TypeError, ValueError):
        try: return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError: return datetime.now(timezone.utc).isoformat()

def fetch_source(source: dict[str, object]) -> list[dict[str, object]]:
    request = urllib.request.Request(str(source["url"]), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    entries = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    articles = []
    for entry in entries[:25]:
        title, url = clean_text(first_text(entry, ("title",))), entry_link(entry)
        if not title or not url: continue
        summary = clean_text(first_text(entry, ("description", "summary", "content")))
        published = first_text(entry, ("pubdate", "published", "updated", "date"))
        identifier = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
        articles.append({"id": identifier, "sport": source["sport"], "title": title, "summary": summary[:240] or "点击查看原文详情。", "source": source["name"], "url": url, "publishedAt": normalize_date(published)})
    return articles

def main() -> int:
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8-sig"))
    old_feed = json.loads(FEED_PATH.read_text(encoding="utf-8-sig"))
    articles = []
    for source in sources:
        if not source.get("enabled", True): continue
        try:
            fetched = fetch_source(source); articles.extend(fetched)
            print(f"成功：{source['name']}，{len(fetched)} 条")
        except Exception as exc:
            print(f"失败：{source['name']}：{exc}", file=sys.stderr)
    deduped = {}
    for article in articles:
        deduped.setdefault(re.sub(r"\W+", "", str(article["title"]).lower()), article)
    result = sorted(deduped.values(), key=lambda a: str(a["publishedAt"]), reverse=True)[:60]
    if not result:
        print("所有来源均未返回数据，保留现有 feed.json。", file=sys.stderr); return 1
    for sport in ("nba", "football", "lol"):
        first = next((item for item in result if item["sport"] == sport), None)
        if first: first["featured"] = True
    output = {"updatedAt": datetime.now(timezone.utc).isoformat(), "matches": old_feed.get("matches", []), "articles": result}
    FEED_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：写入 {len(result)} 条资讯。")
    return 0

if __name__ == "__main__": raise SystemExit(main())
