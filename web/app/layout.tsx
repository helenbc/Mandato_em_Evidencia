import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mandato em Evidência — Falas, votos e alinhamento",
  description:
    "Painel experimental de transparência parlamentar com falas, votos nominais e alinhamento partidário.",
  openGraph: {
    title: "Mandato em Evidência",
    description: "Falas, votos e alinhamento partidário com fontes rastreáveis.",
    locale: "pt_BR",
    type: "website",
    images: [{ url: "/og.png", width: 1731, height: 909, alt: "Mandato em Evidência" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Mandato em Evidência",
    description: "Falas, votos e alinhamento partidário com fontes rastreáveis.",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
