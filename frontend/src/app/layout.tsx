import type { Metadata } from "next";
import { QueryProvider } from "@/providers/query";
import "./globals.css";

export const metadata: Metadata = {
  title: "agent7 — AI Agent Governance",
  description: "Governance dashboard for agent-mesh",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
