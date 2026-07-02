import React from "react";

export function StatusCard({ name, status, summary, onClick, selected }) {
  return (
    <button type="button" className={`status-card status-card--${status} ${selected ? "is-selected" : ""}`} onClick={onClick}>
      <div className="status-card__header">
        <span className="status-card__name">{name}</span>
        <span className={`mini-pill mini-pill--${status}`}>{status}</span>
      </div>
      <p className="status-card__summary">{summary}</p>
    </button>
  );
}
