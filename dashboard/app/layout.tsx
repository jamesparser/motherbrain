import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Motherbrain",
  description: "Shared cognitive memory for Omega agents — short-term, long-term, and dreams.",
  icons: { icon: "/motherbrain.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
