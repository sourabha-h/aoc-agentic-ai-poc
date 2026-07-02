import React from "react";

export function DetailsPanel({
  node,
  inspectedNode,
  findings,
  ragGuidance,
  workflowTimeline = [],
  selectedNodeId,
  issue = null,
}) {
  if (issue) {
    const impactedNodes = [...(issue.affected_nodes || [])]
      .sort((left, right) => {
        const preferredOrder = ["oracle_database", "archive_storage"];
        const leftIndex = preferredOrder.indexOf(left.node_id);
        const rightIndex = preferredOrder.indexOf(right.node_id);
        const safeLeft = leftIndex === -1 ? preferredOrder.length : leftIndex;
        const safeRight = rightIndex === -1 ? preferredOrder.length : rightIndex;
        return safeLeft - safeRight;
      })
      .map((nodeItem) => nodeItem.display_name)
      .join(", ");
    const displayTitle = issue.issue_id === "archive_storage_cleanup" || issue.title === "Archive storage cleanup required"
      ? "Archive Storage Capacity Issue"
      : issue.title;
    const displayAction = issue.issue_id === "archive_storage_cleanup" || issue.action === "cleanup_archive_storage"
      ? "Archive Storage Cleanup"
      : issue.recommended_action;

    return (
      <section className="panel panel--details">
        <div className="panel__header">
          <div>
            <div className="panel__eyebrow">Right-Side Details</div>
            <h2 className="panel__title">{displayTitle}</h2>
          </div>
          <div className={`status-pill status-pill--${issue.severity === "critical" ? "critical" : "warning"}`}>{issue.severity}</div>
        </div>

        <div className="panel__section">
          <div className="detail-metric">
            <span className="detail-metric__label">Issue:</span>
            <span>{displayTitle}</span>
          </div>
          <div className="detail-metric">
            <span className="detail-metric__label">Impacted Nodes:</span>
            <span>{impactedNodes}</span>
          </div>
          <div className="detail-metric">
            <span className="detail-metric__label">Recommended Action:</span>
            <span>{displayAction}</span>
          </div>
          <div className="detail-metric">
            <span className="detail-metric__label">Risk:</span>
            <span>{issue.risk}</span>
          </div>
        </div>
      </section>
    );
  }

  const healthEvent = workflowTimeline.find((item) => item.purpose === "health_check_guidance" && item.node_id === selectedNodeId);
  const resolutionEvent = workflowTimeline.find((item) => item.purpose === "resolution_guidance");
  const healthMatches = Array.isArray(healthEvent?.rag_results) ? healthEvent.rag_results : [];
  const resolutionMatches = Array.isArray(resolutionEvent?.rag_results) ? resolutionEvent.rag_results : [];
  const hasRagUsage = Boolean(healthEvent || resolutionEvent);
  const sourceCount = new Set(
    [...healthMatches, ...resolutionMatches]
      .map((item) => item.source_file)
      .filter(Boolean),
  ).size;

  return (
    <section className="panel panel--details">
      <div className="panel__header">
        <div>
          <div className="panel__eyebrow">Right-Side Details</div>
          <h2 className="panel__title">{node.title}</h2>
        </div>
        <div className={`status-pill status-pill--${node.status}`}>{node.status}</div>
      </div>

      <div className="panel__section">
        <div className="panel__section-title">RAG Guidance Used</div>
        <div className="detail-metric">
          <span className="detail-metric__label">RAG Used:</span>
          <span>{hasRagUsage ? "Yes" : "No"}</span>
        </div>
        <div className="detail-metric">
          <span className="detail-metric__label">Source Count:</span>
          <span>{sourceCount}</span>
        </div>
      </div>
    </section>
  );
}
