import { useState, useEffect } from "react";
import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000/api/v1" });
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

const ACTION_COLORS = {
  LOGIN_SUCCESS:   { bg: "#052e16", text: "#4ade80" },
  LOGIN_FAILED:    { bg: "#450a0a", text: "#f87171" },
  LOGOUT:          { bg: "#1c1917", text: "#a8a29e" },
  SERVER_CREATED:  { bg: "#0c1a2e", text: "#60a5fa" },
  SERVER_DELETED:  { bg: "#450a0a", text: "#f87171" },
  CONFIG_CREATED:  { bg: "#0c1a2e", text: "#60a5fa" },
  CONFIG_UPDATED:  { bg: "#1c1917", text: "#fbbf24" },
  CONFIG_DELETED:  { bg: "#450a0a", text: "#f87171" },
  CONFIG_DEPLOYED: { bg: "#052e16", text: "#4ade80" },
  JOB_TRIGGERED:   { bg: "#0c1a2e", text: "#a78bfa" },
  JOB_COMPLETED:   { bg: "#052e16", text: "#4ade80" },
  JOB_FAILED:      { bg: "#450a0a", text: "#f87171" },
};

function ActionBadge({ action }) {
  const colors = ACTION_COLORS[action] || { bg: "#1e293b", text: "#94a3b8" };
  return (
    <span style={{
      background: colors.bg, color: colors.text,
      padding: "2px 8px", borderRadius: 4, fontSize: 11,
      fontFamily: "monospace", fontWeight: 600, whiteSpace: "nowrap"
    }}>
      {action}
    </span>
  );
}

export default function AuditLog() {
  const [logs, setLogs]         = useState([]);
  const [summary, setSummary]   = useState(null);
  const [total, setTotal]       = useState(0);
  const [page, setPage]         = useState(1);
  const [pages, setPages]       = useState(1);
  const [loading, setLoading]   = useState(false);

  // Filters
  const [filterAction,   setFilterAction]   = useState("");
  const [filterUser,     setFilterUser]     = useState("");
  const [filterStatus,   setFilterStatus]   = useState("");
  const [filterDays,     setFilterDays]     = useState(7);

  const fetchLogs = async (p = 1) => {
    setLoading(true);
    try {
      const params = { page: p, per_page: 50, days: filterDays };
      if (filterAction) params.action = filterAction;
      if (filterUser)   params.user   = filterUser;
      if (filterStatus) params.status = filterStatus;
      const res = await api.get("/audit/", { params });
      setLogs(res.data.logs);
      setTotal(res.data.total);
      setPages(res.data.pages);
      setPage(p);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await api.get("/audit/summary", { params: { days: filterDays } });
      setSummary(res.data);
    } catch (e) {}
  };

  useEffect(() => { fetchLogs(1); fetchSummary(); }, [filterDays, filterAction, filterUser, filterStatus]);

  const handleExport = () => {
    const token = localStorage.getItem("token");
    window.open(`http://localhost:8000/api/v1/audit/export?days=${filterDays}&token=${token}`);
  };

  const cardStyle = {
    background: "#1e293b", borderRadius: 10, padding: "1rem 1.25rem", marginBottom: 12
  };

  return (
    <div style={{ padding: "1.5rem", color: "#f1f5f9" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Audit Log</h2>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            {total} events in the last {filterDays} days
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <select value={filterDays} onChange={e => setFilterDays(Number(e.target.value))}
            style={{ background: "#0f172a", color: "#94a3b8", border: "1px solid #334155",
              borderRadius: 6, padding: "6px 10px", fontSize: 13 }}>
            <option value={1}>Last 24h</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={handleExport}
            style={{ background: "#1e40af", color: "#fff", border: "none",
              borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }}>
            ⬇ Export CSV
          </button>
          <button onClick={() => fetchLogs(1)}
            style={{ background: "#334155", color: "#fff", border: "none",
              borderRadius: 6, padding: "6px 14px", fontSize: 13, cursor: "pointer" }}>
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 20 }}>
          {summary.by_action.slice(0, 6).map(a => (
            <div key={a.action} style={{ ...cardStyle, marginBottom: 0, textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9" }}>{a.count}</div>
              <ActionBadge action={a.action} />
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          style={{ background: "#0f172a", color: "#94a3b8", border: "1px solid #334155",
            borderRadius: 6, padding: "6px 10px", fontSize: 13 }}>
          <option value="">All Actions</option>
          {Object.keys(ACTION_COLORS).map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <input placeholder="Filter by user..." value={filterUser}
          onChange={e => setFilterUser(e.target.value)}
          style={{ background: "#0f172a", color: "#94a3b8", border: "1px solid #334155",
            borderRadius: 6, padding: "6px 10px", fontSize: 13, width: 180 }}
        />
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          style={{ background: "#0f172a", color: "#94a3b8", border: "1px solid #334155",
            borderRadius: 6, padding: "6px 10px", fontSize: 13 }}>
          <option value="">All Statuses</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
        </select>
      </div>

      {/* Log table */}
      <div style={{ ...cardStyle, padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#0f172a", color: "#64748b" }}>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>Timestamp</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>User</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>Action</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>Resource</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>Detail</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>IP</th>
              <th style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 30, color: "#64748b" }}>
                Loading...
              </td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 30, color: "#64748b" }}>
                No audit events found
              </td></tr>
            ) : logs.map((log, i) => (
              <tr key={log.id} style={{ borderTop: "1px solid #1e293b",
                background: i % 2 === 0 ? "transparent" : "#0f172a20" }}>
                <td style={{ padding: "9px 14px", color: "#64748b", whiteSpace: "nowrap" }}>
                  {new Date(log.timestamp).toLocaleString()}
                </td>
                <td style={{ padding: "9px 14px", color: "#cbd5e1" }}>
                  {log.user}
                  {log.auth_method && (
                    <span style={{ color: "#475569", fontSize: 11, marginLeft: 6 }}>
                      [{log.auth_method}]
                    </span>
                  )}
                </td>
                <td style={{ padding: "9px 14px" }}>
                  <ActionBadge action={log.action} />
                </td>
                <td style={{ padding: "9px 14px", color: "#94a3b8" }}>
                  {log.resource}{log.resource_id ? ` #${log.resource_id}` : ""}
                </td>
                <td style={{ padding: "9px 14px", color: "#94a3b8", maxWidth: 300 }}>
                  <span title={log.detail} style={{ display: "block", overflow: "hidden",
                    textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {log.detail}
                  </span>
                </td>
                <td style={{ padding: "9px 14px", color: "#64748b", fontFamily: "monospace" }}>
                  {log.ip_address}
                </td>
                <td style={{ padding: "9px 14px" }}>
                  <span style={{
                    color: log.status === "success" ? "#4ade80" : "#f87171",
                    fontSize: 12, fontWeight: 600
                  }}>
                    {log.status === "success" ? "✓" : "✗"} {log.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16 }}>
          <button onClick={() => fetchLogs(page - 1)} disabled={page === 1}
            style={{ background: "#334155", color: "#fff", border: "none",
              borderRadius: 6, padding: "6px 14px", cursor: page === 1 ? "not-allowed" : "pointer" }}>
            ← Prev
          </button>
          <span style={{ color: "#64748b", padding: "6px 10px" }}>
            Page {page} of {pages}
          </span>
          <button onClick={() => fetchLogs(page + 1)} disabled={page === pages}
            style={{ background: "#334155", color: "#fff", border: "none",
              borderRadius: 6, padding: "6px 14px", cursor: page === pages ? "not-allowed" : "pointer" }}>
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
