"use client";

import { useEffect, useMemo, useState } from "react";

type Sport = "all" | "nba" | "football" | "lol";
type Article = { id: string; sport: Exclude<Sport, "all">; title: string; summary: string; source: string; url: string; publishedAt: string; featured?: boolean; demo?: boolean };
type Match = { id: string; sport: Exclude<Sport, "all">; competition: string; home: string; away: string; homeScore?: number; awayScore?: number; status: "upcoming" | "live" | "finished"; time: string; demo?: boolean };
type Feed = { updatedAt: string; articles: Article[]; matches: Match[] };

const meta = {
  all: { label: "全部", mark: "总" }, nba: { label: "NBA", mark: "篮" },
  football: { label: "欧洲足球", mark: "足" }, lol: { label: "英雄联盟", mark: "竞" },
} satisfies Record<Sport, { label: string; mark: string }>;

const fallback: Feed = {
  updatedAt: "2026-07-25T12:00:00+08:00",
  matches: [
    { id: "m1", sport: "nba", competition: "NBA", home: "主队", away: "客队", status: "upcoming", time: "明日 08:00", demo: true },
    { id: "m2", sport: "football", competition: "欧洲足球", home: "主队", away: "客队", status: "upcoming", time: "明日 02:45", demo: true },
    { id: "m3", sport: "lol", competition: "职业联赛", home: "蓝色方", away: "红色方", status: "upcoming", time: "今日 17:00", demo: true },
  ],
  articles: [
    { id: "a1", sport: "nba", title: "NBA 频道已准备好接收最新资讯", summary: "启用 RSS 数据源后，这里会自动展示联盟、球队和球员动态，并保留原文链接。", source: "边线指南", url: "#sources", publishedAt: "2026-07-25T11:45:00+08:00", featured: true, demo: true },
    { id: "a2", sport: "football", title: "欧洲足球频道覆盖主要赛事与俱乐部动态", summary: "第一版聚合赛程、赛果、转会和伤病信息，并按来源与发布时间排列。", source: "边线指南", url: "#sources", publishedAt: "2026-07-25T11:20:00+08:00", featured: true, demo: true },
    { id: "a3", sport: "lol", title: "英雄联盟频道聚焦职业赛事新闻与战报", summary: "可关注 LPL、LCK 与国际赛事，收藏会保存在当前手机中。", source: "边线指南", url: "#sources", publishedAt: "2026-07-25T10:50:00+08:00", featured: true, demo: true },
    { id: "a4", sport: "nba", title: "资讯会自动去除完全重复的标题和链接", summary: "轻量去重不依赖付费 AI，适合个人低成本使用。", source: "功能说明", url: "#about", publishedAt: "2026-07-25T10:10:00+08:00", demo: true },
    { id: "a5", sport: "football", title: "在手机浏览器中添加到主屏幕即可安装", summary: "安装后会以独立窗口打开，并缓存最近一次成功加载的内容。", source: "功能说明", url: "#install", publishedAt: "2026-07-25T09:30:00+08:00", demo: true },
    { id: "a6", sport: "lol", title: "所有收藏与阅读偏好只保存在本机", summary: "无需注册账号，也不需要额外数据库。", source: "隐私说明", url: "#about", publishedAt: "2026-07-25T09:00:00+08:00", demo: true },
  ],
};

function relativeTime(value: string) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 60) return `${minutes || 1} 分钟前`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} 小时前` : `${Math.round(hours / 24)} 天前`;
}

function ScoreCard({ match }: { match: Match }) {
  const scored = match.homeScore !== undefined && match.awayScore !== undefined;
  return <article className={`score-card sport-${match.sport}`}>
    <div className="score-topline"><span>{match.competition}</span><span className={`status-${match.status}`}>{match.status === "live" ? "进行中" : match.status === "finished" ? "已结束" : match.time}</span></div>
    <div className="teams">
      <div><span className="team-dot">{match.home.slice(0, 1)}</span><strong>{match.home}</strong></div><b>{scored ? match.homeScore : "—"}</b>
      <div><span className="team-dot">{match.away.slice(0, 1)}</span><strong>{match.away}</strong></div><b>{scored ? match.awayScore : "—"}</b>
    </div>
    {match.demo && <span className="demo-badge">演示赛程</span>}
  </article>;
}

export default function SportsApp() {
  const [feed, setFeed] = useState<Feed>(fallback);
  const [active, setActive] = useState<Sport>("all");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [installEvent, setInstallEvent] = useState<Event | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem("sideline-favorites");
    if (saved) { try { setFavorites(JSON.parse(saved)); } catch { /* 忽略损坏的本地数据 */ } }
    fetch("/data/feed.json", { cache: "no-store" }).then((r) => r.ok ? r.json() : Promise.reject()).then(setFeed).catch(() => setFeed(fallback)).finally(() => setLoading(false));
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    const onInstall = (event: Event) => { event.preventDefault(); setInstallEvent(event); };
    window.addEventListener("beforeinstallprompt", onInstall);
    return () => window.removeEventListener("beforeinstallprompt", onInstall);
  }, []);

  const articles = useMemo(() => feed.articles.filter((a) => (active === "all" || a.sport === active) && (!favoritesOnly || favorites.includes(a.id))), [active, favorites, favoritesOnly, feed.articles]);
  const matches = feed.matches.filter((m) => active === "all" || m.sport === active);
  const featured = feed.articles.find((a) => a.featured && (active === "all" || a.sport === active)) ?? articles[0];

  const toggleFavorite = (id: string) => {
    const next = favorites.includes(id) ? favorites.filter((x) => x !== id) : [...favorites, id];
    setFavorites(next); window.localStorage.setItem("sideline-favorites", JSON.stringify(next));
  };

  const install = async () => {
    const event = installEvent as Event & { prompt?: () => Promise<void> };
    if (event?.prompt) { await event.prompt(); setInstallEvent(null); }
    else document.getElementById("install")?.scrollIntoView({ behavior: "smooth" });
  };

  return <main>
    <header className="topbar">
      <a className="brand" href="#top" aria-label="边线首页"><span className="brand-mark">边</span><span>边线</span></a>
      <div className="top-actions"><button className="icon-button" onClick={() => window.location.reload()} aria-label="刷新资讯">↻</button><button className="install-button" onClick={install}>安装到手机</button></div>
    </header>

    <section className="hero" id="top">
      <div className="eyebrow"><span /> 今日场边简报</div>
      <h1>少刷一点，<br />看懂今天。</h1>
      <p>NBA、欧洲足球与英雄联盟，重要资讯和赛果集中在一个安静的页面里。</p>
      <div className="update-chip"><i /> 最近更新 {relativeTime(feed.updatedAt)}{feed.articles.some((a) => a.demo) && <em>演示模式</em>}</div>
    </section>

    <nav className="sport-tabs" aria-label="项目筛选">
      {(Object.keys(meta) as Sport[]).map((sport) => <button key={sport} className={active === sport ? "active" : ""} onClick={() => setActive(sport)}><span>{meta[sport].mark}</span>{meta[sport].label}</button>)}
    </nav>

    <section className="section scores-section" aria-labelledby="matches-title">
      <div className="section-heading"><div><span className="section-kicker">MATCH CENTER</span><h2 id="matches-title">今日比赛</h2></div><span className="count">{matches.length} 场</span></div>
      <div className="score-rail">{matches.map((m) => <ScoreCard key={m.id} match={m} />)}</div>
    </section>

    {featured && <section className={`lead-story sport-${featured.sport}`}>
      <div className="lead-label">编辑精选 · {meta[featured.sport].label}</div><h2>{featured.title}</h2><p>{featured.summary}</p>
      <a href={featured.url} target={featured.url.startsWith("http") ? "_blank" : undefined} rel="noreferrer">查看详情 <span>→</span></a>
    </section>}

    <section className="section news-section" aria-labelledby="news-title">
      <div className="section-heading"><div><span className="section-kicker">LATEST STORIES</span><h2 id="news-title">最新资讯</h2></div><button className={`favorite-filter ${favoritesOnly ? "active" : ""}`} onClick={() => setFavoritesOnly(!favoritesOnly)}>☆ 收藏 {favorites.length || ""}</button></div>
      <div className="news-list" aria-live="polite">
        {loading && <div className="empty-state">正在读取本地资讯…</div>}
        {!loading && !articles.length && <div className="empty-state">这里还没有收藏，点一下资讯右侧的星标即可保存。</div>}
        {!loading && articles.map((article) => <article className="news-item" key={article.id}>
          <div className={`sport-stamp sport-${article.sport}`}>{meta[article.sport].mark}</div>
          <div className="news-copy"><div className="news-meta"><span>{meta[article.sport].label}</span><span>{article.source}</span><time>{relativeTime(article.publishedAt)}</time>{article.demo && <b>样例</b>}</div>
            <a href={article.url} target={article.url.startsWith("http") ? "_blank" : undefined} rel="noreferrer"><h3>{article.title}</h3></a><p>{article.summary}</p>
          </div>
          <button className={`star ${favorites.includes(article.id) ? "saved" : ""}`} onClick={() => toggleFavorite(article.id)} aria-label={favorites.includes(article.id) ? "取消收藏" : "收藏资讯"}>{favorites.includes(article.id) ? "★" : "☆"}</button>
        </article>)}
      </div>
    </section>

    <section className="how-it-works" id="sources"><span className="section-kicker">ZERO-COST SETUP</span><h2>轻量，也能一直更新。</h2><div className="steps">
      <div><b>01</b><h3>免费来源</h3><p>RSS 与有限免费 API，只读取标题、摘要和原文链接。</p></div><div><b>02</b><h3>定时整理</h3><p>采集脚本自动去重并生成一个轻量 JSON 文件。</p></div><div><b>03</b><h3>手机查看</h3><p>无需账号，收藏和设置都只保存在当前设备。</p></div>
    </div></section>

    <section className="install-guide" id="install"><div className="phone-glyph">+</div><div><span className="section-kicker">ADD TO HOME SCREEN</span><h2>把边线放到手机桌面</h2><p>Android 使用浏览器菜单中的“安装应用”；iPhone 使用 Safari 的“分享 → 添加到主屏幕”。</p></div></section>
    <footer id="about"><a className="brand" href="#top"><span className="brand-mark">边</span><span>边线</span></a><p>为个人阅读而做 · 原文版权归各来源所有</p></footer>
    <nav className="mobile-nav" aria-label="移动端导航"><a href="#top"><span>⌂</span>今日</a><a href="#news-title"><span>≡</span>资讯</a><a href="#matches-title"><span>▣</span>比赛</a><button onClick={() => setFavoritesOnly(!favoritesOnly)}><span>☆</span>收藏</button></nav>
  </main>;
}
