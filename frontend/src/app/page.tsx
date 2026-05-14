"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { HealthPanel } from "./health-panel";

export default function Home() {
  const { auth } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, router]);

  if (auth.status === "loading") {
    return (
      <>
        <header className="topbar">
          <h1 className="page-title">Dashboard</h1>
        </header>
        <section className="dashboard" aria-label="Loading">
          <div className="panel">
            <p>Loading…</p>
          </div>
        </section>
      </>
    );
  }

  if (auth.status === "unauthenticated") {
    return null;
  }

  return (
    <>
      <header className="topbar">
        <h1 className="page-title">Dashboard</h1>
        <span className="status-pill status-pill-ok">Phase 2 auth</span>
      </header>
      <section className="dashboard" aria-label="Dashboard">
        <div className="panel">
          <h2>Welcome, {auth.user.display_name}</h2>
          <p>
            Signed in as <strong>{auth.user.username}</strong>
            {auth.user.is_admin ? " · Admin" : ""}. Learning workflows are
            being implemented in upcoming phases.
          </p>
        </div>
        <HealthPanel />
      </section>
    </>
  );
}
