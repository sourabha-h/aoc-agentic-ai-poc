const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  return response.json();
}

export function fetchStatus() {
  return request("/api/status");
}

export function startScan(autoApprove = false) {
  return request("/api/scan", {
    method: "POST",
    body: JSON.stringify({ auto_approve: autoApprove }),
  });
}

export function approveScan() {
  return request("/api/approve", {
    method: "POST",
  });
}

export function resetDemo() {
  return request("/api/reset", {
    method: "POST",
  });
}
