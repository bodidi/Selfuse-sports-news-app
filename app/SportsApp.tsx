"use client";

import { useEffect, useMemo, useState } from "react";

type Sport = "all" | "nba" | "football" | "lol";
type Article = { id: string; sport: Exclude<Sport, "all">; title: string; summary: string; source: string; url: string; publishedAt: string; featured?: boolean; demo?: boolean };
type TeamStats = { team: string; values: Record<string, string> };
type PlayerLine = { name: string; jersey: string; position: string; starter: boolean; stats: Record<string, string> };
type NbaMatchDetails = { kind?: "nba"; venue: string; broadcasts: string[]; teamStats: TeamStats[]; playerStats: { team: string; athletes: PlayerLine[] }[]; leaders: { team: string; categories: { label: string; athlete: string; value: string }[] }[] };
type LolTeamLine = { id: string; name: string; side: "blue" | "red"; gold: number; kills: number; towers: number; dragons: number; dragonTypes: string[]; barons: number; inhibitors: number };
type LolPlayerLine = { participantId: number; team: string; side: "blue" | "red"; name: string; role: string; champion: string; level: number; kills: number; deaths: number; assists: number; gold: number; cs: number; killParticipation: number; damageShare: number; wardsPlaced: number; wardsDestroyed: number; items: number[] };
type LolGame = { gameId: string; gameNumber: number; state: "finished"; patch: string; duration: number; teams: LolTeamLine[]; players: LolPlayerLine[] };
type LolMatchDetails = { kind: "lol"; format: string; games: LolGame[] };
type MatchDetails = NbaMatchDetails | LolMatchDetails;
type Match = { id: string; sport: Exclude<Sport, "all">; competition: string; home: string; away: string; homeScore?: number; awayScore?: number; status: "upcoming" | "live" | "finished"; time: string; startTime?: string; source?: string; details?: MatchDetails; demo?: boolean };
type CommunityPost = { id: string; sport: Exclude<Sport, "all">; platform: "hupu"; region: string; board: string; title: string; excerpt: string; url: string; author: string; publishedAt: string; collectedAt: string; score: number; replyCount: number; viewCount?: number; hotScore: number; topComments: { text: string; score: number }[]; demo?: boolean };
type Feed = { updatedAt: string; articles: Article[]; matches: Match[]; communityPosts: CommunityPost[] };

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const meta = {
  all: { label: "全部", mark: "总" }, nba: { label: "NBA", mark: "篮" },
  football: { label: "欧洲足球", mark: "足" }, lol: { label: "英雄联盟", mark: "竞" },
} satisfies Record<Sport, { label: string; mark: string }>;

const fallback: Feed = {
  updatedAt: "2026-07-25T12:00:00+08:00",
  communityPosts: [
    { id: "c-nba", sport: "nba", platform: "hupu", region: "china", board: "虎扑篮球场", title: "NBA 社区热帖正在读取", excerpt: "这里会展示虎扑篮球场的热门讨论与代表性高亮评论。", url: "https://bbs.hupu.com/nba", author: "没有广告", publishedAt: "2026-07-25T11:00:00+08:00", collectedAt: "2026-07-25T12:00:00+08:00", score: 0, replyCount: 0, hotScore: 0, topComments: [], demo: true },
    { id: "c-football", sport: "football", platform: "hupu", region: "china", board: "虎扑足球话题区", title: "欧洲足球社区热帖正在读取", excerpt: "这里会展示虎扑足球话题区的热门讨论与代表性高亮评论。", url: "https://bbs.hupu.com/topic", author: "没有广告", publishedAt: "2026-07-25T11:00:00+08:00", collectedAt: "2026-07-25T12:00:00+08:00", score: 0, replyCount: 0, hotScore: 0, topComments: [], demo: true },
    { id: "c1", sport: "lol", platform: "hupu", region: "china", board: "虎扑英雄联盟", title: "社区热帖模块正在读取最新讨论", excerpt: "这里会展示来自公开社区的热门帖子、互动数据和代表性高赞评论。", url: "https://bbs.hupu.com/lol", author: "没有广告", publishedAt: "2026-07-25T11:00:00+08:00", collectedAt: "2026-07-25T12:00:00+08:00", score: 0, replyCount: 0, hotScore: 0, topComments: [], demo: true },
  ],
  matches: [
    { id: "m1", sport: "nba", competition: "NBA", home: "主队", away: "客队", status: "upcoming", time: "明日 08:00", demo: true },
    { id: "m2", sport: "football", competition: "欧洲足球", home: "主队", away: "客队", status: "upcoming", time: "明日 02:45", demo: true },
    { id: "m3", sport: "lol", competition: "职业联赛", home: "蓝色方", away: "红色方", status: "upcoming", time: "今日 17:00", demo: true },
  ],
  articles: [
    { id: "a1", sport: "nba", title: "NBA 频道已准备好接收最新资讯", summary: "启用 RSS 数据源后，这里会自动展示联盟、球队和球员动态，并保留原文链接。", source: "没有广告", url: "#sources", publishedAt: "2026-07-25T11:45:00+08:00", featured: true, demo: true },
    { id: "a2", sport: "football", title: "欧洲足球频道覆盖主要赛事与俱乐部动态", summary: "第一版聚合赛程、赛果、转会和伤病信息，并按来源与发布时间排列。", source: "没有广告", url: "#sources", publishedAt: "2026-07-25T11:20:00+08:00", featured: true, demo: true },
    { id: "a4", sport: "nba", title: "资讯会自动去除完全重复的标题和链接", summary: "轻量去重不依赖付费 AI，适合个人低成本使用。", source: "功能说明", url: "#about", publishedAt: "2026-07-25T10:10:00+08:00", demo: true },
    { id: "a5", sport: "football", title: "在手机浏览器中添加到主屏幕即可安装", summary: "安装后会以独立窗口打开，并缓存最近一次成功加载的内容。", source: "功能说明", url: "#install", publishedAt: "2026-07-25T09:30:00+08:00", demo: true },
  ],
};

function relativeTime(value: string) {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 60) return `${minutes || 1} 分钟前`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} 小时前` : `${Math.round(hours / 24)} 天前`;
}
function ScoreCard({ match, onSelect }: { match: Match; onSelect?: () => void }) {
  const scored = match.homeScore !== undefined && match.awayScore !== undefined;
  return <article className={`score-card sport-${match.sport} ${onSelect ? "clickable" : ""}`} onClick={onSelect} onKeyDown={(event) => { if (onSelect && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onSelect(); } }} role={onSelect ? "button" : undefined} tabIndex={onSelect ? 0 : undefined} aria-label={onSelect ? `查看 ${match.away} 对 ${match.home} 比赛详情` : undefined}>
    <div className="score-topline"><span>{match.competition}</span><span className={`status-${match.status}`}>{match.status === "live" ? `进行中 · ${match.time}` : match.status === "finished" ? `已结束 · ${match.time}` : match.time}</span></div>
    <div className="teams">
      <div><span className="team-dot">{match.home.slice(0, 1)}</span><strong>{match.home}</strong></div><b>{scored ? match.homeScore : "—"}</b>
      <div><span className="team-dot">{match.away.slice(0, 1)}</span><strong>{match.away}</strong></div><b>{scored ? match.awayScore : "—"}</b>
    </div>
    {onSelect && <span className="detail-hint">{match.sport === "lol" ? "查看单局详情" : "查看技术统计"} →</span>}
    {match.demo && <span className="demo-badge">演示赛程</span>}
  </article>;
}

const teamMetricLabels: Record<string, string> = { FG: "投篮", "FG%": "命中率", "3PT": "三分", "3P%": "三分率", FT: "罚球", "FT%": "罚球率", REB: "篮板", AST: "助攻", STL: "抢断", BLK: "盖帽", TO: "失误" };
const teamMetricOrder = ["FG", "FG%", "3PT", "3P%", "FT", "FT%", "REB", "AST", "STL", "BLK", "TO"];
const playerMetricOrder = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "FG", "3PT", "+/-"];

function NbaMatchDetail({ match, onClose }: { match: Match; onClose: () => void }) {
  if (!match.details || match.details.kind === "lol") return null;
  const details = match.details;
  const teamOrder = [match.away, match.home];
  const teamStats = teamOrder.map((team) => details.teamStats.find((entry) => entry.team === team));
  return <div className="match-detail-backdrop" role="presentation" onClick={onClose}>
    <section className="match-detail-panel" role="dialog" aria-modal="true" aria-labelledby="match-detail-title" onClick={(event) => event.stopPropagation()}>
      <button className="detail-close" onClick={onClose} aria-label="关闭比赛详情">×</button>
      <div className="detail-kicker">{match.competition} · {match.time}</div>
      <h2 id="match-detail-title">{match.away} {match.awayScore ?? "—"} <span>:</span> {match.homeScore ?? "—"} {match.home}</h2>
      {(details.venue || details.broadcasts.length > 0) && <p className="detail-subline">{[details.venue, details.broadcasts.join(" / ")].filter(Boolean).join(" · ")}</p>}

      {!!details.leaders.length && <div className="detail-section"><h3>本场领先者</h3><div className="leader-grid">
        {details.leaders.map((team) => <div key={team.team}><strong>{team.team}</strong>{team.categories.map((category) => <p key={`${team.team}-${category.label}`}><span>{category.label}</span>{category.athlete}<b>{category.value}</b></p>)}</div>)}
      </div></div>}

      {teamStats.every(Boolean) && <div className="detail-section"><h3>球队数据对比</h3><div className="team-comparison">
        <div className="comparison-head"><strong>{match.away}</strong><span>数据</span><strong>{match.home}</strong></div>
        {teamMetricOrder.map((metric) => <div className="comparison-row" key={metric}><b>{teamStats[0]?.values[metric] ?? "—"}{metric.endsWith("%") && teamStats[0]?.values[metric] ? "%" : ""}</b><span>{teamMetricLabels[metric]}</span><b>{teamStats[1]?.values[metric] ?? "—"}{metric.endsWith("%") && teamStats[1]?.values[metric] ? "%" : ""}</b></div>)}
      </div></div>}

      {!!details.playerStats.length && <div className="detail-section"><h3>球员数据</h3>{teamOrder.map((team) => {
        const roster = details.playerStats.find((entry) => entry.team === team);
        if (!roster) return null;
        return <div className="player-table-wrap" key={team}><h4>{team}</h4><table className="player-table"><thead><tr><th>球员</th>{playerMetricOrder.map((metric) => <th key={metric}>{metric}</th>)}</tr></thead><tbody>
          {roster.athletes.map((player) => <tr key={`${team}-${player.name}`}><td><strong>{player.name}</strong><small>{player.starter ? "首发" : "替补"} · {player.position}{player.jersey ? ` · #${player.jersey}` : ""}</small></td>{playerMetricOrder.map((metric) => <td key={metric}>{player.stats[metric] ?? "—"}</td>)}</tr>)}
        </tbody></table></div>;
      })}</div>}
      <p className="detail-source">数据来源：{match.source ?? "ESPN"}</p>
    </section>
  </div>;
}

const lolRoleLabels: Record<string, string> = { top: "上路", jungle: "打野", mid: "中路", bottom: "下路", support: "辅助" };
const lolMetricLabels: { key: keyof Pick<LolTeamLine, "kills" | "gold" | "towers" | "dragons" | "barons" | "inhibitors">; label: string }[] = [
  { key: "kills", label: "击杀" },
  { key: "gold", label: "经济" },
  { key: "towers", label: "防御塔" },
  { key: "dragons", label: "小龙" },
  { key: "barons", label: "男爵" },
  { key: "inhibitors", label: "兵营" },
];

function compactNumber(value: number) {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(value);
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function durationLabel(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function LolMatchDetail({ match, details, onClose }: { match: Match; details: LolMatchDetails; onClose: () => void }) {
  const [selectedGameNumber, setSelectedGameNumber] = useState(details.games[0]?.gameNumber ?? 1);
  const game = details.games.find((entry) => entry.gameNumber === selectedGameNumber) ?? details.games[0];
  if (!game) return null;
  const blueTeam = game.teams.find((team) => team.side === "blue");
  const redTeam = game.teams.find((team) => team.side === "red");
  if (!blueTeam || !redTeam) return null;
  return <div className="match-detail-backdrop" role="presentation" onClick={onClose}>
    <section className="match-detail-panel lol-detail-panel" role="dialog" aria-modal="true" aria-labelledby="match-detail-title" onClick={(event) => event.stopPropagation()}>
      <button className="detail-close" onClick={onClose} aria-label="关闭比赛详情">×</button>
      <div className="detail-kicker">{match.competition} · {details.format} · {match.time}</div>
      <h2 id="match-detail-title">{match.home} {match.homeScore ?? "—"} <span>:</span> {match.awayScore ?? "—"} {match.away}</h2>
      <p className="detail-subline">官方终局数据 · 版本 {game.patch} · 用时 {durationLabel(game.duration)}</p>

      <div className="lol-game-tabs" role="tablist" aria-label="单局切换">
        {details.games.map((entry) => <button key={entry.gameId} className={entry.gameNumber === game.gameNumber ? "active" : ""} onClick={() => setSelectedGameNumber(entry.gameNumber)} role="tab" aria-selected={entry.gameNumber === game.gameNumber}>第 {entry.gameNumber} 局</button>)}
      </div>

      <div className="detail-section"><h3>本局数据对比</h3><div className="team-comparison lol-comparison">
        <div className="comparison-head"><strong><i className="side-dot blue" />{blueTeam.name}</strong><span>数据</span><strong>{redTeam.name}<i className="side-dot red" /></strong></div>
        {lolMetricLabels.map(({ key, label }) => <div className="comparison-row" key={key}><b>{key === "gold" ? compactNumber(blueTeam[key]) : blueTeam[key]}</b><span>{label}</span><b>{key === "gold" ? compactNumber(redTeam[key]) : redTeam[key]}</b></div>)}
      </div></div>

      <div className="detail-section"><h3>选手数据</h3>{[blueTeam, redTeam].map((team) => {
        const roster = game.players.filter((player) => player.side === team.side);
        return <div className={`player-table-wrap lol-roster side-${team.side}`} key={team.side}><h4>{team.name} · {team.side === "blue" ? "蓝色方" : "红色方"}</h4><table className="player-table lol-player-table"><thead><tr><th>选手</th><th>英雄</th><th>K / D / A</th><th>补刀</th><th>经济</th><th>参团</th><th>伤害</th><th>视野</th></tr></thead><tbody>
          {roster.map((player) => <tr key={player.participantId}><td><strong>{player.name}</strong><small>{lolRoleLabels[player.role] ?? player.role} · Lv.{player.level}</small></td><td><strong>{player.champion}</strong></td><td className="lol-kda">{player.kills} / {player.deaths} / {player.assists}</td><td>{player.cs}</td><td>{compactNumber(player.gold)}</td><td>{percent(player.killParticipation)}</td><td>{percent(player.damageShare)}</td><td>{player.wardsPlaced} / {player.wardsDestroyed}</td></tr>)}
        </tbody></table></div>;
      })}</div>
      <p className="detail-source">数据来源：{match.source ?? "LoL Esports"} · 当前数据源暂不含 Ban 位</p>
    </section>
  </div>;
}

function MatchDetail({ match, onClose }: { match: Match; onClose: () => void }) {
  if (!match.details) return null;
  return match.details.kind === "lol"
    ? <LolMatchDetail match={match} details={match.details} onClose={onClose} />
    : <NbaMatchDetail match={match} onClose={onClose} />;
}

export default function SportsApp() {
  const [feed, setFeed] = useState<Feed>(fallback);
  const [active, setActive] = useState<Sport>("all");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [installEvent, setInstallEvent] = useState<Event | null>(null);
  const [communitySort, setCommunitySort] = useState<"hot" | "new">("hot");
  const [expandedPosts, setExpandedPosts] = useState<string[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  useEffect(() => {
    const saved = window.localStorage.getItem("sideline-favorites");
    if (saved) queueMicrotask(() => { try { setFavorites(JSON.parse(saved)); } catch { /* 忽略损坏的本地数据 */ } });
    fetch(`${basePath}/data/feed.json`, { cache: "no-store" }).then((r) => r.ok ? r.json() : Promise.reject()).then((data: Feed) => setFeed({ ...data, communityPosts: data.communityPosts ?? [] })).catch(() => setFeed(fallback)).finally(() => setLoading(false));
    if ("serviceWorker" in navigator) navigator.serviceWorker.register(`${basePath}/sw.js`, { scope: `${basePath}/` }).catch(() => undefined);
    const onInstall = (event: Event) => { event.preventDefault(); setInstallEvent(event); };
    window.addEventListener("beforeinstallprompt", onInstall);
    return () => window.removeEventListener("beforeinstallprompt", onInstall);
  }, []);

  const articles = useMemo(() => feed.articles.filter((a) => (active === "all" || a.sport === active) && (!favoritesOnly || favorites.includes(a.id))), [active, favorites, favoritesOnly, feed.articles]);
  const matches = feed.matches.filter((m) => active === "all" || m.sport === active);
  const featured = feed.articles.find((a) => a.featured && (active === "all" || a.sport === active)) ?? articles[0];
  const communityPosts = useMemo(() => {
    const filtered = feed.communityPosts.filter((post) => (active === "all" || post.sport === active) && (!favoritesOnly || favorites.includes(post.id)));
    return [...filtered].sort((a, b) => communitySort === "hot" ? b.hotScore - a.hotScore : new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime());
  }, [active, communitySort, favorites, favoritesOnly, feed.communityPosts]);
  const selectedMatch = feed.matches.find((match) => match.id === selectedMatchId);

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
      <a className="brand" href="#top" aria-label="没有广告首页"><span className="brand-mark">无</span><span>没有广告</span></a>
      <div className="top-actions"><button className="icon-button" onClick={() => window.location.reload()} aria-label="刷新资讯">↻</button><button className="install-button" onClick={install}>安装到手机</button></div>
    </header>

    <section className="hero" id="top">
      <div className="eyebrow"><span /> 今日场边简报</div>
      <h1>我们真的<br />没有广告！</h1>
      <p>NBA、欧洲足球与英雄联盟，重要资讯和赛果集中在一个安静的页面里。</p>
      <div className="update-chip"><i /> 最近更新 {relativeTime(feed.updatedAt)}{feed.articles.some((a) => a.demo) && <em>演示模式</em>}</div>
    </section>

    <nav className="sport-tabs" aria-label="项目筛选">
      {(Object.keys(meta) as Sport[]).map((sport) => <button key={sport} className={active === sport ? "active" : ""} onClick={() => setActive(sport)}><span>{meta[sport].mark}</span>{meta[sport].label}</button>)}
    </nav>

    <section className="section scores-section" aria-labelledby="matches-title">
      <div className="section-heading"><div><span className="section-kicker">MATCH CENTER</span><h2 id="matches-title">今日比赛</h2></div><span className="count">{matches.length} 场</span></div>
      <div className="score-rail">{matches.length ? matches.map((m) => <ScoreCard key={m.id} match={m} onSelect={m.details ? () => setSelectedMatchId(m.id) : undefined} />) : <div className="empty-score">当前窗口暂无近期比赛</div>}</div>
    </section>

    {selectedMatch?.details && <MatchDetail match={selectedMatch} onClose={() => setSelectedMatchId(null)} />}

    {featured && active === "all" && <section className={`lead-story sport-${featured.sport}`}>
      <div className="lead-label">编辑精选 · {meta[featured.sport].label}</div><h2>{featured.title}</h2><p>{featured.summary}</p>
      <a href={featured.url} target={featured.url.startsWith("http") ? "_blank" : undefined} rel="noreferrer">查看详情 <span>→</span></a>
    </section>}

    {active === "all" && <section className="section news-section" aria-labelledby="news-title">
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
    </section>}

    {active !== "all" && <section className="section community-section" aria-labelledby="news-title">
      <div className="section-heading"><div><span className="section-kicker">COMMUNITY PULSE · HUPU</span><h2 id="news-title">{meta[active].label}社区热帖</h2></div><button className={`favorite-filter ${favoritesOnly ? "active" : ""}`} onClick={() => setFavoritesOnly(!favoritesOnly)}>☆ 收藏 {favorites.length || ""}</button></div>
      <div className="community-toolbar" aria-label="社区热帖筛选">
        <div className="filter-group"><button className={communitySort === "hot" ? "active" : ""} onClick={() => setCommunitySort("hot")}>热度榜</button><button className={communitySort === "new" ? "active" : ""} onClick={() => setCommunitySort("new")}>新帖榜</button></div>
      </div>
      <p className="community-note">内容来自虎扑公开社区；社区观点不代表事实新闻，仅展示标题、短摘录、互动数据与原文链接。</p>
      <div className="community-list" aria-live="polite">
        {loading && <div className="empty-state">正在读取社区热帖…</div>}
        {!loading && !communityPosts.length && <div className="empty-state">当前筛选下暂无社区热帖，采集失败时会保留上一次成功数据。</div>}
        {!loading && communityPosts.map((post, index) => {
          const expanded = expandedPosts.includes(post.id);
          return <article className={`community-item platform-${post.platform}`} key={post.id}>
            <div className="community-rank">{String(index + 1).padStart(2, "0")}</div>
            <div className="community-copy">
              <div className="news-meta"><span>{meta[post.sport].label}</span><span>虎扑 · {post.board}</span><time>{relativeTime(post.publishedAt)}</time>{post.demo && <b>样例</b>}</div>
              <a href={post.url} target="_blank" rel="noreferrer"><h3>{post.title}</h3></a>
              {post.excerpt && <p>{post.excerpt}</p>}
              <div className="community-stats"><span>热度 {Math.round(post.hotScore * 100)}</span><span>赞/推荐 {post.score}</span><span>回复 {post.replyCount}</span>{post.viewCount !== undefined && <span>浏览 {post.viewCount}</span>}</div>
              {!!post.topComments.length && <button className="comments-toggle" onClick={() => setExpandedPosts(expanded ? expandedPosts.filter((id) => id !== post.id) : [...expandedPosts, post.id])}>{expanded ? "收起高赞评论" : `查看 ${post.topComments.length} 条高赞评论`}</button>}
              {expanded && <div className="top-comments">{post.topComments.map((comment, commentIndex) => <blockquote key={`${post.id}-${commentIndex}`}><p>{comment.text}</p><span>{comment.score} 赞</span></blockquote>)}</div>}
            </div>
            <button className={`star ${favorites.includes(post.id) ? "saved" : ""}`} onClick={() => toggleFavorite(post.id)} aria-label={favorites.includes(post.id) ? "取消收藏" : "收藏热帖"}>{favorites.includes(post.id) ? "★" : "☆"}</button>
          </article>;
        })}
      </div>
    </section>}

    <section className="how-it-works" id="sources"><span className="section-kicker">ZERO-COST SETUP</span><h2>轻量，也能一直更新。</h2><div className="steps">
      <div><b>01</b><h3>免费来源</h3><p>RSS、官方赛程与公开社区入口，只保留必要摘要和原文链接。</p></div><div><b>02</b><h3>定时整理</h3><p>采集脚本按平台归一化热度，并生成一个轻量 JSON 文件。</p></div><div><b>03</b><h3>手机查看</h3><p>无需账号，收藏和设置都只保存在当前设备。</p></div>
    </div></section>

    <section className="install-guide" id="install"><div className="phone-glyph">+</div><div><span className="section-kicker">ADD TO HOME SCREEN</span><h2>把“没有广告”放到手机桌面</h2><p>Android 使用浏览器菜单中的“安装应用”；iPhone 使用 Safari 的“分享 → 添加到主屏幕”。</p></div></section>
    <footer id="about"><a className="brand" href="#top"><span className="brand-mark">无</span><span>没有广告</span></a><p>无广告 · 为个人阅读而做 · 原文版权归各来源所有</p></footer>
    <nav className="mobile-nav" aria-label="移动端导航"><a href="#top"><span>⌂</span>今日</a><a href="#news-title"><span>≡</span>资讯</a><a href="#matches-title"><span>▣</span>比赛</a><button onClick={() => setFavoritesOnly(!favoritesOnly)}><span>☆</span>收藏</button></nav>
  </main>;
}
