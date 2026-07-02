import React from "react";

const NAV_ICONS = {
  Overview: "◉",
  "Network Topology": "⟐",
  "Autonomous Discovery": "⟳",
  "Active Findings": "!",
  "Remediation Center": "⚙",
  "Agent Activity": "▣",
  Reports: "▤",
  "Audit Trail": "⌁",
  Settings: "◌",
};

export function Sidebar({ items, activeItem, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">AOC</div>
        <div>
          <div className="sidebar__eyebrow">Telecom OSS/BSS</div>
          <div className="sidebar__title">Operations Center</div>
        </div>
      </div>

      <nav className="sidebar__nav" aria-label="Primary">
        {items.map((item) => (
          <button
            key={item}
            type="button"
            className={`sidebar__item ${activeItem === item ? "is-active" : ""}`}
            onClick={() => onSelect(item)}
          >
            <span className="sidebar__icon" aria-hidden="true">
              {NAV_ICONS[item] || "•"}
            </span>
            {item}
          </button>
        ))}
      </nav>

      <div className="sidebar__status-card">
        <div className="sidebar__status-label">System Status</div>
        <div className="sidebar__status-value">All Systems Operational</div>
      </div>
    </aside>
  );
}
