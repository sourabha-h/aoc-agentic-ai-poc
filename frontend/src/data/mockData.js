export const navItems = [
  "Overview",
  "Network Topology",
  "Autonomous Discovery",
  "Active Findings",
  "Remediation Center",
  "Agent Activity",
  "Reports",
  "Audit Trail",
  "Settings",
];

export const workflowSummary = {
  title: "Autonomous Multi-Agent Operation Center",
  status: "Ready",
  statusTone: "ready",
};

export const initialTopologyNodes = [
  { id: "billing_server", label: "Billing Server", status: "not-scanned", role: "Not Scanned" },
  { id: "oracle_database", label: "Oracle Database", status: "not-scanned", role: "Not Scanned" },
  { id: "archive_storage", label: "Archive Storage", status: "not-scanned", role: "Not Scanned" },
  { id: "order_platform", label: "Order Platform", status: "not-scanned", role: "Not Scanned" },
  { id: "subscriber_platform", label: "Subscriber Platform", status: "not-scanned", role: "Not Scanned" },
  { id: "sms_gateway", label: "SMS Gateway", status: "not-scanned", role: "Not Scanned" },
  { id: "api_gateway", label: "API Gateway", status: "not-scanned", role: "Not Scanned" },
];

export const initialNodeCards = initialTopologyNodes.map((node) => ({
  id: node.id,
  name: node.label,
  status: "not-scanned",
  summary: "Not Scanned",
}));
