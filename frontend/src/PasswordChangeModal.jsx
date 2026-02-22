import { useState } from 'react';
import axios from 'axios';

export default function PasswordChangeModal({ tempToken, onComplete }) {
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post(
        'http://localhost:8000/api/v1/auth/complete-password-change',
        { token: tempToken, new_password: newPassword }
      );

      localStorage.setItem('token', response.data.access_token);
      localStorage.setItem('user', JSON.stringify(response.data.user));
      onComplete(response.data.user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Password change failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
    }}>
      <div style={{
        background: '#0f172a', borderRadius: 12, padding: '2rem', width: 420,
        boxShadow: '0 25px 50px rgba(0,0,0,0.5)', border: '1px solid #1e293b',
      }}>
        <h2 style={{ margin: '0 0 0.5rem', color: '#f1f5f9', fontSize: 22 }}>
          🔒 Password Change Required
        </h2>
        <p style={{ margin: '0 0 1.5rem', color: '#64748b', fontSize: 14 }}>
          Your administrator requires you to set a new password before continuing.
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ color: '#94a3b8', fontSize: 13, marginBottom: 6, display: 'block', fontWeight: 500 }}>
              New Password
            </label>
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
              style={{
                background: '#1e293b', color: '#f1f5f9', border: '1px solid #334155',
                borderRadius: 6, padding: '10px 12px', fontSize: 14, width: '100%', boxSizing: 'border-box',
              }}
              placeholder="Minimum 8 characters" required autoFocus />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ color: '#94a3b8', fontSize: 13, marginBottom: 6, display: 'block', fontWeight: 500 }}>
              Confirm New Password
            </label>
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
              style={{
                background: '#1e293b', color: '#f1f5f9', border: '1px solid #334155',
                borderRadius: 6, padding: '10px 12px', fontSize: 14, width: '100%', boxSizing: 'border-box',
              }}
              placeholder="Re-enter password" required />
          </div>

          {error && (
            <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: '10px 12px',
              borderRadius: 6, marginBottom: 16, fontSize: 13 }}>
              {error}
            </div>
          )}

          <button type="submit" disabled={loading}
            style={{
              background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6,
              padding: '10px 20px', fontSize: 14, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer', width: '100%', opacity: loading ? 0.6 : 1,
            }}>
            {loading ? 'Changing Password...' : 'Set Password & Continue'}
          </button>
        </form>
      </div>
    </div>
  );
}
