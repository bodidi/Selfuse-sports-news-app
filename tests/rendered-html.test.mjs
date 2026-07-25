import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("服务端渲染边线首页", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /边线/);
  assert.match(html, /少刷一点/);
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
  assert.deepEqual(new Set(feed.articles.map((item) => item.sport)), new Set(["nba", "football", "lol"]));
  await access(new URL("../public/icon-192.png", import.meta.url));
  await access(new URL("../public/icon-512.png", import.meta.url));
  await access(new URL("../public/og.png", import.meta.url));
});
