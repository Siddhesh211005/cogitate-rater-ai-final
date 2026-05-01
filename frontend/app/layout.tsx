import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cogitate — Unified Rater Engine",
  description: "Insurance premium rating platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}