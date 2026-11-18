import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ops Sync Dashboard",
  description: "Stripe + help desk in one place, synced reliably.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
