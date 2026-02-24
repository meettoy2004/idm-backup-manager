import { useState, useEffect } from "react";
import axios from "axios";

const api = axios.create({ baseURL: `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1` });
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

const PROVIDER_TYPES = [
  { value: "oidc", label: "🔑 Keycloak OIDC" },
  { value: "ldap", label: "📂 LDAP / Active Directory" },
  { value: "saml", label: "🎫 SAML 2.0" },
];

const DEFAULT_CONFIGS = {
  oidc: { base_url: "", realm: "", client_id: "", client_secret: "", scope: "openid email profile", verify_ssl: true },
  ldap: { host: "", port: 389, use_ssl: false, bind_dn: "", bind_password: "", search_base: "", search_filter: "(uid={username})", attr_email: "mail", attr_name: "cn" },
  saml: { idp_entity_id: "", idp_sso_url: "", idp_slo_url: "", idp_cert: "", sp_entity_id: "", acs_url: "", sp_cert: "", sp_key: "" }
};

const FIELD_LABELS = {
  oidc: {
    base_url: ["Keycloak Base URL", "https://keycloak.example.com", false],
    realm: ["Realm", "master", false],
    client_id: ["Client ID", "idm-backup-manager", false],
    client_secret: ["Client Secret", "••••••••", true],
    scope: ["Scope", "openid email profile", false],
    verify_ssl: ["Verify SSL", null, false],
  },
  ldap: {
    host: ["LDAP Host", "ldap.example.com", false],
    port: ["Port", "389", false],
    use_ssl: ["Use SSL/TLS", null, false],
    bind_dn: ["Bind DN", "cn=service,dc=example,dc=com", false],
    bind_password: ["Bind Password", "••••••••", true],
    search_base: ["Search Base", "dc=example,dc=com", false],
    search_filter: ["Search Filter", "(uid={username})", false],
    attr_email: ["Email Attribute", "mail", false],
    attr_name: ["Name Attribute", "cn", false],
  },
  saml: {
    idp_entity_id: ["IdP Entity ID", "https://keycloak.example.com/realms/master", false],
    idp_sso_url: ["IdP SSO URL", "https://keycloak.example.com/realms/master/protocol/saml", false],
    idp_slo_url: ["IdP SLO URL", "", false],
    idp_cert: ["IdP Certificate (PEM)", "-----BEGIN CERTIFICATE-----\n...", false],
    sp_entity_id: ["SP Entity ID", "https://backup.example.com/api/v1/providers/1/saml/metadata", false],
    acs_url: ["ACS URL", "https://backup.example.com/api/v1/providers/1/saml/callback", false],
    sp_cert: ["SP Certificate (optional)", "", false],
    sp_key: ["SP Private Key (optional)", "", true],
  }
};

function ProviderForm({ provider, onSave, onCancel }) {
  const [name, setName]           = useState(provider?.name || "");
  const [type, setType]           = useState(provider?.type || "oidc");
  const [enabled, setEnabled]     = useState(provider?.is_enabled ?? true);
  const [config, setConfig]       = useState(provider?.config || DEFAULT_CONFIGS["oidc"]);
  const [saving, setSaving]       = useState(false);
  const [testing, setTesting]     = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [msg, setMsg]             = useState("");

  const handleTypeChange = (newType) => { setType(newType); if (!provider) setConfig(DEFAULT_CONFIGS[newType]); };
  const setField = (key, val) => setConfig(p => ({ ...p, [key]: val }));

  const handleSave = async () => {
    setSaving(true);
    try { await onSave({ name, type, is_enabled: enabled, config }); setMsg("✓ Saved"); }
    catch(e) { setMsg("✗ " + (e.response?.data?.detail || "Save failed")); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    if (!provider?.id) { setTestResult({ success: false, message: "Save first to test" }); return; }
    setTesting(true); setTestResult(null);
    try { const r = await api.post(`/providers/${provider.id}/test`); setTestResult(r.data); }
    catch(e) { setTestResult({ success: false, message: e.response?.data?.detail || "Test failed" }); }
    finally { setTesting(false); }
  };

  const fields = FIELD_LABELS[type] || {};
  const inputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13, width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ background: "#1e293b", borderRadius: 10, padding: "1.5rem", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "flex-end" }}>
        <div style={{ flex: 1 }}>
          <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>Provider Name</div>
          <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Company Keycloak" style={inputStyle} />
        </div>
        <div style={{ width: 220 }}>
          <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>Type</div>
          <select value={type} onChange={e => handleTypeChange(e.target.value)} style={inputStyle}>
            {PROVIDER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingBottom: 2 }}>
          <input type="checkbox" checked={enabled} onChange={e => setEnabled(e.target.checked)} id="enabled" style={{ cursor: "pointer" }} />
          <label htmlFor="enabled" style={{ color: "#94a3b8", fontSize: 13, cursor: "pointer" }}>Enabled</label>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
        {Object.entries(fields).map(([key, [label, placeholder, isSecret]]) => (
          <div key={key} style={{ gridColumn: key.includes("cert") || key.includes("key") || key.includes("filter") ? "1 / -1" : undefined }}>
            <div style={{ color: "#64748b", fontSize: 12, marginBottom: 4 }}>{label}</div>
            {typeof config[key] === "boolean" ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 0" }}>
                <input type="checkbox" checked={config[key]} onChange={e => setField(key, e.target.checked)} style={{ cursor: "pointer" }} />
                <span style={{ color: "#94a3b8", fontSize: 13 }}>{config[key] ? "Enabled" : "Disabled"}</span>
              </div>
            ) : key.includes("cert") || key.includes("key") || key.includes("filter") ? (
              <textarea value={config[key] || ""} onChange={e => setField(key, e.target.value)}
                placeholder={placeholder} rows={key.includes("cert") ? 5 : 2}
                style={{ ...inputStyle, fontFamily: "monospace", fontSize: 11, resize: "vertical" }} />
            ) : (
              <input type={isSecret ? "password" : "text"} value={config[key] ?? ""} placeholder={placeholder}
                onChange={e => setField(key, key === "port" ? Number(e.target.value) : e.target.value)}
                style={inputStyle} />
            )}
          </div>
        ))}
      </div>
      {testResult && (
        <div style={{ background: testResult.success ? "#052e16" : "#450a0a",
          color: testResult.success ? "#4ade80" : "#f87171",
          borderRadius: 6, padding: "8px 12px", marginBottom: 12, fontSize: 13 }}>
          {testResult.success ? "✓ " : "✗ "}{testResult.message}
        </div>
      )}
      {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", fontSize: 13, marginBottom: 8 }}>{msg}</div>}
      {type === "oidc" && provider?.id && (
        <div style={{ background: "#0f172a", borderRadius: 6, padding: "10px 14px", marginBottom: 12, fontSize: 12, color: "#64748b" }}>
          <strong style={{ color: "#94a3b8" }}>Keycloak Setup:</strong> Set Valid Redirect URIs to:{" "}
          <code style={{ color: "#60a5fa" }}>{window.location.origin}/api/v1/providers/{provider.id}/oidc/callback</code>
        </div>
      )}
      {type === "saml" && provider?.id && (
        <div style={{ background: "#0f172a", borderRadius: 6, padding: "10px 14px", marginBottom: 12, fontSize: 12, color: "#64748b" }}>
          <strong style={{ color: "#94a3b8" }}>SP Metadata URL:</strong>{" "}
          <a href={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/providers/${provider.id}/saml/metadata`}
            target="_blank" rel="noreferrer" style={{ color: "#60a5fa" }}>Download SP Metadata</a>
          {" "}— import this into Keycloak as a SAML client.
        </div>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={handleSave} disabled={saving} style={{ background: "#3b82f6", color: "#fff", border: "none",
          borderRadius: 6, padding: "7px 18px", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
          {saving ? "Saving..." : provider ? "Save Changes" : "Create Provider"}
        </button>
        {type === "ldap" && (
          <button onClick={handleTest} disabled={testing} style={{ background: "#1e40af", color: "#93c5fd",
            border: "none", borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13 }}>
            {testing ? "Testing..." : "🔌 Test Connection"}
          </button>
        )}
        {type === "oidc" && provider?.id && (
          <button onClick={handleTest} disabled={testing} style={{ background: "#1e40af", color: "#93c5fd",
            border: "none", borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13 }}>
            {testing ? "Testing..." : "🔌 Test Keycloak"}
          </button>
        )}
        <button onClick={onCancel} style={{ background: "#334155", color: "#94a3b8", border: "none",
          borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13 }}>Cancel</button>
      </div>
    </div>
  );
}

function SecurityPolicies() {
  const numInputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13, width: 90, textAlign: "center", boxSizing: "border-box" };
  const [sessionTimeout, setSessionTimeout]       = useState(30);
  const [sessionSaved, setSessionSaved]           = useState(false);
  const [unlockTime, setUnlockTime]               = useState(15);
  const [maxFailedLogins, setMaxFailedLogins]     = useState(5);
  const [resetCounterAfter, setResetCounterAfter] = useState(10);
  const [lockoutSaved, setLockoutSaved]           = useState(false);

  useEffect(() => {
    try {
      const p = JSON.parse(localStorage.getItem("securityPolicies") || "{}");
      if (p.sessionTimeout)    setSessionTimeout(p.sessionTimeout);
      if (p.unlockTime)        setUnlockTime(p.unlockTime);
      if (p.maxFailedLogins)   setMaxFailedLogins(p.maxFailedLogins);
      if (p.resetCounterAfter) setResetCounterAfter(p.resetCounterAfter);
    } catch(_) {}
  }, []);

  const saveSession = () => {
    const e = JSON.parse(localStorage.getItem("securityPolicies") || "{}");
    localStorage.setItem("securityPolicies", JSON.stringify({ ...e, sessionTimeout }));
    setSessionSaved(true); setTimeout(() => setSessionSaved(false), 2500);
  };
  const saveLockout = () => {
    const e = JSON.parse(localStorage.getItem("securityPolicies") || "{}");
    localStorage.setItem("securityPolicies", JSON.stringify({ ...e, unlockTime, maxFailedLogins, resetCounterAfter }));
    setLockoutSaved(true); setTimeout(() => setLockoutSaved(false), 2500);
  };

  const sectionStyle = { background: "#1e293b", borderRadius: 10, padding: "1.25rem 1.5rem", marginBottom: 20 };
  const labelStyle   = { color: "#64748b", fontSize: 12, marginBottom: 4, display: "block" };
  const rowStyle     = { display: "flex", alignItems: "center", gap: 10 };
  const unitStyle    = { color: "#64748b", fontSize: 13, whiteSpace: "nowrap" };
  const btnStyle     = { background: "#3b82f6", color: "#fff", border: "none",
    borderRadius: 6, padding: "7px 18px", cursor: "pointer", fontSize: 13, fontWeight: 600 };

  return (
    <>
      <div style={sectionStyle}>
        <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>⏱ Session Timeout</h3>
        <p style={{ margin: "0 0 1.25rem", color: "#64748b", fontSize: 12 }}>Log out if no operations are performed within the specified time.</p>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Inactivity timeout</label>
          <div style={rowStyle}>
            <input type="number" min={1} max={1440} value={sessionTimeout}
              onChange={e => setSessionTimeout(Number(e.target.value))} style={numInputStyle} />
            <span style={unitStyle}>minutes</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={saveSession} style={btnStyle}>Save</button>
          {sessionSaved && <span style={{ color: "#4ade80", fontSize: 13 }}>✓ Saved</span>}
        </div>
        <p style={{ margin: "12px 0 0", color: "#475569", fontSize: 11 }}>ℹ Takes effect at the next login.</p>
      </div>
      <div style={sectionStyle}>
        <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>🔒 Account Lockout</h3>
        <p style={{ margin: "0 0 1.25rem", color: "#64748b", fontSize: 12 }}>Temporarily lock accounts after repeated failed login attempts.</p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>Time until account is unlocked</label>
            <div style={rowStyle}>
              <input type="number" min={1} max={1440} value={unlockTime}
                onChange={e => setUnlockTime(Number(e.target.value))} style={numInputStyle} />
              <span style={unitStyle}>min</span>
            </div>
          </div>
          <div>
            <label style={labelStyle}>Number of failed logins before account is locked</label>
            <div style={rowStyle}>
              <input type="number" min={1} max={100} value={maxFailedLogins}
                onChange={e => setMaxFailedLogins(Number(e.target.value))} style={numInputStyle} />
              <span style={unitStyle}>attempts</span>
            </div>
          </div>
          <div>
            <label style={labelStyle}>Reset account lockout counter after</label>
            <div style={rowStyle}>
              <input type="number" min={1} max={1440} value={resetCounterAfter}
                onChange={e => setResetCounterAfter(Number(e.target.value))} style={numInputStyle} />
              <span style={unitStyle}>min</span>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={saveLockout} style={btnStyle}>Save</button>
          {lockoutSaved && <span style={{ color: "#4ade80", fontSize: 13 }}>✓ Saved</span>}
        </div>
      </div>
    </>
  );
}

function ChangePassword({ user }) {
  const [current,  setCurrent]  = useState("");
  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [saving,   setSaving]   = useState(false);
  const [msg,      setMsg]      = useState("");

  const handleSave = async () => {
    if (password.length < 8) { setMsg("✗ Password must be at least 8 characters"); return; }
    if (password !== confirm) { setMsg("✗ Passwords do not match"); return; }
    setSaving(true); setMsg("");
    try {
      await api.post("/auth/change-password", { current_password: current, new_password: password });
      setMsg("✓ Password changed successfully");
      setCurrent(""); setPassword(""); setConfirm("");
    } catch(e) {
      setMsg("✗ " + (e.response?.data?.detail || "Failed"));
    } finally { setSaving(false); }
  };

  const inputStyle = { background: "#0f172a", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "8px 10px", fontSize: 13, width: "100%", boxSizing: "border-box" };
  const labelStyle = { color: "#64748b", fontSize: 12, marginBottom: 4, display: "block" };

  if (user?.auth_method !== "local") {
    return (
      <div style={{ background: "#1e293b", borderRadius: 10, padding: "1.25rem 1.5rem", marginBottom: 20 }}>
        <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>🔑 Change Password</h3>
        <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
          Your account uses SSO. Password changes must be made through your identity provider.
        </p>
      </div>
    );
  }

  return (
    <div style={{ background: "#1e293b", borderRadius: 10, padding: "1.25rem 1.5rem", marginBottom: 20 }}>
      <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>🔑 Change Password</h3>
      <p style={{ margin: "0 0 1.25rem", color: "#64748b", fontSize: 12 }}>Update your local account password.</p>
      <div style={{ maxWidth: 360 }}>
        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>Current Password</label>
          <input type="password" value={current} onChange={e => setCurrent(e.target.value)}
            style={inputStyle} placeholder="Enter current password" />
        </div>
        <div style={{ marginBottom: 10 }}>
          <label style={labelStyle}>New Password</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)}
            style={inputStyle} placeholder="Min 8 characters" />
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>Confirm New Password</label>
          <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
            style={inputStyle} placeholder="Repeat new password" />
        </div>
        {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", fontSize: 13, marginBottom: 12 }}>{msg}</div>}
        <button onClick={handleSave} disabled={saving || !current || !password || !confirm}
          style={{ background: "#3b82f6", color: "#fff", border: "none", borderRadius: 6,
            padding: "8px 20px", cursor: "pointer", fontSize: 13, fontWeight: 600,
            opacity: (!current || !password || !confirm) ? 0.5 : 1 }}>
          {saving ? "Saving..." : "Change Password"}
        </button>
      </div>
    </div>
  );
}

export default function Settings({ user }) {
  const [providers, setProviders] = useState([]);
  const [editing,   setEditing]   = useState(null);
  const [msg,       setMsg]       = useState("");
  const isAdmin = user?.role === "admin";

  useEffect(() => { if (isAdmin) loadProviders(); }, [isAdmin]);

  const loadProviders = async () => {
    try { const r = await api.get("/providers/"); setProviders(r.data); }
    catch(e) { console.error(e); }
  };

  const handleSave = async (data) => {
    if (editing === "new") {
      const r = await api.post("/providers/", data);
      setProviders(p => [...p, r.data]);
    } else {
      const r = await api.put(`/providers/${editing}/`, data);
      setProviders(p => p.map(x => x.id === editing ? r.data : x));
    }
    setEditing(null); setMsg("✓ Provider saved"); setTimeout(() => setMsg(""), 3000);
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this provider?")) return;
    await api.delete(`/providers/${id}/`);
    setProviders(p => p.filter(x => x.id !== id));
    setMsg("Provider deleted"); setTimeout(() => setMsg(""), 3000);
  };

  const typeIcon  = { oidc: "🔑", ldap: "📂", saml: "🎫" };
  const typeLabel = { oidc: "Keycloak OIDC", ldap: "LDAP/AD", saml: "SAML 2.0" };

  return (
    <div style={{ padding: "1.5rem", color: "#f1f5f9", maxWidth: 900 }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700 }}>Settings</h2>
      <p style={{ margin: "0 0 1.5rem", color: "#64748b", fontSize: 13 }}>
        Configure authentication providers and system security policies
      </p>

      <ChangePassword user={user} />

      {isAdmin && (
        <>
          <div style={{ background: "#1e293b", borderRadius: 10, padding: "1.25rem 1.5rem", marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>Authentication Providers</h3>
                <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 12 }}>Configure Keycloak OIDC, LDAP/AD, or SAML 2.0 for single sign-on</p>
              </div>
              {editing !== "new" && (
                <button onClick={() => setEditing("new")} style={{ background: "#3b82f6", color: "#fff",
                  border: "none", borderRadius: 6, padding: "6px 14px", cursor: "pointer",
                  fontSize: 13, fontWeight: 600 }}>+ Add Provider</button>
              )}
            </div>
            {msg && <div style={{ color: msg.startsWith("✓") ? "#4ade80" : "#f87171", fontSize: 13, marginBottom: 12 }}>{msg}</div>}
            {editing === "new" && <ProviderForm onSave={handleSave} onCancel={() => setEditing(null)} />}
            {providers.length === 0 && editing !== "new" ? (
              <div style={{ color: "#475569", fontSize: 13, padding: "1rem 0" }}>No authentication providers configured. Add one to enable SSO.</div>
            ) : (
              providers.map(p => (
                <div key={p.id}>
                  {editing === p.id ? (
                    <ProviderForm provider={p} onSave={handleSave} onCancel={() => setEditing(null)} />
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderTop: "1px solid #334155" }}>
                      <span style={{ fontSize: 20 }}>{typeIcon[p.type]}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                        <div style={{ color: "#64748b", fontSize: 12 }}>
                          {typeLabel[p.type]}
                          {p.type === "oidc" && p.config.realm && ` · realm: ${p.config.realm}`}
                          {p.type === "ldap" && p.config.host && ` · ${p.config.host}:${p.config.port}`}
                        </div>
                      </div>
                      <span style={{ color: p.is_enabled ? "#4ade80" : "#f87171", fontSize: 12, fontWeight: 600 }}>
                        {p.is_enabled ? "● Enabled" : "● Disabled"}
                      </span>
                      <button onClick={() => setEditing(p.id)} style={{ background: "#334155", color: "#cbd5e1",
                        border: "none", borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 12 }}>Edit</button>
                      <button onClick={() => handleDelete(p.id)} style={{ background: "#7f1d1d", color: "#fca5a5",
                        border: "none", borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 12 }}>Delete</button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          <SecurityPolicies />

          <div style={{ background: "#1e293b", borderRadius: 10, padding: "1.25rem 1.5rem" }}>
            <h3 style={{ margin: "0 0 4px", fontSize: 15, fontWeight: 700 }}>Local Users</h3>
            <p style={{ margin: "0 0 12px", color: "#64748b", fontSize: 12 }}>Manage local user accounts from the Auth → Users API or use the admin panel</p>
            <a href=`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/docs#/auth` target="_blank" rel="noreferrer" style={{ color: "#60a5fa", fontSize: 13 }}>Open User Management API →</a>
          </div>
        </>
      )}
    </div>
  );
}
