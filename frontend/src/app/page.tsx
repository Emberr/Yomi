import { HealthPanel } from "./health-panel";

export default function Home() {
  return (
    <>
      <header className="topbar">
        <h1 className="page-title">Dashboard</h1>
        <span className="status-pill">Phase 1 foundation</span>
      </header>
      <section className="dashboard" aria-label="Foundation status">
        <div className="panel">
          <h2>Stack status</h2>
          <p>
            The frontend shell is active. Learning workflows remain disabled
            until their backend systems are implemented in later phases.
          </p>
        </div>
        <HealthPanel />
      </section>
    </>
  );
}

