import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "collect_feeds", Path(__file__).parents[1] / "scripts" / "collect_feeds.py"
)
collect_feeds = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(collect_feeds)


def post(sport: str, identifier: str, score: int, replies: int) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"hupu-{sport}-{identifier}",
        "sport": sport,
        "platform": "hupu",
        "region": "test",
        "board": "test",
        "title": identifier,
        "excerpt": "",
        "url": f"https://example.com/{identifier}",
        "author": "test",
        "publishedAt": now,
        "collectedAt": now,
        "score": score,
        "replyCount": replies,
        "topComments": [],
    }


class CommunityCollectionTests(unittest.TestCase):
    def test_hot_score_is_normalized_within_platform(self) -> None:
        posts = [post("nba", "low", 1, 2), post("nba", "high", 10, 20)]
        collect_feeds.calculate_hot_scores(posts)
        self.assertGreater(posts[1]["hotScore"], posts[0]["hotScore"])
        self.assertTrue(all(0 <= item["hotScore"] <= 1 for item in posts))

    def test_single_source_failure_keeps_only_that_sources_cache(self) -> None:
        cached = [post("football", "cached", 4, 5)]

        def fetch(sport: str) -> list[dict[str, object]]:
            if sport == "football":
                raise RuntimeError("blocked")
            return [post(sport, "fresh", 10, 8)]

        with (
            patch.object(collect_feeds, "fetch_hupu_posts", side_effect=fetch),
            patch.object(collect_feeds, "enrich_top_posts"),
        ):
            result = collect_feeds.collect_community_posts(cached)
        self.assertEqual(
            {item["id"] for item in result},
            {"hupu-nba-fresh", "hupu-football-cached", "hupu-lol-fresh"},
        )


class NbaScheduleTests(unittest.TestCase):
    def test_parses_finished_game_and_scores(self) -> None:
        start_time = datetime.now(timezone.utc).isoformat()
        payload = {
            "events": [{
                "id": "401",
                "date": start_time,
                "status": {"type": {"completed": True, "state": "post"}},
                "competitions": [{"competitors": [
                    {"homeAway": "home", "score": "101", "team": {"abbreviation": "BOS"}},
                    {"homeAway": "away", "score": "99", "team": {"abbreviation": "LAL"}},
                ]}],
            }]
        }
        with patch.object(
            collect_feeds,
            "fetch_bytes",
            return_value=json.dumps(payload).encode("utf-8"),
        ):
            matches = collect_feeds.fetch_nba_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["home"], "BOS")
        self.assertEqual(matches[0]["away"], "LAL")
        self.assertEqual(matches[0]["homeScore"], 101)
        self.assertEqual(matches[0]["status"], "finished")
        self.assertEqual(matches[0]["source"], "ESPN")

    def test_successful_empty_sources_return_empty_schedule(self) -> None:
        with patch.object(
            collect_feeds,
            "fetch_bytes",
            return_value=b'{"events":[]}',
        ):
            self.assertEqual(collect_feeds.fetch_nba_matches(), [])

    def test_parses_compact_boxscore_details(self) -> None:
        payload = {
            "boxscore": {
                "teams": [{
                    "team": {"abbreviation": "BOS"},
                    "statistics": [
                        {"name": "fieldGoalPct", "displayValue": "51"},
                        {"name": "totalRebounds", "displayValue": "44"},
                    ],
                }],
                "players": [{
                    "team": {"abbreviation": "BOS"},
                    "statistics": [{
                        "labels": ["MIN", "PTS", "REB", "AST"],
                        "athletes": [{
                            "starter": True,
                            "didNotPlay": False,
                            "athlete": {
                                "displayName": "Test Player",
                                "jersey": "1",
                                "position": {"abbreviation": "G"},
                            },
                            "stats": ["30", "20", "8", "6"],
                        }],
                    }],
                }],
            },
            "leaders": [{
                "team": {"abbreviation": "BOS"},
                "leaders": [{
                    "displayName": "Points",
                    "leaders": [{
                        "displayValue": "20",
                        "athlete": {"displayName": "Test Player"},
                    }],
                }],
            }],
            "gameInfo": {"venue": {"fullName": "Test Arena"}},
            "header": {"competitions": [{"broadcasts": [{"media": {"shortName": "ESPN"}}]}]},
        }
        details = collect_feeds.parse_nba_match_details(payload)
        self.assertIsNotNone(details)
        self.assertEqual(details["venue"], "Test Arena")
        self.assertEqual(details["broadcasts"], ["ESPN"])
        self.assertEqual(details["teamStats"][0]["values"]["FG%"], "51")
        self.assertEqual(details["playerStats"][0]["athletes"][0]["stats"]["PTS"], "20")
        self.assertEqual(details["leaders"][0]["categories"][0]["athlete"], "Test Player")


class FootballScheduleTests(unittest.TestCase):
    def test_parses_finished_match_and_scores(self) -> None:
        start_time = datetime.now(timezone.utc).isoformat()
        payload = {
            "events": [{
                "id": "701",
                "date": start_time,
                "status": {"type": {"completed": True, "state": "post"}},
                "competitions": [{"competitors": [
                    {
                        "homeAway": "home",
                        "score": "2",
                        "team": {"shortDisplayName": "Arsenal"},
                    },
                    {
                        "homeAway": "away",
                        "score": "1",
                        "team": {"shortDisplayName": "Liverpool"},
                    },
                ]}],
            }]
        }
        def fetch(url: str, **_: object) -> bytes:
            value = payload if "/eng.1/" in url else {"events": []}
            return json.dumps(value).encode("utf-8")

        with patch.object(collect_feeds, "fetch_bytes", side_effect=fetch):
            matches = collect_feeds.fetch_football_matches()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["competition"], "英超")
        self.assertEqual(matches[0]["home"], "Arsenal")
        self.assertEqual(matches[0]["away"], "Liverpool")
        self.assertEqual(matches[0]["homeScore"], 2)
        self.assertEqual(matches[0]["awayScore"], 1)
        self.assertEqual(matches[0]["status"], "finished")
        self.assertEqual(matches[0]["source"], "ESPN")

    def test_successful_empty_sources_return_empty_schedule(self) -> None:
        with patch.object(
            collect_feeds,
            "fetch_bytes",
            return_value=b'{"events":[]}',
        ):
            self.assertEqual(collect_feeds.fetch_football_matches(), [])


class LolDetailsTests(unittest.TestCase):
    def test_parses_finished_game_details(self) -> None:
        participants = [
            {
                "participantId": identifier,
                "summonerName": f"Player{identifier}",
                "championId": f"Champion{identifier}",
                "role": "top" if identifier in {1, 6} else "mid",
            }
            for identifier in range(1, 11)
        ]
        metadata_payload = {
            "gameMetadata": {
                "patchVersion": "16.14.794.5912",
                "blueTeamMetadata": {
                    "esportsTeamId": "team-blue",
                    "participantMetadata": participants[:5],
                },
                "redTeamMetadata": {
                    "esportsTeamId": "team-red",
                    "participantMetadata": participants[5:],
                },
            },
            "frames": [{"rfc460Timestamp": "2026-07-25T07:14:02.000Z"}],
        }
        final_window_payload = {
            "frames": [{
                "rfc460Timestamp": "2026-07-25T07:42:17.000Z",
                "gameState": "finished",
                "blueTeam": {
                    "totalGold": 58531,
                    "totalKills": 12,
                    "towers": 8,
                    "dragons": ["infernal", "mountain", "ocean", "cloud"],
                    "barons": 1,
                    "inhibitors": 2,
                },
                "redTeam": {
                    "totalGold": 48332,
                    "totalKills": 3,
                    "towers": 2,
                    "dragons": [],
                    "barons": 0,
                    "inhibitors": 0,
                },
            }],
        }
        final_details_payload = {
            "frames": [{
                "participants": [{
                    "participantId": identifier,
                    "level": 16,
                    "kills": 3 if identifier == 1 else 0,
                    "deaths": 0,
                    "assists": 5,
                    "totalGoldEarned": 10726,
                    "creepScore": 230,
                    "killParticipation": 0.67,
                    "championDamageShare": 0.14,
                    "wardsPlaced": 16,
                    "wardsDestroyed": 5,
                    "items": [1056, 3340],
                } for identifier in range(1, 11)],
            }],
        }
        details = collect_feeds.parse_lol_game_details(
            "game-1",
            1,
            metadata_payload,
            final_window_payload,
            final_details_payload,
            {"team-blue": "WE", "team-red": "LGD"},
        )
        self.assertIsNotNone(details)
        self.assertEqual(details["patch"], "16.14")
        self.assertEqual(details["duration"], 1695)
        self.assertEqual(details["teams"][0]["name"], "WE")
        self.assertEqual(details["teams"][0]["dragons"], 4)
        self.assertEqual(details["players"][0]["champion"], "Champion1")
        self.assertEqual(details["players"][0]["items"], [1056, 3340])


if __name__ == "__main__":
    unittest.main()
