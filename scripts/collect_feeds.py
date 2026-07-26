#!/usr/bin/env python3
"""零依赖体育聚合器：抓取 RSS、篮球/足球/LoL 赛程与虎扑社区热帖。"""
from __future__ import annotations

import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "public" / "data" / "sources.json"
FEED_PATH = ROOT / "public" / "data" / "feed.json"
LOL_SCHEDULE_URL = "https://lolesports.com/en-US?leagues=lpl%2Clck%2Clec"
LOL_LIVE_STATS_URL = "https://feed.lolesports.com/livestats/v1"
NBA_SCOREBOARD_LEAGUES = (
    ("nba", "NBA"),
    ("nba-summer-las-vegas", "NBA 夏季联赛"),
)
FOOTBALL_SCOREBOARD_LEAGUES = (
    ("eng.1", "英超"),
    ("esp.1", "西甲"),
    ("ita.1", "意甲"),
    ("ger.1", "德甲"),
    ("fra.1", "法甲"),
    ("uefa.champions", "欧冠"),
)
HUPU_BOARDS = {
    "nba": {"url": "https://bbs.hupu.com/nba-hot", "board": "虎扑篮球场"},
    "football": {"url": "https://bbs.hupu.com/topic-hot", "board": "虎扑足球话题区"},
    "lol": {"url": "https://bbs.hupu.com/lol-hot", "board": "虎扑英雄联盟"},
}
USER_AGENT = "Mozilla/5.0 (compatible; SidelinePersonalReader/1.0; personal RSS reader)"
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
EVENT_MARKER = '"__typename":"EventMatch"'
SHANGHAI = ZoneInfo("Asia/Shanghai")


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
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return datetime.now(timezone.utc).isoformat()


def fetch_source(source: dict[str, object]) -> list[dict[str, object]]:
    request = urllib.request.Request(str(source["url"]), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        root = ET.fromstring(response.read())
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    articles: list[dict[str, object]] = []
    for entry in entries[:25]:
        title = clean_text(first_text(entry, ("title",)))
        url = entry_link(entry)
        if not title or not url:
            continue
        summary = clean_text(first_text(entry, ("description", "summary", "content")))
        published = first_text(entry, ("pubdate", "published", "updated", "date"))
        identifier = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
        articles.append({
            "id": identifier,
            "sport": source["sport"],
            "title": title,
            "summary": summary[:240] or "点击查看原文详情。",
            "source": source["name"],
            "url": url,
            "publishedAt": normalize_date(published),
        })
    return articles


def fetch_bytes(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def application_json(page: str) -> dict[str, object]:
    candidates = re.findall(
        r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.I | re.S,
    )
    for candidate in sorted(candidates, key=len, reverse=True):
        try:
            value = json.loads(html.unescape(candidate))
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("页面中没有可解析的 application/json 数据")


def embedded_json_value(page: str, key: str) -> object:
    marker = f'"{key}":'
    start = page.find(marker)
    if start < 0:
        raise ValueError(f"页面中没有 {key} 数据")
    start += len(marker)
    while start < len(page) and page[start].isspace():
        start += 1
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(page[start:])
    return value


def find_mapping_with_key(value: object, key: str) -> dict[str, object] | None:
    if isinstance(value, dict):
        if key in value:
            return value
        for child in value.values():
            found = find_mapping_with_key(child, key)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_mapping_with_key(child, key)
            if found:
                return found
    return None


def fetch_hupu_posts(sport: str = "lol") -> list[dict[str, object]]:
    board_config = HUPU_BOARDS[sport]
    page = fetch_bytes(str(board_config["url"])).decode("utf-8", errors="replace")
    try:
        payload = application_json(page)
        container = find_mapping_with_key(payload, "threads")
        threads_value = container.get("threads") if container else None
    except ValueError:
        threads_value = embedded_json_value(page, "threads")
    threads = threads_value.get("list", []) if isinstance(threads_value, dict) else []
    collected_at = datetime.now(timezone.utc).isoformat()
    posts: list[dict[str, object]] = []
    for item in threads[:20]:
        if not isinstance(item, dict):
            continue
        thread_id = str(item.get("tid", ""))
        title = clean_text(str(item.get("title", "")))
        if not thread_id or not title:
            continue
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        posts.append({
            "id": f"hupu-{thread_id}",
            "sport": sport,
            "platform": "hupu",
            "region": "china",
            "board": board_config["board"],
            "title": title,
            "excerpt": "",
            "url": f"https://bbs.hupu.com/{thread_id}.html",
            "author": str(author.get("puname") or "虎扑用户"),
            "publishedAt": datetime.fromtimestamp(float(item.get("createdAt", 0)) / 1000, timezone.utc).isoformat(),
            "collectedAt": collected_at,
            "score": max(0, int(item.get("lights", 0))),
            "replyCount": max(0, int(item.get("replies", 0))),
            "viewCount": max(0, int(item.get("read", 0))),
            "topComments": [],
        })
    return posts


def percentile(value: int, values: list[int]) -> float:
    if len(values) <= 1:
        return 1.0
    below_or_equal = sum(candidate <= value for candidate in values)
    return (below_or_equal - 1) / (len(values) - 1)


def calculate_hot_scores(posts: list[dict[str, object]]) -> None:
    by_platform: dict[tuple[str, str], list[dict[str, object]]] = {}
    for post in posts:
        key = (str(post["platform"]), str(post["sport"]))
        by_platform.setdefault(key, []).append(post)
    now = datetime.now(timezone.utc)
    for platform_posts in by_platform.values():
        scores = [int(post.get("score", 0)) for post in platform_posts]
        replies = [int(post.get("replyCount", 0)) for post in platform_posts]
        for post in platform_posts:
            try:
                published = datetime.fromisoformat(str(post["publishedAt"]).replace("Z", "+00:00"))
                age_hours = max(0.0, (now - published).total_seconds() / 3600)
            except ValueError:
                age_hours = 72
            freshness = max(0.0, 1.0 - age_hours / 72)
            hot_score = (
                0.45 * percentile(int(post.get("score", 0)), scores)
                + 0.35 * percentile(int(post.get("replyCount", 0)), replies)
                + 0.20 * freshness
            )
            post["hotScore"] = round(min(1.0, max(0.0, hot_score)), 4)


def fetch_hupu_comments(post: dict[str, object]) -> tuple[str, list[dict[str, object]]]:
    page = fetch_bytes(str(post["url"]), timeout=10).decode("utf-8", errors="replace")
    payload = application_json(page)
    detail = find_mapping_with_key(payload, "thread")
    if not detail:
        return "", []
    thread = detail.get("thread") if isinstance(detail.get("thread"), dict) else {}
    excerpt = clean_text(str(thread.get("content", "")))[:240]
    comments_source: list[object] = []
    replies = detail.get("replies")
    if isinstance(replies, dict) and isinstance(replies.get("list"), list):
        comments_source.extend(replies["list"])
    if isinstance(detail.get("lights"), list):
        comments_source.extend(detail["lights"])
    deduped: dict[str, dict[str, object]] = {}
    for item in comments_source:
        if not isinstance(item, dict) or item.get("isHidden") or item.get("isDelete"):
            continue
        text = clean_text(str(item.get("content", "")))[:220]
        if text:
            score = max(0, int(item.get("count", item.get("allLightCount", 0)) or 0))
            deduped.setdefault(text, {"text": text, "score": score})
    comments = sorted(deduped.values(), key=lambda item: int(item["score"]), reverse=True)[:3]
    return excerpt, comments


def enrich_top_posts(posts: list[dict[str, object]], limit_per_sport: int = 3) -> None:
    for sport in HUPU_BOARDS:
        sport_posts = [post for post in posts if post.get("sport") == sport]
        for post in sorted(sport_posts, key=lambda item: float(item.get("hotScore", 0)), reverse=True)[:limit_per_sport]:
            try:
                excerpt, comments = fetch_hupu_comments(post)
                post["excerpt"] = excerpt
                post["topComments"] = comments
            except Exception as exc:
                print(f"评论读取失败：hupu {post['id']}：{exc}", file=sys.stderr)


def collect_community_posts(old_posts: list[dict[str, object]]) -> list[dict[str, object]]:
    combined: list[dict[str, object]] = []
    for sport in HUPU_BOARDS:
        try:
            posts = fetch_hupu_posts(sport)
            if not posts:
                raise ValueError("公开入口未返回帖子")
            combined.extend(posts)
            print(f"成功：虎扑 {sport} 社区，{len(posts)} 条")
        except Exception as exc:
            cached = [
                post for post in old_posts
                if post.get("platform") == "hupu" and post.get("sport") == sport
            ]
            combined.extend(cached)
            print(f"失败：虎扑 {sport} 社区：{exc}，保留 {len(cached)} 条旧数据。", file=sys.stderr)
    unique: dict[str, dict[str, object]] = {}
    for post in combined:
        unique.setdefault(str(post.get("id")), post)
    result = list(unique.values())
    calculate_hot_scores(result)
    enrich_top_posts(result)
    return sorted(result, key=lambda item: float(item.get("hotScore", 0)), reverse=True)


def decode_json_string(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value


def match_time_label(start_time: datetime) -> str:
    local_time = start_time.astimezone(SHANGHAI)
    today = datetime.now(SHANGHAI).date()
    if local_time.date() == today:
        prefix = "今日"
    elif local_time.date() == today + timedelta(days=1):
        prefix = "明日"
    elif local_time.date() == today - timedelta(days=1):
        prefix = "昨日"
    else:
        prefix = f"{local_time.month}月{local_time.day}日"
    return f"{prefix} {local_time:%H:%M}"


def parse_nba_match_details(payload: dict[str, object]) -> dict[str, object] | None:
    boxscore = payload.get("boxscore") if isinstance(payload.get("boxscore"), dict) else {}
    team_stats: list[dict[str, object]] = []
    selected_team_stats = {
        "fieldGoalsMade-fieldGoalsAttempted": "FG",
        "fieldGoalPct": "FG%",
        "threePointFieldGoalsMade-threePointFieldGoalsAttempted": "3PT",
        "threePointFieldGoalPct": "3P%",
        "freeThrowsMade-freeThrowsAttempted": "FT",
        "freeThrowPct": "FT%",
        "totalRebounds": "REB",
        "assists": "AST",
        "steals": "STL",
        "blocks": "BLK",
        "turnovers": "TO",
    }
    for entry in boxscore.get("teams", []):
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") if isinstance(entry.get("team"), dict) else {}
        values: dict[str, str] = {}
        for statistic in entry.get("statistics", []):
            if not isinstance(statistic, dict):
                continue
            key = selected_team_stats.get(str(statistic.get("name")))
            if key:
                values[key] = str(statistic.get("displayValue", "—"))
        if team.get("abbreviation") and values:
            team_stats.append({"team": str(team["abbreviation"]), "values": values})

    player_stats: list[dict[str, object]] = []
    selected_player_labels = {"MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "PF", "+/-"}
    for team_entry in boxscore.get("players", []):
        if not isinstance(team_entry, dict):
            continue
        team = team_entry.get("team") if isinstance(team_entry.get("team"), dict) else {}
        athletes: list[dict[str, object]] = []
        statistics_groups = team_entry.get("statistics", [])
        if not statistics_groups:
            continue
        statistics = statistics_groups[0]
        if not isinstance(statistics, dict):
            continue
        labels = [str(label) for label in statistics.get("labels", [])]
        for athlete_entry in statistics.get("athletes", []):
            if not isinstance(athlete_entry, dict) or athlete_entry.get("didNotPlay"):
                continue
            athlete = athlete_entry.get("athlete") if isinstance(athlete_entry.get("athlete"), dict) else {}
            raw_stats = athlete_entry.get("stats", [])
            values = {
                label: str(value)
                for label, value in zip(labels, raw_stats)
                if label in selected_player_labels
            }
            if athlete.get("displayName") and values:
                position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
                athletes.append({
                    "name": str(athlete["displayName"]),
                    "jersey": str(athlete.get("jersey", "")),
                    "position": str(position.get("abbreviation", "")),
                    "starter": bool(athlete_entry.get("starter")),
                    "stats": values,
                })
        if team.get("abbreviation") and athletes:
            player_stats.append({"team": str(team["abbreviation"]), "athletes": athletes})

    leaders: list[dict[str, object]] = []
    for team_entry in payload.get("leaders", []):
        if not isinstance(team_entry, dict):
            continue
        team = team_entry.get("team") if isinstance(team_entry.get("team"), dict) else {}
        categories: list[dict[str, str]] = []
        for category in team_entry.get("leaders", []):
            if not isinstance(category, dict) or not category.get("leaders"):
                continue
            leader = category["leaders"][0]
            athlete = leader.get("athlete") if isinstance(leader.get("athlete"), dict) else {}
            if athlete.get("displayName"):
                categories.append({
                    "label": str(category.get("displayName", "")),
                    "athlete": str(athlete["displayName"]),
                    "value": str(leader.get("displayValue", "")),
                })
        if team.get("abbreviation") and categories:
            leaders.append({"team": str(team["abbreviation"]), "categories": categories})

    game_info = payload.get("gameInfo") if isinstance(payload.get("gameInfo"), dict) else {}
    venue = game_info.get("venue") if isinstance(game_info.get("venue"), dict) else {}
    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    header_competitions = header.get("competitions", [])
    broadcasts: list[str] = []
    if header_competitions and isinstance(header_competitions[0], dict):
        for broadcast in header_competitions[0].get("broadcasts", []):
            if not isinstance(broadcast, dict):
                continue
            media = broadcast.get("media") if isinstance(broadcast.get("media"), dict) else {}
            if media.get("shortName"):
                broadcasts.append(str(media["shortName"]))

    if not team_stats and not player_stats and not leaders and not venue and not broadcasts:
        return None
    return {
        "venue": str(venue.get("fullName", "")),
        "broadcasts": list(dict.fromkeys(broadcasts)),
        "teamStats": team_stats,
        "playerStats": player_stats,
        "leaders": leaders,
    }


def fetch_nba_match_details(event_id: str, league_slug: str) -> dict[str, object] | None:
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        f"{league_slug}/summary?event={event_id}"
    )
    payload = json.loads(fetch_bytes(url, timeout=15).decode("utf-8"))
    return parse_nba_match_details(payload)


def fetch_nba_matches() -> list[dict[str, object]]:
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=7)).strftime("%Y%m%d")
    date_to = (now + timedelta(days=30)).strftime("%Y%m%d")
    matches_by_id: dict[str, dict[str, object]] = {}
    successful_sources = 0
    errors: list[str] = []

    for league_slug, competition_name in NBA_SCOREBOARD_LEAGUES:
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/"
            f"{league_slug}/scoreboard?dates={date_from}-{date_to}&limit=100"
        )
        try:
            payload = json.loads(fetch_bytes(url).decode("utf-8"))
            successful_sources += 1
        except Exception as exc:
            errors.append(f"{league_slug}: {exc}")
            continue

        for event in payload.get("events", []):
            event_id = str(event.get("id", ""))
            start_value = str(event.get("date", ""))
            competitions = event.get("competitions", [])
            if not event_id or not start_value or not competitions:
                continue
            try:
                start_time = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
            except ValueError:
                continue
            competitors = competitions[0].get("competitors", [])
            home_team = next((team for team in competitors if team.get("homeAway") == "home"), None)
            away_team = next((team for team in competitors if team.get("homeAway") == "away"), None)
            if not home_team or not away_team:
                continue

            status_type = event.get("status", {}).get("type", {})
            if status_type.get("completed"):
                status = "finished"
            elif status_type.get("state") == "in":
                status = "live"
            else:
                status = "upcoming"

            def team_label(team: dict[str, object]) -> str:
                details = team.get("team") if isinstance(team.get("team"), dict) else {}
                return str(details.get("abbreviation") or details.get("shortDisplayName") or details.get("displayName"))

            item: dict[str, object] = {
                "id": f"nba-{event_id}",
                "sport": "nba",
                "competition": competition_name,
                "home": team_label(home_team),
                "away": team_label(away_team),
                "status": status,
                "time": match_time_label(start_time),
                "startTime": start_time.isoformat(),
                "source": "ESPN",
            }
            if status in {"live", "finished"}:
                try:
                    item["homeScore"] = int(float(str(home_team.get("score", 0))))
                    item["awayScore"] = int(float(str(away_team.get("score", 0))))
                except ValueError:
                    pass
            try:
                details = fetch_nba_match_details(event_id, league_slug)
                if details:
                    item["details"] = details
            except Exception as exc:
                print(f"NBA 比赛详情读取失败：{event_id}：{exc}", file=sys.stderr)
            matches_by_id[event_id] = item

    if successful_sources == 0:
        raise RuntimeError("; ".join(errors) or "NBA 赛程来源均不可用")
    return sorted(matches_by_id.values(), key=lambda item: str(item["startTime"]))[:12]


def fetch_football_matches() -> list[dict[str, object]]:
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=7)).strftime("%Y%m%d")
    date_to = (now + timedelta(days=30)).strftime("%Y%m%d")
    matches_by_id: dict[str, dict[str, object]] = {}
    successful_sources = 0
    errors: list[str] = []

    for league_slug, competition_name in FOOTBALL_SCOREBOARD_LEAGUES:
        league_matches: list[dict[str, object]] = []
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{league_slug}/scoreboard?dates={date_from}-{date_to}&limit=100"
        )
        try:
            payload = json.loads(fetch_bytes(url).decode("utf-8"))
            successful_sources += 1
        except Exception as exc:
            errors.append(f"{league_slug}: {exc}")
            continue

        for event in payload.get("events", []):
            event_id = str(event.get("id", ""))
            start_value = str(event.get("date", ""))
            competitions = event.get("competitions", [])
            if not event_id or not start_value or not competitions:
                continue
            try:
                start_time = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
            except ValueError:
                continue
            competitors = competitions[0].get("competitors", [])
            home_team = next((team for team in competitors if team.get("homeAway") == "home"), None)
            away_team = next((team for team in competitors if team.get("homeAway") == "away"), None)
            if not home_team or not away_team:
                continue

            status_type = event.get("status", {}).get("type", {})
            if status_type.get("completed"):
                status = "finished"
            elif status_type.get("state") == "in":
                status = "live"
            else:
                status = "upcoming"

            def team_label(team: dict[str, object]) -> str:
                details = team.get("team") if isinstance(team.get("team"), dict) else {}
                return str(
                    details.get("shortDisplayName")
                    or details.get("abbreviation")
                    or details.get("displayName")
                )

            item: dict[str, object] = {
                "id": f"football-{event_id}",
                "sport": "football",
                "competition": competition_name,
                "home": team_label(home_team),
                "away": team_label(away_team),
                "status": status,
                "time": match_time_label(start_time),
                "startTime": start_time.isoformat(),
                "source": "ESPN",
            }
            if status in {"live", "finished"}:
                try:
                    item["homeScore"] = int(float(str(home_team.get("score", 0))))
                    item["awayScore"] = int(float(str(away_team.get("score", 0))))
                except ValueError:
                    pass
            league_matches.append(item)

        for item in sorted(
            league_matches,
            key=lambda match: str(match["startTime"]),
        )[:4]:
            matches_by_id.setdefault(str(item["id"]), item)

    if successful_sources == 0:
        raise RuntimeError("; ".join(errors) or "足球赛程来源均不可用")
    return sorted(matches_by_id.values(), key=lambda item: str(item["startTime"]))[:24]


def lol_timestamp(value: datetime) -> str:
    value = value.astimezone(timezone.utc).replace(
        second=(value.second // 10) * 10,
        microsecond=0,
    )
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_lol_game_details(
    game_id: str,
    game_number: int,
    metadata_payload: dict[str, object],
    final_window_payload: dict[str, object],
    final_details_payload: dict[str, object],
    team_names: dict[str, str],
) -> dict[str, object] | None:
    metadata = metadata_payload.get("gameMetadata")
    window_frames = final_window_payload.get("frames")
    detail_frames = final_details_payload.get("frames")
    initial_frames = metadata_payload.get("frames")
    if (
        not isinstance(metadata, dict)
        or not isinstance(window_frames, list)
        or not window_frames
        or not isinstance(detail_frames, list)
        or not detail_frames
    ):
        return None

    final_frame = window_frames[-1]
    detail_frame = detail_frames[-1]
    if not isinstance(final_frame, dict) or final_frame.get("gameState") != "finished":
        return None
    if not isinstance(detail_frame, dict):
        return None

    def team_data(side: str) -> tuple[dict[str, object], list[dict[str, object]]]:
        frame_key = f"{side}Team"
        metadata_key = f"{side}TeamMetadata"
        raw_team = final_frame.get(frame_key)
        raw_metadata = metadata.get(metadata_key)
        team = raw_team if isinstance(raw_team, dict) else {}
        team_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
        team_id = str(team_metadata.get("esportsTeamId", ""))
        dragons = team.get("dragons") if isinstance(team.get("dragons"), list) else []
        summary = {
            "id": team_id,
            "name": team_names.get(team_id, "蓝色方" if side == "blue" else "红色方"),
            "side": side,
            "gold": int(team.get("totalGold", 0) or 0),
            "kills": int(team.get("totalKills", 0) or 0),
            "towers": int(team.get("towers", 0) or 0),
            "dragons": len(dragons),
            "dragonTypes": [str(dragon) for dragon in dragons],
            "barons": int(team.get("barons", 0) or 0),
            "inhibitors": int(team.get("inhibitors", 0) or 0),
        }
        participants = team_metadata.get("participantMetadata")
        return summary, participants if isinstance(participants, list) else []

    blue_team, blue_metadata = team_data("blue")
    red_team, red_metadata = team_data("red")
    detail_by_id = {
        int(participant.get("participantId", 0) or 0): participant
        for participant in detail_frame.get("participants", [])
        if isinstance(participant, dict)
    }
    players: list[dict[str, object]] = []
    for team, participants in ((blue_team, blue_metadata), (red_team, red_metadata)):
        for participant in participants:
            if not isinstance(participant, dict):
                continue
            participant_id = int(participant.get("participantId", 0) or 0)
            stats = detail_by_id.get(participant_id, {})
            players.append({
                "participantId": participant_id,
                "team": team["name"],
                "side": team["side"],
                "name": str(participant.get("summonerName", "")),
                "role": str(participant.get("role", "")),
                "champion": str(participant.get("championId", "")),
                "level": int(stats.get("level", 0) or 0),
                "kills": int(stats.get("kills", 0) or 0),
                "deaths": int(stats.get("deaths", 0) or 0),
                "assists": int(stats.get("assists", 0) or 0),
                "gold": int(stats.get("totalGoldEarned", 0) or 0),
                "cs": int(stats.get("creepScore", 0) or 0),
                "killParticipation": float(stats.get("killParticipation", 0) or 0),
                "damageShare": float(stats.get("championDamageShare", 0) or 0),
                "wardsPlaced": int(stats.get("wardsPlaced", 0) or 0),
                "wardsDestroyed": int(stats.get("wardsDestroyed", 0) or 0),
                "items": [
                    int(item)
                    for item in stats.get("items", [])
                    if isinstance(item, (int, float, str)) and str(item).isdigit()
                ],
            })

    duration = 0
    if isinstance(initial_frames, list) and initial_frames and isinstance(initial_frames[0], dict):
        try:
            started = datetime.fromisoformat(str(initial_frames[0]["rfc460Timestamp"]).replace("Z", "+00:00"))
            finished = datetime.fromisoformat(str(final_frame["rfc460Timestamp"]).replace("Z", "+00:00"))
            duration = max(0, round((finished - started).total_seconds()))
        except (KeyError, ValueError):
            pass
    patch_parts = str(metadata.get("patchVersion", "")).split(".")
    return {
        "gameId": game_id,
        "gameNumber": game_number,
        "state": "finished",
        "patch": ".".join(patch_parts[:2]),
        "duration": duration,
        "teams": [blue_team, red_team],
        "players": players,
    }


def fetch_lol_game_details(
    game_id: str,
    game_number: int,
    match_start: datetime,
    team_names: dict[str, str],
) -> dict[str, object] | None:
    metadata_payload = json.loads(
        fetch_bytes(f"{LOL_LIVE_STATS_URL}/window/{game_id}", timeout=20).decode("utf-8")
    )
    probe_query = urllib.parse.urlencode({"startingTime": lol_timestamp(match_start + timedelta(hours=4))})
    final_window_payload = json.loads(
        fetch_bytes(
            f"{LOL_LIVE_STATS_URL}/window/{game_id}?{probe_query}",
            timeout=20,
        ).decode("utf-8")
    )
    frames = final_window_payload.get("frames", [])
    if not frames or not isinstance(frames[-1], dict) or frames[-1].get("gameState") != "finished":
        return None
    final_time = datetime.fromisoformat(str(frames[-1]["rfc460Timestamp"]).replace("Z", "+00:00"))
    detail_query = urllib.parse.urlencode({"startingTime": lol_timestamp(final_time)})
    final_details_payload = json.loads(
        fetch_bytes(
            f"{LOL_LIVE_STATS_URL}/details/{game_id}?{detail_query}",
            timeout=20,
        ).decode("utf-8")
    )
    return parse_lol_game_details(
        game_id,
        game_number,
        metadata_payload,
        final_window_payload,
        final_details_payload,
        team_names,
    )


def fetch_lol_matches() -> list[dict[str, object]]:
    request = urllib.request.Request(LOL_SCHEDULE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=35) as response:
        page = response.read().decode("utf-8", errors="replace")

    positions = [match.start() for match in re.finditer(re.escape(EVENT_MARKER), page)]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=2)
    window_end = now + timedelta(days=7)
    matches_by_id: dict[str, dict[str, object]] = {}

    for index, position in enumerate(positions):
        end = positions[index + 1] if index + 1 < len(positions) else min(len(page), position + 12000)
        block = page[position:end]
        header = re.search(
            r'"id":"([^"]+)","blockName":"([^"]*)","startTime":"([^"]+)","state":"([^"]+)"',
            block,
        )
        league = re.search(r'"__typename":"League","id":"[^"]+","name":"([^"]+)".*?"slug":"([^"]+)"', block)
        tournament = re.search(r'"__typename":"Tournament","id":"[^"]+","name":"([^"]+)"', block)
        teams = re.findall(
            r'"__typename":"MatchTeam","id":"[^"]+:([^"]+)","name":"((?:\\.|[^"])*)".*?"code":"((?:\\.|[^"])*)".*?"gameWins":(\d+),"outcome":(null|"[^"]*")',
            block,
        )
        if not header or not league or len(teams) < 2:
            continue

        match_id, _, start_value, event_state = header.groups()
        try:
            start_time = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if not window_start <= start_time <= window_end:
            continue

        state_key = event_state.lower().replace("_", "")
        if state_key in {"completed", "complete"}:
            status = "finished"
        elif state_key in {"inprogress", "live"}:
            status = "live"
        else:
            status = "upcoming"

        def team_label(team: tuple[str, str, str, str, str]) -> str:
            _, name, code, _, _ = team
            return decode_json_string(code or name)

        competition = decode_json_string(league.group(1))
        if tournament:
            competition = f"{competition} · {decode_json_string(tournament.group(1))}"

        item: dict[str, object] = {
            "id": f"lol-{match_id}",
            "sport": "lol",
            "competition": competition,
            "home": team_label(teams[0]),
            "away": team_label(teams[1]),
            "status": status,
            "time": match_time_label(start_time),
            "startTime": start_time.isoformat(),
            "source": "LoL Esports",
        }
        if status != "upcoming":
            item["homeScore"] = int(teams[0][3])
            item["awayScore"] = int(teams[1][3])
        if status == "finished" and competition.startswith("LPL"):
            strategy = re.search(
                r'"strategy":\{"__typename":"MatchStrategy","type":"bestOf","count":(\d+)\}',
                block,
            )
            games = re.findall(
                r'"__typename":"Game","id":"([^"]+)","state":"([^"]+)","number":(\d+)',
                block,
            )
            team_names = {
                team[0]: team_label(team)
                for team in teams[:2]
            }
            game_details: list[dict[str, object]] = []
            for game_id, game_state, game_number in games:
                if game_state != "completed":
                    continue
                try:
                    details = fetch_lol_game_details(
                        game_id,
                        int(game_number),
                        start_time,
                        team_names,
                    )
                    if details:
                        game_details.append(details)
                except Exception as exc:
                    print(f"LoL 单局详情读取失败：{game_id}：{exc}", file=sys.stderr)
            if game_details:
                item["details"] = {
                    "kind": "lol",
                    "format": f"BO{strategy.group(1)}" if strategy else "",
                    "games": sorted(game_details, key=lambda game: int(game["gameNumber"])),
                }
        matches_by_id[match_id] = item

    return sorted(matches_by_id.values(), key=lambda item: str(item["startTime"]))[:12]


def merge_cached_lol_details(
    old_matches: list[dict[str, object]],
    lol_matches: list[dict[str, object]],
) -> list[dict[str, object]]:
    cached_lol = {
        str(item.get("id")): item
        for item in old_matches
        if (
            item.get("sport") == "lol"
            and str(item.get("competition", "")).startswith("LPL")
            and isinstance(item.get("details"), dict)
        )
    }
    for item in lol_matches:
        cached = cached_lol.get(str(item.get("id")))
        if "details" not in item and cached:
            item["details"] = cached["details"]
    return lol_matches


def refresh_lol_only() -> int:
    old_feed = json.loads(FEED_PATH.read_text(encoding="utf-8-sig"))
    old_matches = old_feed.get("matches", [])
    lol_matches = merge_cached_lol_details(old_matches, fetch_lol_matches())
    old_feed["matches"] = [
        item for item in old_matches if item.get("sport") != "lol"
    ] + lol_matches
    old_feed["updatedAt"] = datetime.now(timezone.utc).isoformat()
    FEED_PATH.write_text(
        json.dumps(old_feed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"完成：更新 {len(lol_matches)} 场 LoL Esports 赛程与 LPL 详情。")
    return 0


def refresh_football_only() -> int:
    old_feed = json.loads(FEED_PATH.read_text(encoding="utf-8-sig"))
    old_matches = old_feed.get("matches", [])
    football_matches = fetch_football_matches()
    old_feed["matches"] = [
        item for item in old_matches if item.get("sport") != "football"
    ] + football_matches
    old_feed["updatedAt"] = datetime.now(timezone.utc).isoformat()
    FEED_PATH.write_text(
        json.dumps(old_feed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"完成：更新 {len(football_matches)} 场欧洲足球赛程。")
    return 0


def main() -> int:
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8-sig"))
    old_feed = json.loads(FEED_PATH.read_text(encoding="utf-8-sig"))
    articles: list[dict[str, object]] = []

    for source in sources:
        if not source.get("enabled", True) or source.get("sport") == "lol":
            continue
        try:
            fetched = fetch_source(source)
            articles.extend(fetched)
            print(f"成功：{source['name']}，{len(fetched)} 条")
        except Exception as exc:
            print(f"失败：{source['name']}：{exc}", file=sys.stderr)

    deduped: dict[str, dict[str, object]] = {}
    for article in articles:
        deduped.setdefault(re.sub(r"\W+", "", str(article["title"]).lower()), article)
    result = sorted(deduped.values(), key=lambda article: str(article["publishedAt"]), reverse=True)[:60]
    if not result:
        print("所有资讯来源均未返回数据，保留现有 feed.json。", file=sys.stderr)
        return 1

    for sport in ("nba", "football"):
        first = next((item for item in result if item["sport"] == sport), None)
        if first:
            first["featured"] = True

    old_matches = old_feed.get("matches", [])
    try:
        nba_matches = fetch_nba_matches()
        matches = [item for item in old_matches if item.get("sport") != "nba"] + nba_matches
        if nba_matches:
            print(f"成功：NBA 近期赛程，{len(nba_matches)} 场")
        else:
            print("成功：NBA 赛程来源可用，当前窗口暂无比赛。")
    except Exception as exc:
        cached_nba = [
            item for item in old_matches
            if item.get("sport") == "nba" and not item.get("demo")
        ]
        matches = [item for item in old_matches if item.get("sport") != "nba"] + cached_nba
        print(f"失败：NBA 赛程：{exc}，保留 {len(cached_nba)} 场旧的真实赛程。", file=sys.stderr)

    try:
        football_matches = fetch_football_matches()
        matches = [
            item for item in matches if item.get("sport") != "football"
        ] + football_matches
        if football_matches:
            print(f"成功：欧洲足球近期赛程，{len(football_matches)} 场")
        else:
            print("成功：欧洲足球赛程来源可用，当前窗口暂无比赛。")
    except Exception as exc:
        cached_football = [
            item for item in old_matches
            if item.get("sport") == "football" and not item.get("demo")
        ]
        matches = [
            item for item in matches if item.get("sport") != "football"
        ] + cached_football
        print(
            f"失败：欧洲足球赛程：{exc}，保留 {len(cached_football)} 场旧的真实赛程。",
            file=sys.stderr,
        )

    try:
        lol_matches = fetch_lol_matches()
        if lol_matches:
            lol_matches = merge_cached_lol_details(old_matches, lol_matches)
            matches = [item for item in matches if item.get("sport") != "lol"] + lol_matches
            print(f"成功：LoL Esports 近期赛程，{len(lol_matches)} 场")
        else:
            print("LoL Esports 未返回近期比赛，保留现有赛程。", file=sys.stderr)
    except Exception as exc:
        print(f"失败：LoL Esports 赛程：{exc}，保留现有赛程。", file=sys.stderr)

    community_posts = collect_community_posts(old_feed.get("communityPosts", []))
    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "matches": matches,
        "articles": result,
        "communityPosts": community_posts,
    }
    FEED_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成：写入 {len(result)} 条资讯、{len(matches)} 场比赛、{len(community_posts)} 条社区热帖。")
    return 0


if __name__ == "__main__":
    if "--lol-only" in sys.argv:
        raise SystemExit(refresh_lol_only())
    if "--football-only" in sys.argv:
        raise SystemExit(refresh_football_only())
    raise SystemExit(main())
