import React, { useMemo, useState } from "react";

function formatDetails(event) {
  if (event.event_type === "RAG_QUERY") {
    return [
      ["Purpose", event.purpose || "Unknown"],
      ["Query", event.query || "Unknown"],
      ["Vector Store", event.vector_store || "ChromaDB"],
      ["Source file", event.source_file || "No matching guidance found"],
      ["Section", event.section || "No matching guidance found"],
      ["Similarity score", event.score ?? "N/A"],
      ["Retrieved content", event.retrieved_content || "No matching guidance found"],
    ];
  }

  return Object.entries(event.details || {}).map(([key, value]) => [key, typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)]);
}

export function AuditTrailPanel({ events }) {
  const [expanded, setExpanded] = useState({});

  const rows = useMemo(() => events || [], [events]);

  return (
    <section className="panel panel--audit">
      <div className="panel__header">
        <div>
          <div className="panel__eyebrow">Audit Trail</div>
          <h2 className="panel__title">Agent Events</h2>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="empty-state empty-state--center">
          <div>No audit events yet</div>
          <div>Run a scan to view traceable agent actions.</div>
        </div>
      ) : (
        <div className="audit-trail">
          <div className="audit-trail__header">
            <span>Time</span>
            <span>Agent</span>
            <span>Event Type</span>
            <span>Summary</span>
            <span>Details</span>
          </div>
          {rows.map((event, index) => {
            const rowId = `${event.timestamp || "unknown"}-${index}`;
            const isOpen = Boolean(expanded[rowId]);
            return (
              <div key={rowId} className="audit-trail__row">
                <span>{(event.timestamp || "").slice(11, 19) || "00:00:00"}</span>
                <span>{event.agent || "unknown"}</span>
                <span>{event.event_type || "UNKNOWN"}</span>
                <span>{event.summary || event.event_type || "Event"}</span>
                <button
                  type="button"
                  className="button button--secondary audit-trail__toggle"
                  onClick={() => setExpanded((value) => ({ ...value, [rowId]: !isOpen }))}
                >
                  {isOpen ? "Hide" : "Show"}
                </button>
                {isOpen ? (
                  <div className="audit-trail__details">
                    {formatDetails(event).map(([label, value]) => (
                      <div key={label} className="audit-trail__detail-row">
                        <span className="audit-trail__detail-label">{label}</span>
                        <span className="audit-trail__detail-value">{value}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
