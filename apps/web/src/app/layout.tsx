import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Function Lineage Auditor",
  description: "Аудит реорганизации: подразделения, функции и потенциальные риски с точными источниками",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="antialiased">{children}</body>
    </html>
  );
}
