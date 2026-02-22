import { useState, useEffect } from "react";
import { notificationsApi } from "./api";

const S = {
  card:  { background: "#1e293b", borderRadius: 10, padding: "1.5rem", marginBottom: 16, border: "1px solid #334155" },
  label: { color: "#94a3b8", fontSize: 12, marginBottom: 4, display: "block" },
  input: { width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
           padding: "8px 10px", color: "#f1f5f9", fontSize: 14, boxSizing: "border-box" },
  btn:   (color) => ({ background: color, color: "#fff", border: "none", borderRadius: 6,
           padding: "8px 16px", cursor: "pointer", fontSize: 13, fontWeight: 600 }),
  row:   { display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" },
};

export default function NotificationSettings() {
  const [settings, setSettings] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [form, setForm] = useState({
    notify_on_failure: true,
    notify_on_success: false,
    notify_threshold:  3,
    email_addresses:   "",
    slack_webhook_url: "",
    is_enabled:        true,
  });

  const load = () => {
    setLoading(true);
    notificationsApi.list()
      .then(r => setSettings(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const emails = form.email_addresses
        ? form.email_addresses.split(",").map(e => e.trim()).filter(Boolean)
        : [];
      await notificationsApi.create({
        ...form,
        email_addresses: emails,
        notify_threshold: parseInt(form.notify_threshold),
      });
      setShowForm(false);
      setForm({ notify_on_failure: true, notify_on_success: false,
                notify_threshold: 3, email_addresses: "", slack_webhook_url: "", is_enabled: true });
      load();
    } catch (e) {
      alert("Failed to save: " + (e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (ns) => {
    try {
      await notificationsApi.update(ns.id, { is_enabled: !ns.is_enabled });
      load();
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this notification setting?")) return;
    try { await notificationsApi.delete(id); load(); }
    catch (e) { alert("Delete failed"); }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, color: "#f1f5f9" }}>🔔 Notification Settings</h2>
        <button style={S.btn("#3b82f6")} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add Setting"}
        </button>
      </div>

      {showForm && (
        <div style={S.card}>
          <h3 style={{ margin: "0 0 16px", color: "#f1f5f9" }}>New Notification Setting</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label style={S.label}>Email Addresses (comma-separated)</label>
              <input style={S.input} value={form.email_addresses}
                onChange={e => setForm({ ...form, email_addresses: e.target.value })}
                placeholder="ops@example.com, admin@example.com" />
            </div>
            <div>
              <label style={S.label}>Slack Webhook URL</label>
              <input style={S.input} value={form.slack_webhook_url}
                onChange={e => setForm({ ...form, slack_webhook_url: e.target.value })}
                placeholder="https://hooks.slack.com/..." />
            </div>
            <div>
              <label style={S.label}>Failure Threshold (consecutive failures)</label>
              <input style={S.input} type="number" min={1} value={form.notify_threshold}
                onChange={e => setForm({ ...form, notify_threshold: e.target.value })} />
            </div>
          </div>
          <div style={{ ...S.row, marginBottom: 16 }}>
            {[["notify_on_failure","Alert on Failure"],["notify_on_success","Alert on Success"],["is_enabled","Enabled"]].map(([k, label]) => (
              <label key={k} style={{ display: "flex", alignItems: "center", gap: 6, color: "#cbd5e1", cursor: "pointer" }}>
                <input type="checkbox" checked={form[k]}
                  onChange={e => setForm({ ...form, [k]: e.target.checked })} />
                {label}
              </label>
            ))}
          </div>
          <button style={S.btn("#22c55e")} onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Setting"}
          </button>
        </div>
      )}

      {loading ? (
        <p style={{ color: "#64748b" }}>Loading...</p>
      ) : settings.length === 0 ? (
        <div style={{ ...S.card, textAlign: "center", color: "#64748b" }}>
          No notification settings configured. Add one to receive alerts.
        </div>
      ) : (
        settings.map(ns => (
          <div key={ns.id} style={{ ...S.card, opacity: ns.is_enabled ? 1 : 0.5 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <div style={{ ...S.row, marginBottom: 8 }}>
                  <span style={{ color: ns.is_enabled ? "#22c55e" : "#64748b", fontSize: 12, fontWeight: 700 }}>
                    {ns.is_enabled ? "● ENABLED" : "● DISABLED"}
                  </span>
                  {ns.notify_on_failure && <span style={{ background: "#7f1d1d", color: "#fca5a5", borderRadius: 4, padding: "2px 8px", fontSize: 11 }}>On Failure</span>}
                  {ns.notify_on_success && <span style={{ background: "#14532d", color: "#86efac", borderRadius: 4, padding: "2px 8px", fontSize: 11 }}>On Success</span>}
                  <span style={{ color: "#94a3b8", fontSize: 12 }}>Threshold: {ns.notify_threshold}</span>
                </div>
                {ns.email_addresses?.length > 0 && (
                  <div style={{ color: "#cbd5e1", fontSize: 13, marginBottom: 4 }}>
                    📧 {ns.email_addresses.join(", ")}
                  </div>
                )}
                {ns.slack_webhook_url && (
                  <div style={{ color: "#cbd5e1", fontSize: 13 }}>
                    💬 Slack webhook configured
                  </div>
                )}
              </div>
              <div style={S.row}>
                <button style={S.btn(ns.is_enabled ? "#64748b" : "#22c55e")} onClick={() => handleToggle(ns)}>
                  {ns.is_enabled ? "Disable" : "Enable"}
                </button>
                <button style={S.btn("#ef4444")} onClick={() => handleDelete(ns.id)}>Delete</button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
