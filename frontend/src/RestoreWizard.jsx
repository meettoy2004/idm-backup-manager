import { useState, useEffect } from "react";
import { restoresApi, jobsApi } from "./api";

const S = {
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex",
             alignItems: "center", justifyContent: "center", zIndex: 1000 },
  modal:   { background: "#1e293b", borderRadius: 12, padding: "2rem", width: 540,
             maxHeight: "85vh", overflowY: "auto", border: "1px solid #334155" },
  label:   { color: "#94a3b8", fontSize: 12, marginBottom: 4, display: "block" },
  input:   { width: "100%", background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
             padding: "8px 10px", color: "#f1f5f9", fontSize: 14, boxSizing: "border-box" },
  btn:     (color) => ({ background: color, color: "#fff", border: "none", borderRadius: 6,
             padding: "8px 18px", cursor: "pointer", fontSize: 14, fontWeight: 600 }),
  step:    (active) => ({ display: "flex", alignItems: "center", gap: 8, color: active ? "#f1f5f9" : "#475569",
             fontWeight: active ? 700 : 400, fontSize: 13 }),
  stepNum: (active, done) => ({
    width: 24, height: 24, borderRadius: "50%", display: "flex", alignItems: "center",
    justifyContent: "center", fontSize: 12, fontWeight: 700, flexShrink: 0,
    background: done ? "#22c55e" : active ? "#3b82f6" : "#334155",
    color: "#fff",
  }),
};

const STEPS = ["Select Job", "Configure", "Confirm", "Running"];

export default function RestoreWizard({ serverId, serverName, onClose }) {
  const [step,       setStep]       = useState(0);
  const [jobs,       setJobs]       = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [restorePath, setRestorePath] = useState("/var/lib/ipa/restore");
  const [passphrase,  setPassphrase]  = useState("");
  const [restoreOp,   setRestoreOp]   = useState(null);
  const [polling,     setPolling]     = useState(false);
  const [error,       setError]       = useState("");

  useEffect(() => {
    jobsApi.list({ server_id: serverId, status: "SUCCESS" })
      .then(r => setJobs(r.data))
      .catch(console.error);
  }, [serverId]);

  // Poll restore status when running
  useEffect(() => {
    if (!restoreOp || !polling) return;
    const interval = setInterval(async () => {
      try {
        const r = await restoresApi.get(restoreOp.id);
        setRestoreOp(r.data);
        if (["completed", "failed"].includes(r.data.restore_status)) {
          setPolling(false);
        }
      } catch (e) { console.error(e); }
    }, 3000);
    return () => clearInterval(interval);
  }, [restoreOp, polling]);

  const handleStart = async () => {
    if (!passphrase) { setError("GPG passphrase is required"); return; }
    setError("");
    setStep(3);
    try {
      const r = await restoresApi.create({
        job_id:         selectedJob?.id || null,
        server_id:      serverId,
        restore_path:   restorePath,
        gpg_passphrase: passphrase,
      });
      setRestoreOp(r.data);
      setPolling(true);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  };

  const statusColor = {
    pending:   "#f59e0b",
    running:   "#3b82f6",
    completed: "#22c55e",
    failed:    "#ef4444",
    cancelled: "#64748b",
  };

  return (
    <div style={S.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={S.modal}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <h2 style={{ margin: 0, color: "#f1f5f9" }}>🔄 Restore Wizard</h2>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", fontSize: 20, cursor: "pointer" }}>✕</button>
        </div>

        {/* Step indicators */}
        <div style={{ display: "flex", gap: 16, marginBottom: 28, borderBottom: "1px solid #334155", paddingBottom: 16 }}>
          {STEPS.map((label, i) => (
            <div key={i} style={S.step(i === step)}>
              <div style={S.stepNum(i === step, i < step)}>{i < step ? "✓" : i + 1}</div>
              {label}
            </div>
          ))}
        </div>

        {/* Step 0: Select Job */}
        {step === 0 && (
          <div>
            <p style={{ color: "#94a3b8", marginBottom: 16 }}>
              Select a successful backup job to restore on <strong style={{ color: "#f1f5f9" }}>{serverName}</strong>,
              or leave unselected to use the latest backup.
            </p>
            <div style={{ maxHeight: 260, overflowY: "auto", marginBottom: 20 }}>
              <div
                onClick={() => setSelectedJob(null)}
                style={{ padding: "10px 12px", borderRadius: 6, marginBottom: 6, cursor: "pointer",
                  background: !selectedJob ? "#1e3a5f" : "#0f172a", border: `1px solid ${!selectedJob ? "#3b82f6" : "#334155"}` }}
              >
                <div style={{ color: "#f1f5f9", fontSize: 13 }}>📁 Latest available backup</div>
                <div style={{ color: "#64748b", fontSize: 11 }}>Auto-select most recent file on server</div>
              </div>
              {jobs.map(job => (
                <div key={job.id}
                  onClick={() => setSelectedJob(job)}
                  style={{ padding: "10px 12px", borderRadius: 6, marginBottom: 6, cursor: "pointer",
                    background: selectedJob?.id === job.id ? "#1e3a5f" : "#0f172a",
                    border: `1px solid ${selectedJob?.id === job.id ? "#3b82f6" : "#334155"}` }}
                >
                  <div style={{ color: "#f1f5f9", fontSize: 13 }}>Job #{job.id}</div>
                  <div style={{ color: "#64748b", fontSize: 11 }}>
                    {job.started_at ? new Date(job.started_at).toLocaleString() : "Unknown time"}
                  </div>
                </div>
              ))}
            </div>
            <button style={S.btn("#3b82f6")} onClick={() => setStep(1)}>Next →</button>
          </div>
        )}

        {/* Step 1: Configure */}
        {step === 1 && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <label style={S.label}>Restore Path (on target server)</label>
              <input style={S.input} value={restorePath}
                onChange={e => setRestorePath(e.target.value)} />
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={S.label}>GPG Passphrase *</label>
              <input style={S.input} type="password" value={passphrase}
                onChange={e => setPassphrase(e.target.value)}
                placeholder="Enter backup encryption passphrase" />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button style={S.btn("#475569")} onClick={() => setStep(0)}>← Back</button>
              <button style={S.btn("#3b82f6")} onClick={() => { if (!passphrase) { setError("Passphrase required"); return; } setError(""); setStep(2); }}>Next →</button>
            </div>
            {error && <p style={{ color: "#ef4444", marginTop: 8, fontSize: 13 }}>{error}</p>}
          </div>
        )}

        {/* Step 2: Confirm */}
        {step === 2 && (
          <div>
            <div style={{ background: "#0f172a", borderRadius: 8, padding: "1rem", marginBottom: 20 }}>
              <div style={{ color: "#94a3b8", fontSize: 12, marginBottom: 12 }}>RESTORE SUMMARY</div>
              {[
                ["Server",       serverName],
                ["Job",          selectedJob ? `#${selectedJob.id}` : "Latest available"],
                ["Restore Path", restorePath],
                ["Passphrase",   "••••••••"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ color: "#64748b", fontSize: 13 }}>{k}</span>
                  <span style={{ color: "#f1f5f9", fontSize: 13 }}>{v}</span>
                </div>
              ))}
            </div>
            <p style={{ color: "#fbbf24", fontSize: 13, marginBottom: 16 }}>
              ⚠️ This will overwrite existing data at the restore path. Proceed with caution.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button style={S.btn("#475569")} onClick={() => setStep(1)}>← Back</button>
              <button style={S.btn("#ef4444")} onClick={handleStart}>🔄 Start Restore</button>
            </div>
          </div>
        )}

        {/* Step 3: Running */}
        {step === 3 && (
          <div style={{ textAlign: "center" }}>
            {!restoreOp ? (
              <div>
                <div style={{ fontSize: 40, marginBottom: 12 }}>⏳</div>
                <p style={{ color: "#94a3b8" }}>Initiating restore...</p>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 40, marginBottom: 12 }}>
                  {restoreOp.restore_status === "completed" ? "✅" :
                   restoreOp.restore_status === "failed"    ? "❌" : "🔄"}
                </div>
                <div style={{ color: statusColor[restoreOp.restore_status] || "#f1f5f9",
                              fontSize: 18, fontWeight: 700, marginBottom: 8, textTransform: "uppercase" }}>
                  {restoreOp.restore_status}
                </div>
                {polling && <p style={{ color: "#64748b", fontSize: 13 }}>Checking status every 3 seconds...</p>}
                {restoreOp.error_message && (
                  <div style={{ background: "#7f1d1d", borderRadius: 6, padding: 12, marginTop: 12, textAlign: "left" }}>
                    <div style={{ color: "#fca5a5", fontSize: 13 }}>{restoreOp.error_message}</div>
                  </div>
                )}
                {restoreOp.restore_status === "completed" && (
                  <p style={{ color: "#22c55e", fontSize: 13 }}>
                    Restore completed successfully to {restoreOp.restore_path}
                  </p>
                )}
              </div>
            )}
            {error && <p style={{ color: "#ef4444", marginTop: 8 }}>{error}</p>}
            {["completed","failed"].includes(restoreOp?.restore_status) && (
              <button style={{ ...S.btn("#3b82f6"), marginTop: 16 }} onClick={onClose}>Close</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
