import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Rasputin · Auditoria fiscal",
  description: "Conferência fiscal com evidência, contexto e rastreabilidade.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
