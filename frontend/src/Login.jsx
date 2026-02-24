import { useState, useEffect } from "react";
import axios from "axios";
import PasswordChangeModal from "./PasswordChangeModal";

const BASE = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1`;

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);
  const [providers, setProviders] = useState([]);
  const [ldapProvider, setLdapProvider] = useState(null);
  const [showLdap, setShowLdap] = useState(false);
  const [ldapUser, setLdapUser] = useState("");
  const [ldapPass, setLdapPass] = useState("");
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const [tempToken, setTempToken] = useState(null);

  useEffect(() => {
    axios.get(`${BASE}/providers/public`)
      .then(r => {
        setProviders(r.data.filter(p => p.type !== "ldap"));
        const ldap = r.data.find(p => p.type === "ldap");
        if (ldap) setLdapProvider(ldap);
      }).catch(() => {});

    const hash = window.location.hash;
    if (hash.includes("token=")) {
      const token = new URLSearchParams(hash.split("?")[1]).get("token");
      if (token) {
        axios.get(`${BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        }).then(r => {
          localStorage.setItem("token", token);
          localStorage.setItem("user", JSON.stringify(r.data));
          onLogin(r.data);
        }).catch(() => setError("SSO login failed — invalid token"));
      }
    }
  }, [onLogin]);

  const handleLocal = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    
    try {
      // OAuth2PasswordRequestForm expects form data, not JSON
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);
      
      const res = await axios.post(`${BASE}/auth/login`, formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      
      // Check if password change is required
      if (res.data.requires_password_change) {
        setTempToken(res.data.temp_token);
        setShowPasswordChange(true);
        setLoading(false);
        return;
      }

      // Normal login flow
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user", JSON.stringify(res.data.user));
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLdap = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const res = await axios.post(`${BASE}/providers/${ldapProvider.id}/ldap/login`, {
        username: ldapUser, password: ldapPass
      });
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user", JSON.stringify(res.data.user));
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || "LDAP login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleOIDC = (provider) => {
    window.location.href = `${BASE}/providers/${provider.id}/oidc/login`;
  };

  const handleSAML = (provider) => {
    window.location.href = `${BASE}/providers/${provider.id}/saml/login`;
  };

  const inputStyle = {
    background: "#1e293b", color: "#f1f5f9", border: "1px solid #334155",
    borderRadius: 6, padding: "10px 12px", fontSize: 14, width: "100%", boxSizing: "border-box",
  };
  const labelStyle = { color: "#94a3b8", fontSize: 13, marginBottom: 6, display: "block", fontWeight: 500 };

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", display: "flex",
      alignItems: "center", justifyContent: "center", padding: 20 }}>
      <div style={{ background: "#1e293b", borderRadius: 12, padding: "2.5rem", width: 400,
        boxShadow: "0 25px 50px rgba(0,0,0,0.3)", border: "1px solid #334155" }}>
        <h1 style={{ margin: "0 0 0.5rem", color: "#f1f5f9", fontSize: 28, textAlign: "center" }}>
          🔐 IdM Backup Manager
        </h1>
        <p style={{ margin: "0 0 2rem", color: "#64748b", fontSize: 14, textAlign: "center" }}>
          Sign in to continue
        </p>

        <form onSubmit={handleLocal}>
          <div style={{ marginBottom: 14 }}>
            <label style={labelStyle}>Username or Email</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)}
              style={inputStyle} placeholder="admin" required autoFocus />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              style={inputStyle} placeholder="••••••••" required />
          </div>
          {error && (
            <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "10px 12px",
              borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
              {error}
            </div>
          )}
          <button type="submit" disabled={loading}
            style={{ background: "#3b82f6", color: "#fff", border: "none", borderRadius: 6,
              padding: "10px 20px", fontSize: 14, fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer", width: "100%", marginBottom: 16,
              opacity: loading ? 0.6 : 1 }}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        {(providers.length > 0 || ldapProvider) && (
          <>
            <div style={{ display: "flex", alignItems: "center", margin: "1.5rem 0", gap: 12 }}>
              <div style={{ flex: 1, height: 1, background: "#334155" }} />
              <span style={{ color: "#64748b", fontSize: 12 }}>OR</span>
              <div style={{ flex: 1, height: 1, background: "#334155" }} />
            </div>

            {providers.map(p => (
              <button key={p.id}
                onClick={() => p.type === "oidc" ? handleOIDC(p) : handleSAML(p)}
                style={{ background: "#334155", color: "#cbd5e1", border: "none", borderRadius: 6,
                  padding: "10px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer", width: "100%",
                  marginBottom: 10 }}>
                {p.type === "oidc" ? "🔑" : "🎫"} Sign in with {p.name}
              </button>
            ))}

            {ldapProvider && !showLdap && (
              <button onClick={() => setShowLdap(true)}
                style={{ background: "#334155", color: "#cbd5e1", border: "none", borderRadius: 6,
                  padding: "10px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer", width: "100%" }}>
                📂 Sign in with {ldapProvider.name}
              </button>
            )}

            {ldapProvider && showLdap && (
              <form onSubmit={handleLdap}>
                <div style={{ marginBottom: 10 }}>
                  <label style={labelStyle}>LDAP Username</label>
                  <input value={ldapUser} onChange={(e) => setLdapUser(e.target.value)}
                    style={inputStyle} required />
                </div>
                <div style={{ marginBottom: 14 }}>
                  <label style={labelStyle}>LDAP Password</label>
                  <input type="password" value={ldapPass} onChange={(e) => setLdapPass(e.target.value)}
                    style={inputStyle} required />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button type="submit" disabled={loading}
                    style={{ flex: 1, background: "#1e40af", color: "#93c5fd", border: "none", borderRadius: 6,
                      padding: "8px 14px", fontSize: 13, cursor: loading ? "not-allowed" : "pointer",
                      opacity: loading ? 0.6 : 1 }}>
                    Sign in
                  </button>
                  <button type="button" onClick={() => setShowLdap(false)}
                    style={{ background: "#334155", color: "#94a3b8", border: "none", borderRadius: 6,
                      padding: "8px 14px", fontSize: 13, cursor: "pointer" }}>
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </div>

      {showPasswordChange && (
        <PasswordChangeModal
          tempToken={tempToken}
          onComplete={(user) => {
            setShowPasswordChange(false);
            onLogin(user);
          }}
        />
      )}
    </div>
  );
}
