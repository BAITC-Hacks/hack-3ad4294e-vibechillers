import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Function Lineage Auditor",
  description: "Before/after regulation function lineage audit with verifiable clause citations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
