import React from "react";

export function TopBar({
  title,
  status,
  statusTone,
  onStartScan,
  onResetDemo,
  loading,
}) {
  return (
    <header className="topbar">
      <div>
        <div className="topbar__eyebrow">Autonomous Multi-Agent Operation Center</div>
        <h1 className="topbar__title">{title}</h1>
      </div>

      <div className="topbar__actions">
        <div className={`status-pill status-pill--${statusTone}`}>{status}</div>
        <button type="button" className="button button--secondary" onClick={onResetDemo}>
          Reset Demo
        </button>
        <button type="button" className="button button--primary" onClick={onStartScan} disabled={loading}>
          {loading ? "Scanning..." : "Start Autonomous Scan"}
        </button>
      </div>
    </header>
  );
}
