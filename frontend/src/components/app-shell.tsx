"use client";

import { useRouter } from "next/navigation";
import { type ReactNode } from "react";
import { useAuth } from "@/contexts/auth-context";
import { apiLogout } from "@/lib/api";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", active: true },
  { label: "Grammar", active: false },
  { label: "Review", active: false },
  { label: "Vocabulary", active: false },
  { label: "Kanji", active: false },
  { label: "Settings", active: false },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { auth, clearUser } = useAuth();
  const router = useRouter();

  function handleLogout() {
    void (async () => {
      await apiLogout();
      clearUser();
      router.push("/login");
    })();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-title">Yomi</span>
          <span className="brand-subtitle">読み / 黄泉</span>
        </div>

        <nav className="nav">
          {NAV_ITEMS.map((item) =>
            item.active ? (
              <a
                aria-current="page"
                className="nav-item nav-item-active"
                href={item.href}
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
            ),
          )}
        </nav>

        <div className="user-section">
          {auth.status === "loading" && (
            <span className="user-loading" aria-label="Loading user">
              …
            </span>
          )}

          {auth.status === "authenticated" && (
            <>
              <div className="user-name">{auth.user.username}</div>
              {auth.user.is_admin && (
                <div className="user-role">Admin</div>
              )}
              <div className="user-actions">
                <a className="user-action-link" href="/change-password">
                  Change password
                </a>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={handleLogout}
                  type="button"
                >
                  Sign out
                </button>
              </div>
            </>
          )}

          {auth.status === "unauthenticated" && (
            <a className="btn btn-ghost btn-sm" href="/login">
              Sign in
            </a>
          )}
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
