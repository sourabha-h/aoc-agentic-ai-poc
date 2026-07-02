import React from "react";

export function TimelinePanel({ events }) {
  return (
    <section className="panel panel--timeline">
      <div className="panel__header">
        <div>
          <div className="panel__eyebrow">Bottom Timeline</div>
          <h2 className="panel__title">Workflow Events</h2>
        </div>
      </div>

      <div className="timeline">
        {events.length === 0 ? (
          <div className="empty-state empty-state--center">
            <div>No activity yet</div>
            <div>Start an autonomous scan to see agent activity and workflow progress here.</div>
          </div>
        ) : (
          events.map((event) => (
            <div key={`${event.time}-${event.agent}`} className="timeline__item">
              <div className="timeline__time">{event.time}</div>
              <div className="timeline__content">
                <div className="timeline__agent">{event.agent}</div>
                <div className="timeline__detail">{event.detail}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
