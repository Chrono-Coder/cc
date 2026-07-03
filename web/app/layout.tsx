import type { Metadata } from "next";
import { Doto, Geist, Geist_Mono, IBM_Plex_Mono, Outfit, Rubik } from "next/font/google";
import localFont from "next/font/local";
import Script from "next/script";
import AppNav from "@/components/AppNav";
import QuickSwitcher from "@/components/QuickSwitcher";
import IdleScreen from "@/components/IdleScreen";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { EventProvider } from "@/components/EventProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const rubik = Rubik({
  variable: "--font-rubik",
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const doto = Doto({
  variable: "--font-doto",
  subsets: ["latin"],
});

/** Full (unsubsetted) Plex Mono — the Google `latin` subset strips the block
 *  and box-drawing glyphs (█ ╔ ═ …) the ASCII banner art needs, which would
 *  otherwise render from a metrics-mismatched fallback and misalign. */
const plexMonoFull = localFont({
  src: "./fonts/IBMPlexMono-Full.woff2",
  variable: "--font-mono-full",
  weight: "400",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CC — Companion",
  description: "Odoo Dev CLI Companion App",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${outfit.variable} ${rubik.variable} ${plexMono.variable} ${plexMonoFull.variable} ${doto.variable} h-full antialiased dark`} suppressHydrationWarning>
      <body className="min-h-full bg-background text-foreground" suppressHydrationWarning>
        <Script id="theme-init" strategy="beforeInteractive">{`
          (function() {
            try {
              var t = localStorage.getItem('cc-theme') || 'dark';
              document.documentElement.setAttribute('data-theme', t);
              if (t === 'light') document.documentElement.classList.remove('dark');
              else document.documentElement.classList.add('dark');
            } catch(e) {}
          })();
        `}</Script>
        <ThemeProvider>
        <EventProvider>
        <TooltipProvider>
          <div className="flex min-h-screen">
            <AppNav />
            <main className="flex-1 px-10 py-10 overflow-x-hidden">
              {children}
            </main>
          </div>
          <QuickSwitcher />
          <Toaster />
          <IdleScreen />
        </TooltipProvider>
        </EventProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
