import { useState, useEffect } from "react";
import { drTemplatesApi } from "./api";

const S = {
  card:  { background: "#1e293b", borderRadius: 10, padding: "1.5rem", marginBottom: 16, border: "1px solid #334155" },
  label: { color: "#94a3b8", fontSize: 12, marginBottom: 4, display: "block" },
  input: { width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
           padding: "8px 10px", color: "#f1f5f9", fontSize: 14, boxSizing: "border-box" },
  textarea: { width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
              padding: "8px 10px", color: "#f1f5f9", fontSize: 13, boxSizing: "border-box",
              fontFamily: "monospace", minHeight: 120, resize: "vertical" },
  btn:   (color) => ({ background: color, color: "#fff", border: "none", borderRadius: 6,
           padding: "8px 16px", cursor: "pointer", fontSize: 13, fontWeight: 600 }),
};

const DEFAULT_CONFIG = JSON.stringify({
  rto_hours: 4,
  rpo_hours: 24,
  steps: ["Verify latest backup integrity", "Provision restore target", "Decrypt and extract backup", "Validate restored data", "Update DNS / failover"],
  verification_required: true,
  notification_groups: []
}, null, 2);

export default function DRTemplates() {
  const [templates, setTemplates] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [showForm,  setShowForm]  = useState(false);
  const [expanded,  setExpanded]  = useState(null);
  const [saving,    setSaving]    = useState(false);
  const [form, setForm] = useState({ name: "", description: "", template_config: DEFAULT_CONFIG });

  const load = () => {
    setLoading(true);
    drTemplatesApi.list()
      .then(r => setTemplates(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    if (!form.name) { alert("Name is required"); return; }
    setSaving(true);
    try {
      let config = null;
      try { config = JSON.parse(form.template_config); } catch { alert("Invalid JSON in config"); setSaving(false); return; }
      await drTemplatesApi.create({ name: form.name, description: form.description, template_config: config });
      setShowForm(false);
      setForm({ name: "", description: "", template_config: DEFAULT_CONFIG });
      load();
    } catch (e) {
      alert("Failed to save: " + (e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!confirm(`Deactivate template "${name}"?`)) return;
    try { await drTemplatesApi.delete(id); load(); }
    catch (e) { alert("Failed to delete"); }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, color: "#f1f5f9" }}>🛡️ DR Templates</h2>
        <button style={S.btn("#3b82f6")} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ New Template"}
        </button>
      </div>

      {showForm && (
        <div style={S.card}>
          <h3 style={{ margin: "0 0 16px", color: "#f1f5f9" }}>New DR Template</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label style={S.label}>Template Name *</label>
              <input style={S.input} value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Full IdM Recovery" />
            </div>
            <div>
              <label style={S.label}>Description</label>
              <input style={S.input} value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <label style={S.label}>Template Config (JSON)</label>
            <textarea style={S.textarea} value={form.template_config}
              onChange={e => setForm({ ...form, template_config: e.target.value })} />
          </div>
          <button style={S.btn("#22c55e")} onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save Template"}
          </button>
        </div>
      )}

      {loading ? (
        <p style={{ color: "#64748b" }}>Loading...</p>
      ) : templates.length === 0 ? (
        <div style={{ ...S.card, textAlign: "center", color: "#64748b" }}>
          No DR templates yet. Create one to document your recovery runbook.
        </div>
      ) : (
        templates.map(t => (
          <div key={t.id} style={S.card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{ color: "#f1f5f9", fontWeight: 700, fontSize: 15 }}>{t.name}</span>
                  {t.template_config?.rto_hours && (
                    <span style={{ background: "#1e3a5f", color: "#93c5fd", borderRadius: 4, padding: "2px 8px", fontSize: 11 }}>
                      RTO {t.template_config.rto_hours}h
                    </span>
                  )}
                  {t.template_config?.rpo_hours && (
                    <span style={{ background: "#1e3a5f", color: "#93c5fd", borderRadius: 4, padding: "2px 8px", fontSize: 11 }}>
                      RPO {t.template_config.rpo_hours}h
                    </span>
                  )}
                </div>
                {t.description && <div style={{ color: "#94a3b8", fontSize: 13, marginBottom: 8 }}>{t.description}</div>}
                {t.template_config?.steps && (
                  <div>
                    <button style={{ background: "none", border: "none", color: "#3b82f6", cursor: "pointer", fontSize: 12, padding: 0 }}
                      onClick={() => setExpanded(expanded === t.id ? null : t.id)}>
                      {expanded === t.id ? "▾ Hide steps" : `▸ ${t.template_config.steps.length} recovery steps`}
                    </button>
                    {expanded === t.id && (
                      <ol style={{ marginTop: 8, paddingLeft: 20, color: "#cbd5e1", fontSize: 13 }}>
                        {t.template_config.steps.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
                      </ol>
                    )}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 8, marginLeft: 16 }}>
                <button style={S.btn("#ef4444")} onClick={() => handleDelete(t.id, t.name)}>Delete</button>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
