import React from "react";

const NODE_POSITIONS = {
  billing_server: { x: 18, y: 18 },
  oracle_database: { x: 50, y: 18 },
  archive_storage: { x: 82, y: 18 },
  order_platform: { x: 18, y: 60 },
  subscriber_platform: { x: 50, y: 60 },
  sms_gateway: { x: 82, y: 60 },
  api_gateway: { x: 50, y: 85 },
};

const NODE_ICONS = {
  billing_server: "💳",
  oracle_database: "🗄",
  archive_storage: "📦",
  order_platform: "🛒",
  subscriber_platform: "👥",
  sms_gateway: "✉",
  api_gateway: "🌐",
};

function getNodePosition(nodeId, index) {
  return NODE_POSITIONS[nodeId] || { x: 18 + (index % 3) * 32, y: 20 + Math.floor(index / 3) * 40 };
}

function formatStatusLabel(status) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function TopologyPlaceholder({ nodes, dependencies, onSelectNode, selectedNodeId }) {
  const positions = Object.fromEntries(nodes.map((node, index) => [node.id, getNodePosition(node.id, index)]));

  return (
    <section className="panel panel--topology">
      <div className="panel__header">
        <div>
          <div className="panel__eyebrow">Network Topology</div>
          <h2 className="panel__title">7 Node Mock Topology</h2>
        </div>
        <div className="topology-legend" aria-label="Status legend">
          <span className="legend-item"><span className="legend-dot legend-dot--healthy" />Healthy</span>
          <span className="legend-item"><span className="legend-dot legend-dot--warning" />Warning</span>
          <span className="legend-item"><span className="legend-dot legend-dot--critical" />Critical</span>
          <span className="legend-item"><span className="legend-dot legend-dot--not-scanned" />Not Scanned</span>
        </div>
      </div>

      <div className="topology-graph" role="list" aria-label="Mock network nodes">
        <svg className="topology-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 Z" className="topology-arrow" />
            </marker>
          </defs>
          {dependencies.map((edge, index) => {
            const from = positions[edge.from];
            const to = positions[edge.to];
            if (!from || !to) return null;
            return (
              <line
                key={`${edge.from}-${edge.to}-${index}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                className="topology-line"
                markerEnd="url(#arrowhead)"
              />
            );
          })}
        </svg>

        {nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            role="listitem"
            className={`topology-node topology-node--${node.status.replaceAll("_", "-")} ${selectedNodeId === node.id ? "is-selected" : ""}`}
            style={{ left: `${positions[node.id]?.x || 50}%`, top: `${positions[node.id]?.y || 50}%` }}
            onClick={() => onSelectNode(node.id)}
          >
            <div className="topology-node__icon" aria-hidden="true">
              {NODE_ICONS[node.id] || "◌"}
            </div>
            <div className="topology-node__content">
              <div className="topology-node__label">{node.label}</div>
              <div className={`mini-pill mini-pill--${node.status.replaceAll("_", "-")}`}>{formatStatusLabel(node.status)}</div>
              <div className="topology-node__activity">{node.activity}</div>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
