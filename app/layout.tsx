import type { Metadata, Viewport } from "next";
import "./globals.css";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001";

export function generateMetadata(): Metadata {
  return {
    metadataBase: new URL(siteUrl),
    title: { default: "没有广告", template: "%s · 没有广告" },
    description: "NBA、欧洲足球与英雄联盟赛事资讯，一处轻松掌握。",
    manifest: `${basePath}/manifest.webmanifest`,
    applicationName: "没有广告",
    appleWebApp: { capable: true, title: "没有广告", statusBarStyle: "black-translucent" },
    formatDetection: { telephone: false },
    icons: { icon: `${basePath}/icon-192.png`, apple: `${basePath}/icon-192.png` },
    openGraph: { title: "没有广告", description: "少刷一点，看懂今天。", type: "website", url: siteUrl, images: [{ url: `${siteUrl}/og.png`, width: 1733, height: 907, alt: "没有广告体育资讯" }] },
    twitter: { card: "summary_large_image", title: "没有广告", description: "少刷一点，看懂今天。", images: [`${siteUrl}/og.png`] },
  };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1, maximumScale: 1, viewportFit: "cover", themeColor: "#f3f0e8" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="zh-CN"><body>{children}</body></html>; }
