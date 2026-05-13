import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Yomi",
  description: "Self-hosted Japanese learning platform.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0d0d0d",
};

const navItems = [
  { label: "Dashboard", active: true },
  { label: "Grammar", active: false },
  { label: "Review", active: false },
  { label: "Vocabulary", active: false },
  { label: "Kanji", active: false },
  { label: "Settings", active: false },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar" aria-label="Primary navigation">
            <div className="brand">
              <span className="brand-title">Yomi</span>
              <span className="brand-subtitle">Foundation</span>
            </div>
            <nav className="nav">
              {navItems.map((item) =>
                item.active ? (
                  <a
                    aria-current="page"
                    className="nav-item nav-item-active"
                    href="/"
                    key={item.label}
                  >
                    <span>{item.label}</span>
                  </a>
                ) : (
                  <button
                    aria-disabled="true"
                    className="nav-item nav-item-disabled"
                    disabled
                    key={item.label}
                    type="button"
                  >
                    <span>{item.label}</span>
                    <span className="nav-badge">Later</span>
                  </button>
                )
              )}
            </nav>
          </aside>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}

