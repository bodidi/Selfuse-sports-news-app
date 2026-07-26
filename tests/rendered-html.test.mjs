import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("服务端渲染没有广告首页", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /没有广告/);
  assert.match(html, /我们真的/);
  assert.match(html, /没有广告/);
  assert.match(html, /NBA/);
  assert.match(html, /欧洲足球/);
  assert.match(html, /英雄联盟/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|react-loading-skeleton/);
});
test("包含可安装和离线运行所需资源", async () => {
  const [manifestText, workerText, feedText] = await Promise.all([
    readFile(new URL("../public/manifest.webmanifest", import.meta.url), "utf8"),
    readFile(new URL("../public/sw.js", import.meta.url), "utf8"),
    readFile(new URL("../public/data/feed.json", import.meta.url), "utf8"),
  ]);
  const manifest = JSON.parse(manifestText);
  const feed = JSON.parse(feedText);
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.lang, "zh-CN");
  assert.equal(manifest.icons.length, 2);
  assert.match(workerText, /caches\.open/);
  assert.ok(feed.articles.length >= 3);
  assert.deepEqual(new Set(feed.articles.map((item) => item.sport)), new Set(["nba", "football"]));
  const lolMatches = feed.matches.filter((item) => item.sport === "lol");
  const nbaMatches = feed.matches.filter((item) => item.sport === "nba");
  const footballMatches = feed.matches.filter((item) => item.sport === "football");
  assert.ok(nbaMatches.length >= 1);
  assert.ok(nbaMatches.every((item) => item.source === "ESPN"));
  assert.ok(nbaMatches.every((item) => !item.demo && item.startTime));
  assert.ok(nbaMatches.every((item) => item.details));
  assert.ok(nbaMatches.every((item) => item.details.teamStats.length === 2));
  assert.ok(nbaMatches.every((item) => item.details.playerStats.length === 2));
  assert.ok(nbaMatches.every((item) => item.details.leaders.length === 2));
  assert.ok(footballMatches.length >= 1);
  assert.ok(footballMatches.every((item) => item.source === "ESPN"));
  assert.ok(footballMatches.every((item) => !item.demo && item.startTime));
  assert.ok(footballMatches.every((item) => ["英超", "西甲", "意甲", "德甲", "法甲", "欧冠"].includes(item.competition)));
  assert.ok(lolMatches.length >= 1);
  assert.ok(lolMatches.every((item) => item.source === "LoL Esports"));
  assert.ok(lolMatches.every((item) => !item.demo && item.startTime));
  const detailedLplMatches = lolMatches.filter((item) => item.competition.startsWith("LPL") && item.status === "finished");
  assert.ok(detailedLplMatches.length >= 1);
  assert.ok(detailedLplMatches.every((item) => item.details?.kind === "lol"));
  assert.ok(detailedLplMatches.every((item) => item.details.games.length === item.homeScore + item.awayScore));
  assert.ok(detailedLplMatches.every((item) => item.details.games.every((game) => game.teams.length === 2 && game.players.length === 10)));
  assert.ok(lolMatches.filter((item) => !item.competition.startsWith("LPL")).every((item) => !item.details));
  await access(new URL("../public/icon-192.png", import.meta.url));
  await access(new URL("../public/icon-512.png", import.meta.url));
  await access(new URL("../public/og.png", import.meta.url));
});

test("社区热帖字段、去重和热度有效", async () => {
  const feed = JSON.parse(await readFile(new URL("../public/data/feed.json", import.meta.url), "utf8"));
  assert.ok(Array.isArray(feed.communityPosts));
  assert.ok(feed.communityPosts.length >= 1);
  assert.deepEqual(new Set(feed.communityPosts.map((post) => post.platform)), new Set(["hupu"]));
  assert.deepEqual(new Set(feed.communityPosts.map((post) => post.sport)), new Set(["nba", "football", "lol"]));
  const required = ["id", "sport", "platform", "region", "board", "title", "excerpt", "url", "author", "publishedAt", "collectedAt", "score", "replyCount", "hotScore", "topComments"];
  for (const post of feed.communityPosts) {
    assert.ok(required.every((field) => Object.hasOwn(post, field)), `社区帖子字段不完整：${post.id}`);
    assert.ok(["nba", "football", "lol"].includes(post.sport));
    assert.match(post.url, /^https:\/\//);
    assert.ok(post.hotScore >= 0 && post.hotScore <= 1);
    assert.ok(Array.isArray(post.topComments) && post.topComments.length <= 3);
  }
  assert.equal(new Set(feed.communityPosts.map((post) => post.id)).size, feed.communityPosts.length);
  assert.deepEqual(feed.communityPosts.map((post) => post.hotScore), [...feed.communityPosts].map((post) => post.hotScore).sort((a, b) => b - a));
});
