import { useState, useEffect } from "react";
import Login from "./Login";
import Dashboard from "./Dashboard";
import AuditLog from "./AuditLog";
import Settings from "./Settings";
import Users from "./Users";
import NotificationSettings from "./NotificationSettings";
import DRTemplates from "./DRTemplates";
import RestoreWizard from "./RestoreWizard";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const can = (user, action) => {
  const role = user?.role;
  if (role === "admin")  return true;
  if (role === "editor") return action !== "manage_users";
  if (role === "viewer") return action === "view";
  return false;
};

export default function App() {
  const [user,    setUser]    = useState(null);
  const [tab,     setTab]     = useState("dashboard");
  const [servers, setServers] = useState([]);
  const [backups, setBackups] = useState([]);
  const [jobs,    setJobs]    = useState([]);
  const [restoreTarget, setRestoreTarget] = useState(null);

  useEffect(() => {
    const token    = localStorage.getItem("token");
    const userData = localStorage.getItem("user");
    if (token && userData) setUser(JSON.parse(userData));
  }, []);

  const api = axios.create({ baseURL: `${API_BASE}/api/v1` });
  api.interceptors.request.use(cfg => {
    const token = localStorage.getItem("token");
    if (token) cfg.headers.Authorization = `Bearer ${token}`;
    return cfg;
  });

  useEffect(() => {
    if (!user) return;
    api.get("/servers/").then(r => setServers(r.data)).catch(console.error);
    api.get("/backups/").then(r => setBackups(r.data)).catch(console.error);
    api.get("/jobs/").then(r => setJobs(r.data)).catch(console.error);
  }, [user]);

  const handleLogout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  };

  if (!user) return <Login onLogin={u => setUser(u)} />;

  const TABS = [
    { id: "dashboard",     label: "📊 Dashboard",      roles: ["admin","editor","viewer"] },
    { id: "servers",       label: "🖥  Servers",        roles: ["admin","editor","viewer"] },
    { id: "backups",       label: "💾 Backup Configs",  roles: ["admin","editor","viewer"] },
    { id: "jobs",          label: "📋 Jobs",            roles: ["admin","editor","viewer"] },
    { id: "restores",      label: "🔄 Restores",        roles: ["admin","editor"] },
    { id: "notifications", label: "🔔 Notifications",   roles: ["admin"] },
    { id: "dr-templates",  label: "🛡️ DR Templates",    roles: ["admin","editor"] },
    { id: "audit",         label: "🔍 Audit Log",       roles: ["admin","editor","viewer"] },
    { id: "users",         label: "👥 Users",           roles: ["admin"] },
    { id: "settings",      label: "⚙️ Settings",        roles: ["admin"] },
  ].filter(t => t.roles.includes(user.role));

  const ROLE_BADGE = {
    admin:  { color: "#fbbf24", icon: "★", label: "Admin"  },
    editor: { color: "#60a5fa", icon: "✎", label: "Editor" },
    viewer: { color: "#94a3b8", icon: "👁", label: "Viewer" },
  };
  const badge = ROLE_BADGE[user.role] || ROLE_BADGE.viewer;

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#0f172a", color: "#f1f5f9", fontFamily: "system-ui, sans-serif" }}>

      {/* ── Sidebar ── */}
      <div style={{
        width: 220, minWidth: 220, background: "#1e293b", borderRight: "1px solid #334155",
        display: "flex", flexDirection: "column",
        position: "sticky", top: 0, height: "100vh", overflowY: "auto",
      }}>
        {/* Logo */}
        <div style={{ padding: "18px 16px 14px", borderBottom: "1px solid #334155" }}>
          <span style={{ color: "#f1f5f9", fontWeight: 700, fontSize: 15 }}>🔐 IDM Toolkit</span>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: tab === t.id ? "#3b82f6" : "transparent",
              color: tab === t.id ? "#fff" : "#94a3b8",
              border: "none", borderRadius: 6, padding: "8px 12px",
              fontSize: 13, cursor: "pointer", fontWeight: tab === t.id ? 600 : 400,
              textAlign: "left", width: "100%",
            }}>{t.label}</button>
          ))}
        </nav>

        {/* User + logout */}
        <div style={{ padding: "12px 14px", borderTop: "1px solid #334155" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span style={{ color: badge.color, fontSize: 11, fontWeight: 700,
              background: "#0f172a", borderRadius: 4, padding: "2px 6px", letterSpacing: "0.03em" }}>
              {badge.icon} {badge.label}
            </span>
          </div>
          <div style={{ color: "#64748b", fontSize: 12, marginBottom: 8 }}>{user.username}</div>
          <button onClick={handleLogout} style={{ background: "#334155", color: "#94a3b8",
            border: "none", borderRadius: 6, padding: "5px 10px", fontSize: 12, cursor: "pointer", width: "100%" }}>
            Sign out
          </button>
        </div>
      </div>

      {/* ── Main content ── */}
      <div style={{ flex: 1, minWidth: 0, overflowY: "auto" }}>
        {tab === "dashboard"     && <Dashboard />}
        {tab === "audit"         && <AuditLog />}
        {tab === "settings"      && <Settings user={user} />}
        {tab === "users"         && <Users />}
        {tab === "notifications" && <div style={{ padding: "1.5rem" }}><NotificationSettings /></div>}
        {tab === "dr-templates"  && <div style={{ padding: "1.5rem" }}><DRTemplates /></div>}
        {tab === "restores"      && <RestoresTab servers={servers} />}
        {tab === "servers"       && <ServersTab  servers={servers} setServers={setServers} setJobs={setJobs} api={api} canWrite={can(user,"write")} onRestore={(id, name) => setRestoreTarget({ serverId: id, serverName: name })} />}
        {tab === "backups"       && <BackupsTab  backups={backups} servers={servers} setBackups={setBackups} api={api} canWrite={can(user,"write")} />}
        {tab === "jobs"          && <JobsTab     jobs={jobs} servers={servers} setJobs={setJobs} api={api} canWrite={can(user,"write")} />}

        {restoreTarget && (
          <RestoreWizard
            serverId={restoreTarget.serverId}
            serverName={restoreTarget.serverName}
            onClose={() => setRestoreTarget(null)}
          />
        )}
      </div>
    </div>
  );
}

function ReadOnlyBanner() {
  return (
    <div style={{ background: "#1c1917", border: "1px solid #44403c", borderRadius: 8,
      padding: "10px 16px", marginBottom: 16, color: "#a8a29e", fontSize: 13,
      display: "flex", alignItems: "center", gap: 8 }}>
      👁 <strong>View-only mode</strong> — your account has viewer access. Contact an admin to make changes.
    </div>
  );
}

// ─── Restores Tab ─────────────────────────────────────────────────────────────
function RestoresTab({ servers }) {
  const [restores,      setRestores]      = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [showWizard,    setShowWizard]    = useState(false);
  const [selectedServer, setSelectedServer] = useState("");

  const load = () => {
    setLoading(true);
    import("./api").then(({ restoresApi }) =>
      restoresApi.list()
        .then(r => setRestores(r.data))
        .catch(console.error)
        .finally(() => setLoading(false))
    );
  };

  useEffect(() => { load(); }, []);

  const statusColor = { pending: "#f59e0b", running: "#3b82f6", completed: "#22c55e", failed: "#ef4444", cancelled: "#64748b" };

  return (
    <div style={{ padding: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>🔄 Restore Operations</h2>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select value={selectedServer} onChange={e => setSelectedServer(e.target.value)}
            style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 6,
              padding: "6px 10px", color: "#f1f5f9", fontSize: 13 }}>
            <option value="">Select server...</option>
            {servers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <button disabled={!selectedServer} onClick={() => setShowWizard(true)}
            style={{ background: selectedServer ? "#3b82f6" : "#334155", color: "#fff", border: "none",
              borderRadius: 6, padding: "8px 16px", cursor: selectedServer ? "pointer" : "not-allowed",
              fontSize: 13, fontWeight: 600 }}>
            + New Restore
          </button>
        </div>
      </div>

      {loading ? <p style={{ color: "#64748b" }}>Loading...</p> :
       restores.length === 0 ? (
        <div style={{ background: "#1e293b", borderRadius: 10, padding: "2rem", textAlign: "center", color: "#64748b", border: "1px solid #334155" }}>
          No restore operations yet.
        </div>
       ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}>
              {["ID","Server","Job","Status","Restore Path","Started","Completed"].map(h => (
                <th key={h} style={{ textAlign: "left", padding: "8px 12px", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {restores.map(r => (
              <tr key={r.id} style={{ borderBottom: "1px solid #1e293b" }}>
                <td style={{ padding: "10px 12px", color: "#64748b" }}>#{r.id}</td>
                <td style={{ padding: "10px 12px" }}>{servers.find(s => s.id === r.server_id)?.name || `Server ${r.server_id}`}</td>
                <td style={{ padding: "10px 12px", color: "#64748b" }}>{r.job_id ? `#${r.job_id}` : "Latest"}</td>
                <td style={{ padding: "10px 12px" }}>
                  <span style={{ color: statusColor[r.restore_status] || "#f1f5f9", fontWeight: 700, textTransform: "uppercase", fontSize: 12 }}>
                    {r.restore_status}
                  </span>
                </td>
                <td style={{ padding: "10px 12px", color: "#64748b" }}>{r.restore_path || "—"}</td>
                <td style={{ padding: "10px 12px", color: "#64748b" }}>{r.started_at ? new Date(r.started_at).toLocaleString() : "—"}</td>
                <td style={{ padding: "10px 12px", color: "#64748b" }}>{r.completed_at ? new Date(r.completed_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
       )}

      {showWizard && selectedServer && (
        <RestoreWizard
          serverId={parseInt(selectedServer)}
          serverName={servers.find(s => s.id === parseInt(selectedServer))?.name || "Server"}
          onClose={() => { setShowWizard(false); load(); }}
        />
      )}
    </div>
  );
}

// ─── Servers Tab (+ Trigger Backup + Restore button) ─────────────────────────
function ServersTab({ servers, setServers, setJobs, api, canWrite, onRestore }) {
  const [form, setForm] = useState({ name:"", hostname:"", port:22, username:"", description:"" });
  const [editId,     setEditId]     = useState(null);
  const [msg,        setMsg]        = useState("");
  const [subStatus,  setSubStatus]  = useState({});
  const [checking,   setChecking]   = useState({});
  const [triggering, setTriggering] = useState({});

  useEffect(() => {
    servers.forEach(s => {
      if (s.subscription_status) {
        setSubStatus(prev => ({ ...prev, [s.id]: {
          status: s.subscription_status,
          message: s.subscription_message,
          last_checked: s.subscription_last_checked
        }}));
      }
    });
  }, [servers]);

  const triggerBackup = async (server) => {
    setTriggering(prev => ({ ...prev, [server.id]: true }));
    try {
      const r = await api.post("/jobs/trigger", { server_id: server.id });
      setJobs(prev => [r.data, ...prev]);
      setMsg(`✓ Backup triggered on ${server.name}`);
      setTimeout(() => setMsg(""), 4000);
    } catch(e) {
      setMsg("✗ " + (e.response?.data?.detail || "Trigger failed"));
    }
    setTriggering(prev => ({ ...prev, [server.id]: false }));
  };

  const checkSubscription = async (serverId) => {
    setChecking(prev => ({ ...prev, [serverId]: true }));
    try {
      const r = await api.get(`/servers/${serverId}/check-subscription`);
      setSubStatus(prev => ({ ...prev, [serverId]: r.data }));
    } catch(e) {
      setSubStatus(prev => ({ ...prev, [serverId]: { status: "error", message: "Check failed" } }));
    }
    setChecking(prev => ({ ...prev, [serverId]: false }));
  };

  const saveServer = async (e) => {
    e.preventDefault();
    try {
      if (editId) {
        const r = await api.put(`/servers/${editId}`, form);
        setServers(prev => prev.map(s => s.id === editId ? r.data : s));
        setMsg("✓ Server updated");
      } else {
        const r = await api.post("/servers/", form);
        setServers(prev => [...prev, r.data]);
        setMsg("✓ Server added");
      }
      setForm({ name:"", hostname:"", port:22, username:"", description:"" });
      setEditId(null);
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Error")); }
  };

  const editServer = (server) => {
    setEditId(server.id);
    setForm({ name: server.name, hostname: server.hostname, port: server.port,
              username: server.username, description: server.description || "" });
  };

  const deleteServer = async (id) => {
    if (!confirm("Delete this server? All backup configs and jobs will also be deleted.")) return;
    try {
      await api.delete(`/servers/${id}`);
      setServers(prev => prev.filter(s => s.id !== id));
      setMsg("✓ Server deleted");
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Error")); }
  };

  const inputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13, width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ padding: "1.5rem" }}>
      <h2 style={{ margin: "0 0 1rem" }}>Servers</h2>
      {!canWrite && <ReadOnlyBanner />}
      {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", marginBottom: 12 }}>{msg}</div>}
      {canWrite && (
        <form onSubmit={saveServer} style={{ display:"flex", gap:8, flexWrap:"wrap", marginBottom:20, alignItems:"flex-end" }}>
          {[["Name","name","text"],["Hostname","hostname","text"],["Port","port","number"],
            ["Username","username","text"],["Description","description","text"]].map(([label,field,type]) => (
            <div key={field} style={{ flex: field === "description" ? 2 : 1, minWidth: 120 }}>
              <div style={{ color:"#64748b", fontSize:12, marginBottom:4 }}>{label}</div>
              <input type={type} value={form[field]} required={field !== "description"}
                onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))} style={inputStyle} />
            </div>
          ))}
          <button type="submit" style={{ background:"#3b82f6", color:"#fff", border:"none",
            borderRadius:6, padding:"7px 16px", cursor:"pointer", whiteSpace:"nowrap" }}>
            {editId ? "💾 Update" : "+ Add Server"}
          </button>
          {editId && (
            <button type="button" onClick={() => { setEditId(null); setForm({ name:"", hostname:"", port:22, username:"", description:"" }); }}
              style={{ background:"#334155", color:"#94a3b8", border:"none", borderRadius:6, padding:"7px 16px", cursor:"pointer" }}>
              Cancel
            </button>
          )}
        </form>
      )}
      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
        <thead><tr style={{ color:"#64748b", borderBottom:"1px solid #334155" }}>
          {["Name","Hostname","Port","Username","Status","Subscription", canWrite ? "Actions" : null].filter(Boolean).map(h => (
            <th key={h} style={{ textAlign:"left", padding:"8px 12px", fontWeight:600 }}>{h}</th>
          ))}
        </tr></thead>
        <tbody>
          {servers.map(s => {
            const sub = subStatus[s.id];
            return (
              <tr key={s.id} style={{ borderBottom:"1px solid #1e293b", background: editId === s.id ? "#1e293b" : "transparent" }}>
                <td style={{ padding:"10px 12px" }}>{s.name}</td>
                <td style={{ padding:"10px 12px", color:"#64748b", fontFamily:"monospace" }}>{s.hostname}</td>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>{s.port}</td>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>{s.username}</td>
                <td style={{ padding:"10px 12px" }}>
                  <span style={{ color: s.is_active ? "#4ade80" : "#f87171" }}>
                    {s.is_active ? "● Active" : "● Inactive"}
                  </span>
                </td>
                <td style={{ padding:"10px 12px" }}>
                  {checking[s.id] ? (
                    <span style={{ color:"#94a3b8" }}>Checking...</span>
                  ) : sub ? (
                    <span style={{ color: sub.status === "active" ? "#4ade80" : "#f87171" }} title={sub.message}>
                      {sub.status === "active" ? "✓ Active" :
                       sub.status === "not_installed" ? "✗ Not Installed" :
                       sub.status === "error" ? "✗ Error" : "✗ Inactive"}
                    </span>
                  ) : (
                    <button onClick={() => checkSubscription(s.id)}
                      style={{ background:"#334155", color:"#94a3b8", border:"none",
                        borderRadius:4, padding:"2px 8px", cursor:"pointer", fontSize:11 }}>
                      Check
                    </button>
                  )}
                </td>
                {canWrite && (
                  <td style={{ padding:"10px 12px" }}>
                    <div style={{ display:"flex", gap:6 }}>
                      <button onClick={() => triggerBackup(s)} disabled={!!triggering[s.id]}
                        style={{ background: triggering[s.id] ? "#334155" : "#065f46",
                          color: triggering[s.id] ? "#64748b" : "#6ee7b7",
                          border:"none", borderRadius:4, padding:"3px 10px",
                          cursor: triggering[s.id] ? "not-allowed" : "pointer", fontSize:12 }}>
                        {triggering[s.id] ? "⟳ Running..." : "▶ Backup"}
                      </button>
                      <button onClick={() => onRestore(s.id, s.name)} style={{ background:"#6d28d9",
                        color:"#ddd6fe", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>🔄 Restore</button>
                      <button onClick={() => editServer(s)} style={{ background:"#1e40af",
                        color:"#93c5fd", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>Edit</button>
                      <button onClick={() => deleteServer(s.id)} style={{ background:"#7f1d1d",
                        color:"#fca5a5", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>Delete</button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Backups Tab (original) ───────────────────────────────────────────────────
function BackupsTab({ backups, servers, setBackups, api, canWrite }) {
  const [form, setForm] = useState({ server_id:"", schedule:"*-*-* 01:00:00", retention_count:10,
    s3_mount_dir:"/mnt/idm-backup", backup_dir:"/var/lib/ipa/backup" });
  const [editId, setEditId] = useState(null);
  const [msg, setMsg] = useState("");

  const saveBackup = async (e) => {
    e.preventDefault();
    try {
      const data = { ...form, server_id: Number(form.server_id), retention_count: Number(form.retention_count) };
      if (editId) {
        const r = await api.put(`/backups/${editId}`, data);
        setBackups(prev => prev.map(b => b.id === editId ? r.data : b));
        const ds = r.data.deploy_status;
        if (ds === "deployed")       setMsg("✓ Config updated and deployed to server");
        else if (ds === "skipped")   setMsg("✓ Config updated (server inactive or config disabled — skipped deploy)");
        else                         setMsg(`✓ Config updated — deploy: ${ds}`);
      } else {
        const r = await api.post("/backups/", data);
        setBackups(prev => [...prev, r.data]);
        setMsg("✓ Config created");
      }
      setForm({ server_id:"", schedule:"*-*-* 01:00:00", retention_count:10,
        s3_mount_dir:"/mnt/idm-backup", backup_dir:"/var/lib/ipa/backup" });
      setEditId(null);
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Error")); }
  };

  const editBackup = (backup) => {
    setEditId(backup.id);
    setForm({ server_id: backup.server_id, schedule: backup.schedule, retention_count: backup.retention_count,
      s3_mount_dir: backup.s3_mount_dir, backup_dir: backup.backup_dir });
  };

  const deleteBackup = async (id) => {
    if (!confirm("Delete this backup config?")) return;
    try {
      await api.delete(`/backups/${id}`);
      setBackups(prev => prev.filter(b => b.id !== id));
      setMsg("✓ Config deleted");
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Error")); }
  };

  const deploy = async (id) => {
    try {
      const r = await api.post(`/backups/${id}/deploy`);
      setMsg("✓ " + r.data.message);
      setTimeout(() => setMsg(""), 5000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Deploy failed")); }
  };

  const inputStyle = { background:"#0f172a", color:"#f1f5f9", border:"1px solid #334155",
    borderRadius:6, padding:"7px 10px", fontSize:13, width:"100%", boxSizing:"border-box" };

  return (
    <div style={{ padding:"1.5rem" }}>
      <h2 style={{ margin:"0 0 1rem" }}>Backup Configurations</h2>
      {!canWrite && <ReadOnlyBanner />}
      {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", marginBottom:12 }}>{msg}</div>}
      {canWrite && (
        <form onSubmit={saveBackup} style={{ display:"flex", gap:8, flexWrap:"wrap", marginBottom:20, alignItems:"flex-end" }}>
          <div style={{ minWidth:160 }}>
            <div style={{ color:"#64748b", fontSize:12, marginBottom:4 }}>Server</div>
            <select value={form.server_id} required disabled={!!editId}
              onChange={e => setForm(p => ({ ...p, server_id:e.target.value }))} style={inputStyle}>
              <option value="">Select server</option>
              {servers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          {[["Schedule","schedule"],["Retention","retention_count"],
            ["S3 Mount","s3_mount_dir"],["Backup Dir","backup_dir"]].map(([label,field]) => (
            <div key={field} style={{ flex:1, minWidth:120 }}>
              <div style={{ color:"#64748b", fontSize:12, marginBottom:4 }}>{label}</div>
              <input value={form[field]} onChange={e => setForm(p => ({ ...p, [field]:e.target.value }))} style={inputStyle} />
            </div>
          ))}
          <button type="submit" style={{ background:"#3b82f6", color:"#fff", border:"none",
            borderRadius:6, padding:"7px 16px", cursor:"pointer" }}>
            {editId ? "💾 Update" : "+ Add Config"}
          </button>
          {editId && (
            <button type="button" onClick={() => { setEditId(null); setForm({ server_id:"", schedule:"*-*-* 01:00:00", retention_count:10, s3_mount_dir:"/mnt/idm-backup", backup_dir:"/var/lib/ipa/backup" }); }}
              style={{ background:"#334155", color:"#94a3b8", border:"none", borderRadius:6, padding:"7px 16px", cursor:"pointer" }}>
              Cancel
            </button>
          )}
        </form>
      )}
      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
        <thead><tr style={{ color:"#64748b", borderBottom:"1px solid #334155" }}>
          {["Server","Schedule","Retention","Status", canWrite ? "Actions" : null].filter(Boolean).map(h => (
            <th key={h} style={{ textAlign:"left", padding:"8px 12px", fontWeight:600 }}>{h}</th>
          ))}
        </tr></thead>
        <tbody>
          {backups.map(b => {
            const server = servers.find(s => s.id === b.server_id);
            return (
              <tr key={b.id} style={{ borderBottom:"1px solid #1e293b", background: editId === b.id ? "#1e293b" : "transparent" }}>
                <td style={{ padding:"10px 12px" }}>{server?.name || b.server_id}</td>
                <td style={{ padding:"10px 12px", fontFamily:"monospace", color:"#64748b" }}>{b.schedule}</td>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>{b.retention_count} backups</td>
                <td style={{ padding:"10px 12px" }}>
                  <span style={{ color: b.is_enabled ? "#4ade80" : "#f87171" }}>
                    {b.is_enabled ? "● Enabled" : "● Disabled"}
                  </span>
                </td>
                {canWrite && (
                  <td style={{ padding:"10px 12px" }}>
                    <div style={{ display:"flex", gap:6 }}>
                      <button onClick={() => deploy(b.id)} style={{ background:"#065f46",
                        color:"#6ee7b7", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>Deploy</button>
                      <button onClick={() => editBackup(b)} style={{ background:"#1e40af",
                        color:"#93c5fd", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>Edit</button>
                      <button onClick={() => deleteBackup(b.id)} style={{ background:"#7f1d1d",
                        color:"#fca5a5", border:"none", borderRadius:4, padding:"3px 10px",
                        cursor:"pointer", fontSize:12 }}>Delete</button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
// Ensure ISO timestamps are treated as UTC before converting to local time
const fmtDate = (iso) => {
  if (!iso) return "-";
  const s = iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z";
  return new Date(s).toLocaleString();
};

// ─── Jobs Tab ────────────────────────────────────────────────────────────────
function JobsTab({ jobs, servers, setJobs, api, canWrite }) {
  const [msg, setMsg]         = useState("");
  const [syncing, setSyncing] = useState(false);

  const deleteJob = async (id) => {
    if (!confirm("Delete this job record?")) return;
    try {
      await api.delete(`/jobs/${id}`);
      setJobs(prev => prev.filter(j => j.id !== id));
      setMsg("✓ Job deleted");
      setTimeout(() => setMsg(""), 3000);
    } catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Error")); }
  };

  const syncJobs = async () => {
    setSyncing(true);
    setMsg("");
    try {
      const r = await api.post("/jobs/sync");
      // Refresh the full list so newly-imported jobs appear
      const list = await api.get("/jobs/");
      setJobs(list.data);
      const n = r.data.synced;
      const errs = r.data.errors || [];
      let m = n > 0 ? `✓ Synced ${n} new job${n === 1 ? "" : "s"} from server journals` : "✓ No new jobs found";
      if (errs.length) m += ` (${errs.length} server${errs.length > 1 ? "s" : ""} unreachable)`;
      setMsg(m);
      setTimeout(() => setMsg(""), 5000);
    } catch(e) {
      setMsg("✗ Sync failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setSyncing(false);
    }
  };

  const STATUS_COLOR = { SUCCESS:"#4ade80", FAILED:"#f87171", RUNNING:"#fbbf24", PENDING:"#94a3b8" };

  return (
    <div style={{ padding:"1.5rem" }}>
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:"1rem" }}>
        <h2 style={{ margin:0 }}>Backup Jobs</h2>
        <button onClick={syncJobs} disabled={syncing}
          style={{ background:"#1e3a5f", color:"#93c5fd", border:"1px solid #3b82f6",
            borderRadius:6, padding:"5px 14px", cursor: syncing ? "not-allowed" : "pointer",
            fontSize:13, opacity: syncing ? 0.7 : 1 }}>
          {syncing ? "Syncing…" : "Sync from servers"}
        </button>
      </div>
      {!canWrite && <ReadOnlyBanner />}
      {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", marginBottom:12 }}>{msg}</div>}
      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
        <thead><tr style={{ color:"#64748b", borderBottom:"1px solid #334155" }}>
          {["ID","Server","Status","Started","Completed","Error", canWrite ? "Actions" : null].filter(Boolean).map(h => (
            <th key={h} style={{ textAlign:"left", padding:"8px 12px", fontWeight:600 }}>{h}</th>
          ))}
        </tr></thead>
        <tbody>
          {jobs.map(j => {
            const server = servers.find(s => s.id === j.server_id);
            return (
              <tr key={j.id} style={{ borderBottom:"1px solid #1e293b" }}>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>#{j.id}</td>
                <td style={{ padding:"10px 12px" }}>{server?.name || j.server_id}</td>
                <td style={{ padding:"10px 12px" }}>
                  <span style={{ color: STATUS_COLOR[j.status?.toUpperCase()] || "#94a3b8", fontWeight:600 }}>
                    {j.status?.toUpperCase()}
                  </span>
                </td>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>{fmtDate(j.started_at)}</td>
                <td style={{ padding:"10px 12px", color:"#64748b" }}>{fmtDate(j.completed_at)}</td>
                <td style={{ padding:"10px 12px", color:"#f87171", maxWidth:200 }}>
                  <span title={j.error_message} style={{ overflow:"hidden", textOverflow:"ellipsis",
                    whiteSpace:"nowrap", display:"block" }}>{j.error_message || "-"}</span>
                </td>
                {canWrite && (
                  <td style={{ padding:"10px 12px" }}>
                    <button onClick={() => deleteJob(j.id)} style={{ background:"#7f1d1d",
                      color:"#fca5a5", border:"none", borderRadius:4, padding:"3px 10px",
                      cursor:"pointer", fontSize:12 }}>Delete</button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
