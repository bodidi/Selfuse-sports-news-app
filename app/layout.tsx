import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const protocol = host.includes("localhost") || host.startsWith("127.0.0.1") ? "http" : "https";
  const origin = `${protocol}://${host}`;
  return {
    metadataBase: new URL(origin),
    title: { default: "边线 · 体育资讯", template: "%s · 边线" },
    description: "NBA、欧洲足球与英雄联盟赛事资讯，一处轻松掌握。",
    manifest: "/manifest.webmanifest",
    applicationName: "边线",
    appleWebApp: { capable: true, title: "边线", statusBarStyle: "black-translucent" },
    formatDetection: { telephone: false },
    icons: { icon: "/icon-192.png", apple: "/icon-192.png" },
    openGraph: { title: "边线 · 体育资讯", description: "少刷一点，看懂今天。", type: "website", url: origin, images: [{ url: `${origin}/og.png`, width: 1733, height: 907, alt: "边线体育资讯" }] },
    twitter: { card: "summary_large_image", title: "边线 · 体育资讯", description: "少刷一点，看懂今天。", images: [`${origin}/og.png`] },
  };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1, maximumScale: 1, viewportFit: "cover", themeColor: "#f3f0e8" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-CN"><body>{children}</body></html>; }
