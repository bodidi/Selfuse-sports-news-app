import type { Metadata } from "next";
import SportsApp from "./SportsApp";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "边线 · 体育资讯",
  description: "NBA、欧洲足球与英雄联盟赛事资讯，一处轻松掌握。",
};

export default function Home() {
  return <SportsApp />;
}
