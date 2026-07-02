import React, { useEffect, useMemo, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { DetailsPanel } from "./components/DetailsPanel";
import { AuditTrailPanel } from "./components/AuditTrailPanel";
import { TimelinePanel } from "./components/TimelinePanel";
import { TopologyPlaceholder } from "./components/TopologyPlaceholder";
import { initialTopologyNodes, navItems, workflowSummary } from "./data/mockData";
import { approveScan, fetchStatus, resetDemo, startScan } from "./api";

function mapWorkflowStatus(payload, scanLoading) {
  if (!payload || payload.workflow_status === "ready" || payload.status === "idle") return "Ready for Autonomous Scan";
  if (payload?.workflow_status === "running" && (payload?.consolidated_issues || []).length > 0) return "Remediation In Progress";
  if (scanLoading || payload?.workflow_status === "running") return "Autonomous Discovery Running";
  if (payload?.workflow_status === "waiting_approval" || payload?.approval_status === "WAITING_FOR_APPROVAL") {
    return "Waiting for Approval";
  }
  if (payload?.workflow_status === "completed" && payload?.final_status) return payload.final_status;
  if (payload?.approval_status === "rejected") return "Guardrail Rejected";
  if (payload?.verification_status === "healthy") return "Verified Healthy";
  if (payload?.verification_status === "unhealthy") return "Manual Review Required";
  return "Completed with Findings";
}

function mapStatusTone(status, payload) {
  if (!status) return "warning";
  if (status === "Ready for Autonomous Scan") return "ready";
  if (status === "Healthy" || status === "Verified Healthy") return "healthy";
  if (status === "Autonomous Discovery Running") return "warning";
  if (status === "Remediation In Progress") return "warning";
  if (status === "Waiting for Approval") return "warning";
  if (status === "Escalated") return "critical";
  if (status === "Manual Review Required") return "critical";
  if (status === "Completed with Findings") {
    const hasCritical = (payload?.active_findings || []).some((finding) => finding.severity === "critical");
    return hasCritical ? "critical" : "warning";
  }
  return "warning";
}

function deriveNodeStatus(nodeId, payload) {
  if (!payload || payload.workflow_status === "ready" || payload.status === "idle") return "not_scanned";
  const node = (payload?.topology?.nodes || []).find((item) => item.node_id === nodeId);
  if (node?.status) return node.status;
  return "not_scanned";
}

function getNodeActivity(nodeId, payload, scanLoading, pollTick) {
  const node = (payload?.topology?.nodes || []).find((item) => item.node_id === nodeId);
  if (scanLoading || payload?.workflow_status === "running") {
    const nodeIndex = (payload?.topology?.nodes || []).findIndex((item) => item.node_id === nodeId);
    const runningActivities = ["Retrieving RAG guidance", "Running df -kh", "Running service --status-all", "Analysing output"];
    return runningActivities[(Math.max(0, pollTick) + Math.max(0, nodeIndex)) % runningActivities.length];
  }
  if (node?.current_activity) return node.current_activity;
  return "Waiting for scan";
}

function formatTimelineEvent(item) {
  if (item.agent === "supervisor_start") {
    return { agent: "Supervisor", detail: item.message || "Scan started" };
  }
  if (item.purpose === "health_check_guidance") {
    return { agent: "Discovery", detail: `Loaded health-check guidance for ${item.node_id}` };
  }
  if (item.purpose === "resolution_guidance") {
    return { agent: "Discovery", detail: "Loaded resolution guidance from runbooks" };
  }
  if (item.purpose === "findings") {
    const count = Array.isArray(item.findings) ? item.findings.length : 0;
    return { agent: "Discovery", detail: count > 0 ? `${count} findings identified` : "No findings identified" };
  }
  if (item.agent === "planning_agent" && item.purpose === "plan") {
    return { agent: "Planning", detail: "Remediation plan prepared" };
  }
  if (item.agent === "guardrail_agent" && item.purpose === "guardrail_result") {
    return { agent: "Guardrail", detail: item.result === "approved" ? "Plan approved" : "Plan rejected" };
  }
  if (item.agent === "approval_gate" && item.purpose === "approval_status") {
    if (item.approval_status === "approved") return { agent: "Approval", detail: "Auto-approved" };
    if (item.approval_status === "WAITING_FOR_APPROVAL") return { agent: "Approval", detail: "Waiting for approval" };
    return { agent: "Approval", detail: "Approval rejected" };
  }
  if (item.agent === "execution_agent" && item.purpose === "execution_result") {
    return {
      agent: "Execution",
      detail: `Ran ${item.action || "remediation"} attempt ${item.remediation_attempts || 0}`,
    };
  }
  if (item.agent === "verification_agent" && item.purpose === "verification_result") {
    return { agent: "Verification", detail: `Verification ${item.verification_status}` };
  }
  if (item.agent === "escalation_agent" && item.purpose === "retry_or_escalation") {
    return { agent: "Escalation", detail: item.result === "escalation" ? "Escalated after retry limit" : "Retry scheduled" };
  }
  if (item.agent === "reporting_agent") {
    return { agent: "Reporting", detail: item.message || "Final report generated" };
  }
  return null;
}

function getSummaryDescription(type, workflowData, workflowStatus) {
  if (type === "findings") {
    const count = workflowData?.active_findings?.length || 0;
    if (count > 0) return "View discovered evidence";
    return "No active findings detected.";
  }
  if (type === "issues") {
    return "Root issues requiring action";
  }
  if (type === "affected_nodes") {
    return "Oracle Database and Archive and Backup Storage are impacted";
  }
  if (type === "verification") {
    if (!workflowData) return "Awaiting Remediation";
    if (workflowData?.final_report?.status === "escalated" || workflowData?.approval_status === "rejected") {
      return "Manual Review Required";
    }
    if (workflowData?.verification_status === "healthy") return "Verified Healthy";
    if (workflowData?.workflow_status === "running" && Number(workflowData?.remediation_attempts || 0) > 0) {
      return "Retry in Progress";
    }
    if (workflowData?.workflow_status === "running" && workflowData?.approval_status === "approved") {
      return "Verification Pending";
    }
    if (workflowData?.verification_status === "unhealthy") return "Verification Failed";
    return "Awaiting Remediation";
  }
  return workflowStatus;
}

function formatSummaryValue(type, workflowData) {
  if (type === "findings") {
    return String(workflowData?.active_findings?.length || 0);
  }
  if (type === "issues") {
    return String(workflowData?.consolidated_issues?.length || 0);
  }
  if (type === "affected_nodes") {
    const issueCounts = (workflowData?.consolidated_issues || []).map((issue) => issue.affected_nodes?.length || 0);
    return String(issueCounts.reduce((total, count) => total + count, 0));
  }
  if (type === "verification") {
    const verification = workflowData?.verification_status;
    if (workflowData?.final_status) return workflowData.final_status;
    if (workflowData?.final_report?.status === "escalated" || workflowData?.approval_status === "rejected") return "Manual Review Required";
    if (verification === "healthy") return "Verified Healthy";
    if (workflowData?.workflow_status === "running" && Number(workflowData?.remediation_attempts || 0) > 0) return "Retry in Progress";
    if (workflowData?.workflow_status === "running" && workflowData?.approval_status === "approved") return "Verification Pending";
    if (verification === "unhealthy") return "Manual Review Required";
    return "Awaiting Remediation";
  }
  return "0";
}

function formatIssueTitle(issue) {
  if (!issue) return "";
  if (issue.issue_id === "archive_storage_cleanup" || issue.title === "Archive storage cleanup required") {
    return "Archive Storage Capacity Issue";
  }
  return issue.title || "";
}

function formatIssueNodes(issue) {
  if (!issue) return "";
  const preferredOrder = ["oracle_database", "archive_storage"];
  const nodes = [...(issue.affected_nodes || [])].sort((left, right) => {
    const leftIndex = preferredOrder.indexOf(left.node_id);
    const rightIndex = preferredOrder.indexOf(right.node_id);
    const safeLeft = leftIndex === -1 ? preferredOrder.length : leftIndex;
    const safeRight = rightIndex === -1 ? preferredOrder.length : rightIndex;
    return safeLeft - safeRight;
  });
  return nodes.map((node) => node.display_name).join(", ");
}

function formatRecommendedAction(issue) {
  if (!issue) return "";
  if (issue.issue_id === "archive_storage_cleanup" || issue.action === "cleanup_archive_storage") {
    return "Archive Storage Cleanup";
  }
  return issue.recommended_action || "";
}

export default function App() {
  const [activeNav, setActiveNav] = useState("Overview");
  const [selectedNodeId, setSelectedNodeId] = useState("archive_storage");
  const [workflowData, setWorkflowData] = useState(null);
  const [workflowStatus, setWorkflowStatus] = useState("Ready for Autonomous Scan");
  const [scanLoading, setScanLoading] = useState(false);
  const [scanSessionActive, setScanSessionActive] = useState(false);
  const [approvalPending, setApprovalPending] = useState(false);
  const [pollTick, setPollTick] = useState(0);
  const [findingsExpanded, setFindingsExpanded] = useState(false);
  const [selectedIssueId, setSelectedIssueId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    async function loadStatus() {
      try {
        const payload = await fetchStatus();
        if (ignore) return;
        if (payload.workflow_status === "running" || payload.workflow_status === "completed" || payload.workflow_status === "waiting_approval" || payload.status === "ok") {
          setWorkflowData(payload);
          setWorkflowStatus(mapWorkflowStatus(payload, payload.workflow_status === "running"));
          setScanSessionActive(payload.workflow_status === "running");
          setScanLoading(payload.workflow_status === "running");
          setApprovalPending(payload.workflow_status === "waiting_approval");
        } else {
          setWorkflowData(null);
          setWorkflowStatus("Ready for Autonomous Scan");
          setScanSessionActive(false);
          setScanLoading(false);
          setApprovalPending(false);
        }
        setError("");
      } catch (err) {
        if (ignore) return;
        setError("Backend unavailable. Start the API server at http://localhost:8000.");
      }
    }

    loadStatus();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!scanSessionActive || workflowData?.workflow_status !== "running") return undefined;

    let ignore = false;
    const interval = window.setInterval(async () => {
      try {
        const payload = await fetchStatus();
        if (ignore) return;
        if (payload.workflow_status === "completed" || payload.workflow_status === "ready") {
          setWorkflowData(payload);
          setWorkflowStatus(mapWorkflowStatus(payload, false));
          setScanLoading(false);
          setScanSessionActive(false);
          setApprovalPending(false);
          window.clearInterval(interval);
        } else if (payload.workflow_status === "waiting_approval") {
          setWorkflowData(payload);
          setWorkflowStatus(mapWorkflowStatus(payload, false));
          setScanLoading(false);
          setScanSessionActive(false);
          setApprovalPending(true);
          window.clearInterval(interval);
        } else {
          setWorkflowData(payload);
          setWorkflowStatus(mapWorkflowStatus(payload, true));
          setPollTick((value) => value + 1);
        }
        setError("");
      } catch (err) {
        if (!ignore) {
          setError("Backend unavailable. Start the API server at http://localhost:8000.");
        }
      }
    }, 1000);

    return () => {
      ignore = true;
      window.clearInterval(interval);
    };
  }, [scanSessionActive, workflowData]);

  const timelineEvents = useMemo(() => {
    const timeline = workflowData?.agent_timeline || [];
    const healthGuidance = timeline.find((item) => item.purpose === "health_check_guidance");
    const resolutionGuidance = timeline.find((item) => item.purpose === "resolution_guidance");
    const discoveryFindings = timeline.find((item) => item.purpose === "findings");

    const events = [];
    if (healthGuidance) {
      const guidanceCount = timeline.filter((item) => item.purpose === "health_check_guidance").length;
      events.push({
        time: healthGuidance.timestamp?.slice(11, 19) || "00:00:00",
        agent: "Discovery",
        detail: `Loaded health-check guidance for ${guidanceCount} node${guidanceCount === 1 ? "" : "s"}`,
      });
    }
    if (discoveryFindings) {
      events.push({
        time: discoveryFindings.timestamp?.slice(11, 19) || "00:00:00",
        agent: "Discovery",
        detail:
          Array.isArray(discoveryFindings.findings) && discoveryFindings.findings.length > 0
            ? `${discoveryFindings.findings.length} findings identified`
            : "No findings identified",
      });
    }
    if (resolutionGuidance) {
      events.push({
        time: resolutionGuidance.timestamp?.slice(11, 19) || "00:00:00",
        agent: "Discovery",
        detail: "Loaded resolution guidance from runbooks",
      });
    }

    timeline.forEach((item) => {
      if (item.purpose === "health_check_guidance" || item.purpose === "findings" || item.purpose === "resolution_guidance") {
        return;
      }
      const summary = formatTimelineEvent(item);
      if (!summary) return;
      events.push({
        time: item.timestamp?.slice(11, 19) || "00:00:00",
        agent: summary.agent,
        detail: summary.detail,
      });
    });

    return events;
  }, [workflowData]);

  const nodeMap = useMemo(() => {
    const nodes = workflowData?.topology?.nodes || initialTopologyNodes;
    return Object.fromEntries(nodes.map((node) => [node.node_id, node]));
  }, [workflowData]);

  const topologyNodes = useMemo(() => {
    const nodes = workflowData?.topology?.nodes || initialTopologyNodes.map((node) => ({
      node_id: node.id,
      display_name: node.label,
      dependencies: [],
      status: "not_scanned",
      current_activity: "Waiting for scan",
    }));
    return nodes.map((node) => {
      return {
        id: node.node_id,
        label: node.display_name,
        status: node.status || deriveNodeStatus(node.node_id, workflowData),
        activity: node.current_activity || getNodeActivity(node.node_id, workflowData, scanLoading, pollTick),
      };
    });
  }, [pollTick, scanLoading, workflowData]);

  const selectedNode = useMemo(() => nodeMap[selectedNodeId], [nodeMap, selectedNodeId]);
  const selectedInspectedNode = workflowData?.inspected_nodes?.[selectedNodeId];
  const selectedFindings = useMemo(
    () => (workflowData?.active_findings || []).filter((finding) => finding.node_id === selectedNodeId),
    [selectedNodeId, workflowData],
  );
  const auditEvents = workflowData?.audit_events || [];
  const consolidatedIssues = workflowData?.consolidated_issues || [];
  const activeFindings = useMemo(() => {
    const findings = workflowData?.active_findings || workflowData?.initial_findings || [];
    const deduped = [];
    const seen = new Set();
    findings.forEach((finding) => {
      const key = `${finding.node_id}:${finding.severity}:${finding.summary}:${(finding.evidence || []).join("|")}`;
      if (seen.has(key)) return;
      seen.add(key);
      deduped.push(finding);
    });
    return deduped;
  }, [workflowData]);
  const selectedIssue = useMemo(
    () => consolidatedIssues.find((issue) => issue.issue_id === selectedIssueId) || consolidatedIssues[0] || null,
    [consolidatedIssues, selectedIssueId],
  );

  function handleOpenRemediationCenter() {
    setActiveNav("Remediation Center");
  }

  function handleToggleFindings() {
    setActiveNav("Overview");
    setFindingsExpanded((value) => !value);
  }

  async function handleApproveSelected() {
    if (!selectedIssue) return;
    setError("");
    try {
      const payload = await approveScan();
      if (payload.status === "error") {
        setError(payload.message || "Approval failed.");
        return;
      }
      setWorkflowData({
        ...(workflowData || {}),
        ...payload,
        workflow_status: "running",
        consolidated_issues: workflowData?.consolidated_issues || [],
      });
      setWorkflowStatus("Remediation In Progress");
      setScanSessionActive(true);
      setScanLoading(true);
      setApprovalPending(false);
      setPollTick(0);
    } catch (err) {
      setError("Approval failed. The backend API may be unavailable.");
    }
  }

  const summaryCards = useMemo(
    () => [
      {
        key: "findings",
        icon: "!",
        title: "Active Findings",
        value: String(activeFindings.length),
        description: getSummaryDescription("findings", workflowData, workflowStatus),
        clickable: true,
        onClick: handleToggleFindings,
      },
      {
        key: "issues",
        icon: "↻",
        title: "Root Issues Requiring Action",
        value: formatSummaryValue("issues", workflowData),
        description: getSummaryDescription("issues", workflowData, workflowStatus),
        clickable: true,
        onClick: handleOpenRemediationCenter,
      },
      {
        key: "affected_nodes",
        icon: "⌛",
        title: "Affected Nodes",
        value: formatSummaryValue("affected_nodes", workflowData),
        description: getSummaryDescription("affected_nodes", workflowData, workflowStatus),
        clickable: true,
        onClick: handleOpenRemediationCenter,
      },
      {
        key: "verification",
        icon: "✓",
        title: "Verification Status",
        value: formatSummaryValue("verification", workflowData),
        description: getSummaryDescription("verification", workflowData, workflowStatus),
      },
    ],
    [activeFindings.length, workflowData, workflowStatus],
  );

  useEffect(() => {
    if (topologyNodes.length > 0 && !nodeMap[selectedNodeId]) {
      setSelectedNodeId(topologyNodes[0].id);
    }
  }, [nodeMap, selectedNodeId, topologyNodes]);

  useEffect(() => {
    if (consolidatedIssues.length === 0) {
      setSelectedIssueId("");
      return;
    }
    if (!selectedIssueId || !consolidatedIssues.some((issue) => issue.issue_id === selectedIssueId)) {
      setSelectedIssueId(consolidatedIssues[0].issue_id);
    }
  }, [consolidatedIssues, selectedIssueId]);

  async function handleStartScan() {
    setScanLoading(true);
    setWorkflowStatus("Autonomous Discovery Running");
    setError("");
    try {
      const payload = await startScan(false);
      setWorkflowData(payload);
      setWorkflowStatus(mapWorkflowStatus(payload, true));
      setScanSessionActive(true);
      setApprovalPending(false);
      setPollTick(0);
      if (payload.topology?.nodes?.length) {
        setSelectedNodeId(payload.topology.nodes[0].node_id);
      }
      setSelectedIssueId("");
    } catch (err) {
      setError("Scan failed. The backend API may be unavailable.");
      setScanLoading(false);
      setScanSessionActive(false);
      setApprovalPending(false);
    }
  }

  async function handleResetDemo() {
    setError("");
    try {
      const payload = await resetDemo();
      if (payload.status === "error") {
        setError(payload.message || "Reset failed.");
        return;
      }
      setWorkflowData(null);
      setWorkflowStatus("Ready for Autonomous Scan");
      setScanLoading(false);
      setScanSessionActive(false);
      setApprovalPending(false);
      setPollTick(0);
      setSelectedNodeId("archive_storage");
      setFindingsExpanded(false);
      setSelectedIssueId("");
    } catch (err) {
      setError("Reset failed. The backend API may be unavailable.");
    }
  }

  return (
    <div className="app-shell">
      <Sidebar items={navItems} activeItem={activeNav} onSelect={setActiveNav} />

      <main className="main-shell">
        <TopBar
          title={workflowSummary.title}
          status={workflowStatus}
          statusTone={mapStatusTone(workflowStatus, workflowData)}
          onStartScan={handleStartScan}
          onResetDemo={handleResetDemo}
          loading={scanLoading || scanSessionActive}
        />

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="workspace">
          <section className="workspace__main">
            {activeNav === "Audit Trail" ? (
              <AuditTrailPanel events={auditEvents} />
            ) : activeNav === "Remediation Center" ? (
              <section className="panel panel--remediation">
                <div className="panel__header">
                  <div>
                    <div className="panel__eyebrow">Remediation Center</div>
                    <h2 className="panel__title">Issues and Pending Actions</h2>
                  </div>
                </div>

                <div className="status-grid">
                  <section className="status-card status-card--warning">
                    <div className="status-card__header">
                      <div>
                        <div className="panel__eyebrow">Root Issues Requiring Action</div>
                        <div className="status-card__name">{formatSummaryValue("issues", workflowData)}</div>
                      </div>
                      <div className="mini-pill mini-pill--warning">Review</div>
                    </div>
                    <p className="status-card__summary">Review recommended remediation for the current findings.</p>
                  </section>
                  <section className="status-card status-card--warning">
                    <div className="status-card__header">
                      <div>
                        <div className="panel__eyebrow">Affected Nodes</div>
                        <div className="status-card__name">{formatSummaryValue("affected_nodes", workflowData)}</div>
                      </div>
                      <div className="mini-pill mini-pill--warning">Pending</div>
                    </div>
                    <p className="status-card__summary">{getSummaryDescription("affected_nodes", workflowData, workflowStatus)}</p>
                  </section>
                </div>

                <div className="panel__section">
                  <div className="panel__section-title">Archive Storage Issue</div>
                  {consolidatedIssues.length === 0 ? (
                    <div className="empty-state empty-state--inline">No archive-storage remediation requires approval.</div>
                  ) : (
                    <div className="remediation-list">
                      {consolidatedIssues.map((issue) => {
                        const selected = selectedIssue?.issue_id === issue.issue_id;
                        const displayTitle = formatIssueTitle(issue);
                        const displayNodes = formatIssueNodes(issue);
                        const displayAction = formatRecommendedAction(issue);
                        return (
                          <div
                            key={issue.issue_id}
                            className={`remediation-item ${selected ? "is-selected" : ""}`}
                            onClick={() => setSelectedIssueId(issue.issue_id)}
                          >
                            <label className="remediation-item__check" onClick={(event) => event.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={() => setSelectedIssueId(issue.issue_id)}
                              />
                              <span>Selected</span>
                            </label>
                            <div className="remediation-item__title">Issue: {displayTitle}</div>
                            <div className="remediation-item__meta">
                              <span className={`mini-pill mini-pill--${issue.severity === "critical" ? "critical" : "warning"}`}>{issue.severity}</span>
                            </div>
                            <div className="remediation-item__nodes">
                              Impacted Nodes: {displayNodes}
                            </div>
                            <div className="remediation-item__action">
                              Recommended Action: {displayAction}
                            </div>
                            <div className="remediation-item__risk">Risk: {issue.risk}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  <div className="remediation-actions">
                    <button
                      type="button"
                      className="button button--primary"
                      onClick={handleApproveSelected}
                      disabled={!selectedIssue || scanLoading || scanSessionActive}
                    >
                      Approve Selected Remediation
                    </button>
                  </div>
                </div>
              </section>
            ) : (
              <>
                <TopologyPlaceholder
                  nodes={topologyNodes}
                  dependencies={workflowData?.topology?.dependencies || []}
                  onSelectNode={setSelectedNodeId}
                  selectedNodeId={selectedNodeId}
                />

                {findingsExpanded ? (
                  <section className="panel panel--findings">
                    <div className="panel__header">
                      <div>
                        <div className="panel__eyebrow">Expanded Findings</div>
                        <h2 className="panel__title">Active Findings</h2>
                      </div>
                    </div>

                    {activeFindings.length === 0 ? (
                      <div className="empty-state empty-state--inline">No active findings to show.</div>
                    ) : (
                      <div className="findings-list">
                        {activeFindings.map((finding, index) => (
                          <div key={`${finding.node_id}-${finding.summary}-${index}`} className="finding-row">
                            <div className="finding-row__meta">
                              <div className="finding-row__node">{nodeMap[finding.node_id]?.display_name || finding.node_id}</div>
                              <div className={`mini-pill mini-pill--${finding.severity === "critical" ? "critical" : "warning"}`}>{finding.severity}</div>
                            </div>
                            <div className="finding-row__summary">{finding.summary}</div>
                            <div className="finding-row__evidence">
                              <div className="guidance-label">Evidence</div>
                              <div className="finding-row__evidence-list">
                                {(finding.evidence || []).length > 0 ? (
                                  finding.evidence.map((line, evidenceIndex) => (
                                    <div key={`${index}-${evidenceIndex}`} className="guidance-text empty-state--inline">
                                      {line}
                                    </div>
                                  ))
                                ) : (
                                  <div className="empty-state empty-state--inline">No evidence captured.</div>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                ) : null}

                <div className="workflow-summary-grid">
                  {summaryCards.map((card) => (
                    card.clickable ? (
                      <button
                        key={card.key}
                        type="button"
                        className="panel panel--compact summary-card summary-card--interactive"
                        onClick={card.onClick}
                        aria-label={card.title}
                      >
                        <div className="summary-card__top">
                          <div className="summary-card__icon" aria-hidden="true">
                            {card.icon}
                          </div>
                          <div className="summary-card__value">{card.value}</div>
                        </div>
                        <div>
                          <div className="panel__eyebrow">{card.title}</div>
                          <div className="summary-card__description">{card.description}</div>
                        </div>
                      </button>
                    ) : (
                      <section key={card.key} className="panel panel--compact summary-card">
                        <div className="summary-card__top">
                          <div className="summary-card__icon" aria-hidden="true">
                            {card.icon}
                          </div>
                          <div className="summary-card__value">{card.value}</div>
                        </div>
                        <div>
                          <div className="panel__eyebrow">{card.title}</div>
                          <div className="summary-card__description">{card.description}</div>
                        </div>
                      </section>
                    )
                  ))}
                </div>

                <TimelinePanel events={timelineEvents} />
              </>
            )}
          </section>

          <aside className="workspace__side">
            <DetailsPanel
              node={{
                title: selectedNode?.display_name || "Selected Node",
                status: deriveNodeStatus(selectedNodeId, workflowData),
                notes: [
                  workflowData?.workflow_status === "running" ? "Scanning in progress." : "Waiting for scan.",
                  "Use Start Autonomous Scan to refresh the workflow state.",
                ],
              }}
              inspectedNode={selectedInspectedNode}
              findings={selectedFindings}
              ragGuidance={selectedInspectedNode?.rag_guidance || workflowData?.rag_results || {}}
              workflowTimeline={workflowData?.agent_timeline || []}
              selectedNodeId={selectedNodeId}
              issue={activeNav === "Remediation Center" ? selectedIssue : null}
            />
          </aside>
        </div>
      </main>
    </div>
  );
}
