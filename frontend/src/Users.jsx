import { useState, useEffect } from "react";
import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000/api/v1" });
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

const ROLES       = ["admin", "editor", "viewer"];
const ROLE_COLORS = { admin: "#fbbf24", editor: "#60a5fa", viewer: "#94a3b8" };
const ROLE_ICONS  = { admin: "★", editor: "✎", viewer: "👁" };

function UserFormModal({ user, onSave, onClose }) {
  const isEdit = !!user;
  const [form, setForm] = useState({
    username:  user?.username  || "",
    email:     user?.email     || "",
    full_name: user?.full_name || "",
    role:      user?.role      || "viewer",
    password:  "",
    requires_password_change: user?.requires_password_change || false,
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState("");

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSubmit = async () => {
    if (!form.username || !form.email) { setError("Username and email are required"); return; }
    if (!isEdit && !form.password)     { setError("Password is required for new users"); return; }
    setSaving(true); setError("");
    try { await onSave(form); }
    catch(e) { setError(e.response?.data?.detail || "Save failed"); }
    finally { setSaving(false); }
  };

  const inputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "8px 10px", fontSize: 13, width: "100%", boxSizing: "border-box" };
  const labelStyle = { color: "#64748b", fontSize: 12, marginBottom: 4, display: "block" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div style={{ background: "#1e293b", borderRadius: 12, padding: "1.75rem",
        width: 520, boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
        <h3 style={{ margin: "0 0 1.25rem", fontSize: 16, fontWeight: 700 }}>
          {isEdit ? `Edit User — ${user.username}` : "Create New User"}
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>Username *</label>
            <input value={form.username} onChange={e => set("username", e.target.value)}
              disabled={isEdit} style={{ ...inputStyle, opacity: isEdit ? 0.5 : 1 }} placeholder="jdoe" />
          </div>
          <div>
            <label style={labelStyle}>Email *</label>
            <input value={form.email} onChange={e => set("email", e.target.value)}
              style={inputStyle} placeholder="jdoe@company.com" />
          </div>
          <div>
            <label style={labelStyle}>Full Name</label>
            <input value={form.full_name} onChange={e => set("full_name", e.target.value)}
              style={inputStyle} placeholder="John Doe" />
          </div>
          <div>
            <label style={labelStyle}>Role</label>
            <select value={form.role} onChange={e => set("role", e.target.value)} style={inputStyle}>
              {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
            </select>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={labelStyle}>{isEdit ? "New Password (leave blank to keep current)" : "Password *"}</label>
            <input type="password" value={form.password} onChange={e => set("password", e.target.value)}
              style={inputStyle} placeholder={isEdit ? "Leave blank to keep unchanged" : "Min 8 characters"} />
          </div>
          <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 8, 
            background: "#0f172a", borderRadius: 6, padding: "10px 12px" }}>
            <input type="checkbox" id="requirePwdChange"
              checked={form.requires_password_change}
              onChange={e => set("requires_password_change", e.target.checked)}
              style={{ cursor: "pointer" }} />
            <label htmlFor="requirePwdChange" style={{ color: "#94a3b8", fontSize: 13, cursor: "pointer", flex: 1 }}>
              🔒 Require password change on next login
            </label>
          </div>
        </div>
        <div style={{ background: "#0f172a", borderRadius: 8, padding: "10px 14px",
          marginBottom: 16, fontSize: 12 }}>
          {form.role === "admin"  && <span style={{ color: "#fbbf24" }}>★ <strong>Admin</strong> — Full access: user management, settings, all operations</span>}
          {form.role === "editor" && <span style={{ color: "#60a5fa" }}>✎ <strong>Editor</strong> — Configure backups, servers, trigger jobs. No user management.</span>}
          {form.role === "viewer" && <span style={{ color: "#94a3b8" }}>👁 <strong>Viewer</strong> — Read-only. Cannot make changes.</span>}
        </div>
        {error && <div style={{ color: "#f87171", fontSize: 13, marginBottom: 12 }}>{error}</div>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{ background: "#334155", color: "#94a3b8", border: "none",
            borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 13 }}>Cancel</button>
          <button onClick={handleSubmit} disabled={saving}
            style={{ background: "#3b82f6", color: "#fff", border: "none",
              borderRadius: 6, padding: "8px 20px", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
            {saving ? "Saving..." : isEdit ? "Save Changes" : "Create User"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ResetPasswordModal({ user, onClose }) {
  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [requireChange, setRequireChange] = useState(true);
  const [saving,   setSaving]   = useState(false);
  const [done,     setDone]     = useState(false);
  const [error,    setError]    = useState("");

  const handleReset = async () => {
    if (password.length < 8)  { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm)  { setError("Passwords do not match"); return; }
    setSaving(true); setError("");
    try {
      await api.patch(`/auth/users/${user.id}`, { 
        password,
        requires_password_change: requireChange
      });
      setDone(true);
    } catch(e) {
      setError(e.response?.data?.detail || "Reset failed");
    } finally { setSaving(false); }
  };

  const inputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "8px 10px", fontSize: 13, width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div style={{ background: "#1e293b", borderRadius: 12, padding: "1.75rem",
        width: 380, boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
        <h3 style={{ margin: "0 0 1.25rem", fontSize: 16, fontWeight: 700 }}>
          Reset Password — {user.username}
        </h3>
        {done ? (
          <>
            <div style={{ color: "#4ade80", fontSize: 14, marginBottom: 16 }}>
              ✓ Password reset successfully.
              {requireChange && <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 6 }}>User will be required to change password on next login.</div>}
            </div>
            <button onClick={onClose} style={{ background: "#334155", color: "#94a3b8", border: "none",
              borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 13 }}>Close</button>
          </>
        ) : (
          <>
            <div style={{ marginBottom: 10 }}>
              <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>New Password</div>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                style={inputStyle} placeholder="Min 8 characters" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>Confirm Password</div>
              <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
                style={inputStyle} placeholder="Repeat password" />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, 
              background: "#0f172a", borderRadius: 6, padding: "10px 12px", marginBottom: 16 }}>
              <input type="checkbox" id="requireChangeReset"
                checked={requireChange}
                onChange={e => setRequireChange(e.target.checked)}
                style={{ cursor: "pointer" }} />
              <label htmlFor="requireChangeReset" style={{ color: "#94a3b8", fontSize: 12, cursor: "pointer" }}>
                Require password change on next login
              </label>
            </div>
            {error && <div style={{ color: "#f87171", fontSize: 13, marginBottom: 12 }}>{error}</div>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={onClose} style={{ background: "#334155", color: "#94a3b8", border: "none",
                borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 13 }}>Cancel</button>
              <button onClick={handleReset} disabled={saving}
                style={{ background: "#dc2626", color: "#fff", border: "none",
                  borderRadius: 6, padding: "8px 20px", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
                {saving ? "Resetting..." : "Reset Password"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function Users() {
  const [users,       setUsers]       = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [modal,       setModal]       = useState(null);
  const [resetTarget, setResetTarget] = useState(null);
  const [msg,         setMsg]         = useState("");

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = async () => {
    setLoading(true);
    try { const r = await api.get("/auth/users"); setUsers(r.data); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 3500); };

  const handleCreate = async (form) => {
    const r = await api.post("/auth/users", {
      username: form.username,
      email: form.email,
      full_name: form.full_name,
      role: form.role,
      password: form.password,
      requires_password_change: form.requires_password_change
    });
    setUsers(p => [r.data, ...p]);
    setModal(null);
    flash("✓ User created");
  };

  const handleEdit = async (form) => {
    const body = { full_name: form.full_name, role: form.role };
    if (form.password) body.password = form.password;
    body.requires_password_change = form.requires_password_change;
    
    const r = await api.patch(`/auth/users/${modal.user.id}`, body);
    setUsers(p => p.map(u => u.id === modal.user.id ? r.data : u));
    setModal(null);
    flash("✓ User updated");
  };

  const toggleActive = async (user) => {
    const r = await api.patch(`/auth/users/${user.id}`, { is_active: !user.is_active });
    setUsers(p => p.map(u => u.id === user.id ? r.data : u));
    flash(`✓ User ${r.data.is_active ? "activated" : "deactivated"}`);
  };

  return (
    <div style={{ padding: "1.5rem", color: "#f1f5f9", maxWidth: 1100 }}>
      {modal === "create" && <UserFormModal onSave={handleCreate} onClose={() => setModal(null)} />}
      {modal?.type === "edit" && <UserFormModal user={modal.user} onSave={handleEdit} onClose={() => setModal(null)} />}
      {resetTarget && <ResetPasswordModal user={resetTarget} onClose={() => { setResetTarget(null); loadUsers(); }} />}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.5rem" }}>
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700 }}>👥 User Management</h2>
          <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>Create and manage local user accounts and roles</p>
        </div>
        <button onClick={() => setModal("create")} style={{ background: "#3b82f6", color: "#fff",
          border: "none", borderRadius: 6, padding: "8px 18px", cursor: "pointer",
          fontSize: 13, fontWeight: 600 }}>+ New User</button>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        {ROLES.map(r => (
          <div key={r} style={{ background: "#1e293b", borderRadius: 8, padding: "8px 14px",
            display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <span style={{ color: ROLE_COLORS[r], fontWeight: 700 }}>{ROLE_ICONS[r]}</span>
            <div>
              <div style={{ fontWeight: 600, color: ROLE_COLORS[r], textTransform: "capitalize" }}>{r}</div>
              <div style={{ color: "#475569" }}>
                {r === "admin" && "Full access"}
                {r === "editor" && "Configure, no user mgmt"}
                {r === "viewer" && "Read-only"}
              </div>
            </div>
          </div>
        ))}
      </div>

      {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", fontSize: 13, marginBottom: 12 }}>{msg}</div>}

      {loading ? (
        <div style={{ color: "#475569", padding: "2rem 0" }}>Loading users...</div>
      ) : (
        <div style={{ background: "#1e293b", borderRadius: 10, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ color: "#64748b", borderBottom: "1px solid #334155" }}>
                {["User","Role","Auth Method","Status","Last Login","Actions"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 16px", fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: "1px solid #0f172a" }}>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ fontWeight: 600 }}>{u.username}</div>
                    <div style={{ color: "#64748b", fontSize: 12 }}>{u.email}</div>
                    {u.full_name && <div style={{ color: "#475569", fontSize: 11 }}>{u.full_name}</div>}
                    {u.requires_password_change && (
                      <div style={{ color: "#fbbf24", fontSize: 11, marginTop: 2 }}>🔒 Password change required</div>
                    )}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{ color: ROLE_COLORS[u.role], fontWeight: 600, fontSize: 12,
                      background: "#0f172a", borderRadius: 4, padding: "2px 8px" }}>
                      {ROLE_ICONS[u.role]} {u.role}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>
                    {u.auth_method === "local" ? "🔑 Local" : "🌐 SSO"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{ color: u.is_active ? "#4ade80" : "#f87171", fontSize: 12, fontWeight: 600 }}>
                      {u.is_active ? "● Active" : "● Inactive"}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#64748b", fontSize: 12 }}>
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "Never"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button onClick={() => setModal({ type: "edit", user: u })}
                        style={{ background: "#334155", color: "#cbd5e1", border: "none",
                          borderRadius: 5, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}>Edit</button>
                      {u.auth_method === "local" && (
                        <button onClick={() => setResetTarget(u)}
                          style={{ background: "#1e40af", color: "#93c5fd", border: "none",
                            borderRadius: 5, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}>Reset PW</button>
                      )}
                      <button onClick={() => toggleActive(u)}
                        style={{ background: u.is_active ? "#7f1d1d" : "#14532d",
                          color: u.is_active ? "#fca5a5" : "#86efac", border: "none",
                          borderRadius: 5, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}>
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <div style={{ padding: "2rem", color: "#475569", textAlign: "center" }}>No users found.</div>
          )}
        </div>
      )}
    </div>
  );
}
