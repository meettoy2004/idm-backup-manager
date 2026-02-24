import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { statsApi, serversApi } from './api';

const COLORS = { success: '#4CAF50', failed: '#f44336', pending: '#FF9800' };
const PIE_COLORS = ['#4CAF50', '#f44336', '#FF9800', '#2196F3'];

function StatCard({ label, value, sub, color = '#1F4E79' }) {
  return (
    <div style={{
      background: 'white', borderRadius: 10, padding: '24px 28px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)', flex: 1,
      borderTop: `4px solid ${color}`, minWidth: 160
    }}>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 6, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 36, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#aaa', marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function ChartCard({ title, children, controls }) {
  return (
    <div style={{
      background: 'white', borderRadius: 10, padding: 24,
      boxShadow: '0 2px 8px rgba(0,0,0,0.08)', marginBottom: 24
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h3 style={{ margin: 0, color: '#1F4E79', fontSize: 16 }}>{title}</h3>
        {controls}
      </div>
      {children}
    </div>
  );
}

function HealthBadge({ status }) {
  const cfg = {
    success: { bg: '#E8F5E9', color: '#2E7D32', label: '✓ Success' },
    failed:  { bg: '#FFEBEE', color: '#C62828', label: '✗ Failed'  },
    never:   { bg: '#F5F5F5', color: '#888888', label: '— No Jobs' },
    running: { bg: '#E3F2FD', color: '#1565C0', label: '⟳ Running' },
    pending: { bg: '#FFF3E0', color: '#E65100', label: '… Pending' },
  }[status] || { bg: '#F5F5F5', color: '#888', label: status };
  return (
    <span style={{ padding: '3px 10px', borderRadius: 12, fontSize: 12,
      fontWeight: 600, background: cfg.bg, color: cfg.color }}>
      {cfg.label}
    </span>
  );
}

function DiskBar({ pct }) {
  const num = parseInt(pct) || 0;
  const color = num >= 90 ? '#f44336' : num >= 75 ? '#FF9800' : '#4CAF50';
  return (
    <div style={{ background: '#e5e7eb', borderRadius: 4, height: 8, overflow: 'hidden' }}>
      <div style={{ width: `${Math.min(num, 100)}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.3s' }} />
    </div>
  );
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

export default function Dashboard() {
  const [overview,    setOverview]    = useState(null);
  const [timeSeries,  setTimeSeries]  = useState([]);
  const [byServer,    setByServer]    = useState([]);
  const [failures,    setFailures]    = useState([]);
  const [durations,   setDurations]   = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [timeRange,   setTimeRange]   = useState(30);
  const [sysHealth,   setSysHealth]   = useState([]);   // [{server_id, server_name, hostname, root_disk, backup_disk, ipa_services, error}]
  const [sysLoading,  setSysLoading]  = useState(false);

  useEffect(() => { loadAll(); }, [timeRange]);
  useEffect(() => { loadSysHealth(); }, []);

  const loadSysHealth = async () => {
    setSysLoading(true);
    try {
      const serversResp = await serversApi.list();
      const servers = serversResp.data;
      const results = await Promise.all(
        servers.map(s => serversApi.systemStatus(s.id).catch(err => ({
          data: { server_id: s.id, server_name: s.name, hostname: s.hostname,
                  error: err.message, root_disk: null, backup_disk: null, ipa_services: [] }
        })))
      );
      setSysHealth(results.map(r => r.data));
    } catch (e) {
      console.error('sysHealth load error:', e);
    } finally {
      setSysLoading(false);
    }
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [ov, ts, bs, rf, dur] = await Promise.all([
        statsApi.overview(),
        statsApi.jobsOverTime(timeRange),
        statsApi.successByServer(timeRange),
        statsApi.recentFailures(),
        statsApi.jobDurationStats(timeRange),
      ]);
      setOverview(ov.data);
      setTimeSeries(ts.data);
      setByServer(bs.data);
      setFailures(rf.data);
      setDurations(dur.data);
    } catch (e) {
      console.error('Dashboard load error:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !overview) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" />
          <p style={{ color: '#888' }}>Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const { servers, configs, jobs_30d, server_health } = overview;

  // Pie chart data for job outcomes
  const pieData = [
    { name: 'Success', value: jobs_30d.success },
    { name: 'Failed',  value: jobs_30d.failed  },
    { name: 'Other',   value: jobs_30d.total - jobs_30d.success - jobs_30d.failed },
  ].filter(d => d.value > 0);

  const rangeBtn = (val, label) => (
    <button
      onClick={() => setTimeRange(val)}
      style={{
        padding: '4px 12px', marginLeft: 6, borderRadius: 6, cursor: 'pointer',
        fontSize: 12, fontWeight: 600, border: '1px solid #ddd',
        background: timeRange === val ? '#1F4E79' : 'white',
        color: timeRange === val ? 'white' : '#555',
      }}
    >{label}</button>
  );

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, color: '#1F4E79', fontSize: 22 }}>Monitoring Dashboard</h2>
        <p style={{ margin: '4px 0 0', color: '#888', fontSize: 13 }}>
          Last refreshed: {new Date().toLocaleString()}
          <button onClick={loadAll} style={{ marginLeft: 12, fontSize: 12, padding: '2px 10px',
            background: '#E3F2FD', color: '#1565C0', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
            ↻ Refresh
          </button>
        </p>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <StatCard label="Total Servers"     value={servers.total}          sub={`${servers.active} active`}          color="#1F4E79" />
        <StatCard label="Backup Configs"    value={configs.total}          sub={`${configs.enabled} enabled`}        color="#2E75B6" />
        <StatCard label="Jobs (30 days)"    value={jobs_30d.total}         sub={`${jobs_30d.success} succeeded`}     color="#4CAF50" />
        <StatCard label="Failed (30 days)"  value={jobs_30d.failed}        sub="requires attention"                  color={jobs_30d.failed > 0 ? '#f44336' : '#4CAF50'} />
        <StatCard label="Success Rate"      value={`${jobs_30d.success_rate}%`} sub="last 30 days"                  color={jobs_30d.success_rate >= 90 ? '#4CAF50' : jobs_30d.success_rate >= 70 ? '#FF9800' : '#f44336'} />
      </div>

      {/* Server Health & Pie Chart */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, marginBottom: 0 }}>
        <ChartCard title="Server Health Status">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#F5F5F5' }}>
                {['Server', 'Hostname', 'Last Backup', 'Status', 'Error'].map(h => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: '#555', fontWeight: 600, borderBottom: '1px solid #eee' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {server_health.map((s, i) => (
                <tr key={s.server_id} style={{ background: i % 2 === 0 ? 'white' : '#FAFAFA' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 600, color: '#1F4E79' }}>{s.server_name}</td>
                  <td style={{ padding: '10px 12px', color: '#666', fontFamily: 'monospace', fontSize: 12 }}>{s.hostname}</td>
                  <td style={{ padding: '10px 12px', color: '#888', fontSize: 12 }}>{formatDate(s.last_job_time)}</td>
                  <td style={{ padding: '10px 12px' }}><HealthBadge status={s.last_job_status} /></td>
                  <td style={{ padding: '10px 12px', color: '#f44336', fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.last_job_error || '—'}
                  </td>
                </tr>
              ))}
              {server_health.length === 0 && (
                <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: '#aaa' }}>No servers configured</td></tr>
              )}
            </tbody>
          </table>
        </ChartCard>

        <ChartCard title="Job Outcomes (30 days)">
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                    {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i]} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8 }}>
                {pieData.map((d, i) => (
                  <div key={d.name} style={{ fontSize: 12, color: '#666', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: PIE_COLORS[i], display: 'inline-block' }} />
                    {d.name}: {d.value}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#aaa' }}>No job data yet</div>
          )}
        </ChartCard>
      </div>

      {/* Time Series Chart */}
      <ChartCard
        title="Backup Jobs Over Time"
        controls={<div>{rangeBtn(7, '7d')}{rangeBtn(14, '14d')}{rangeBtn(30, '30d')}</div>}
      >
        {timeSeries.some(d => d.total > 0) ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={timeSeries} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#888' }} tickFormatter={d => d.slice(5)} />
              <YAxis tick={{ fontSize: 11, fill: '#888' }} allowDecimals={false} />
              <Tooltip formatter={(val, name) => [val, name.charAt(0).toUpperCase() + name.slice(1)]} labelFormatter={l => `Date: ${l}`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="success" name="Success" fill="#4CAF50" radius={[3,3,0,0]} />
              <Bar dataKey="failed"  name="Failed"  fill="#f44336" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 60, color: '#aaa' }}>No job data in this time range</div>
        )}
      </ChartCard>

      {/* Success Rate by Server */}
      <ChartCard title="Success Rate by Server" controls={<div>{rangeBtn(7, '7d')}{rangeBtn(30, '30d')}</div>}>
        {byServer.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byServer} margin={{ top: 5, right: 20, left: 0, bottom: 5 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#888' }} tickFormatter={v => `${v}%`} />
              <YAxis dataKey="server_name" type="category" tick={{ fontSize: 12, fill: '#555' }} width={120} />
              <Tooltip formatter={(val) => [`${val}%`, 'Success Rate']} />
              <Bar dataKey="success_rate" name="Success Rate" radius={[0,4,4,0]}
                fill="#2E75B6"
                label={{ position: 'right', fontSize: 12, fill: '#555', formatter: v => `${v}%` }}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>No server data yet</div>
        )}
      </ChartCard>

      {/* Server System Health — Disk + IPA Services */}
      <ChartCard
        title="Server System Health"
        controls={
          <button onClick={loadSysHealth} disabled={sysLoading}
            style={{ fontSize: 12, padding: '3px 10px', background: '#E3F2FD', color: '#1565C0',
              border: 'none', borderRadius: 6, cursor: sysLoading ? 'not-allowed' : 'pointer' }}>
            {sysLoading ? '⟳ Checking...' : '↻ Refresh'}
          </button>
        }
      >
        {sysLoading && sysHealth.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>Connecting to servers...</div>
        ) : sysHealth.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>No servers configured</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {sysHealth.map(srv => (
              <div key={srv.server_id} style={{ border: '1px solid #eee', borderRadius: 8, padding: '14px 16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <span style={{ fontWeight: 700, color: '#1F4E79', fontSize: 14 }}>{srv.server_name}</span>
                    <span style={{ color: '#888', fontSize: 12, marginLeft: 8, fontFamily: 'monospace' }}>{srv.hostname}</span>
                  </div>
                  {srv.error && (
                    <span style={{ color: '#f44336', fontSize: 12, background: '#FFEBEE', padding: '2px 8px', borderRadius: 4 }}>
                      SSH error — {srv.error}
                    </span>
                  )}
                </div>
                {!srv.error && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                    {/* Root disk */}
                    <div>
                      <div style={{ fontSize: 12, color: '#555', fontWeight: 600, marginBottom: 6 }}>💿 Root Filesystem ( / )</div>
                      {srv.root_disk ? (
                        <>
                          <DiskBar pct={srv.root_disk.use_pct} />
                          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                            {srv.root_disk.used} used of {srv.root_disk.size} ({srv.root_disk.use_pct})
                            {srv.root_disk.type && <span style={{ marginLeft: 6, color: '#bbb' }}>{srv.root_disk.type}</span>}
                          </div>
                        </>
                      ) : <span style={{ color: '#aaa', fontSize: 12 }}>N/A</span>}
                    </div>
                    {/* Backup disk */}
                    <div>
                      <div style={{ fontSize: 12, color: '#555', fontWeight: 600, marginBottom: 6 }}>🗂 Backup Dir ( /var/lib/ipa/backup )</div>
                      {srv.backup_disk ? (
                        <>
                          <DiskBar pct={srv.backup_disk.use_pct} />
                          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                            {srv.backup_disk.used} used of {srv.backup_disk.size} ({srv.backup_disk.use_pct})
                          </div>
                        </>
                      ) : <span style={{ color: '#aaa', fontSize: 12 }}>N/A</span>}
                    </div>
                    {/* IPA services */}
                    <div>
                      <div style={{ fontSize: 12, color: '#555', fontWeight: 600, marginBottom: 6 }}>⚙ IPA Services</div>
                      {srv.ipa_services.length === 0 ? (
                        <span style={{ color: '#aaa', fontSize: 12 }}>No data</span>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                          {srv.ipa_services.map((svc, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                              <span style={{ color: '#555' }}>{svc.service}</span>
                              <span style={{ fontWeight: 600, color: svc.status === 'RUNNING' ? '#4CAF50' : '#f44336' }}>
                                {svc.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </ChartCard>

      {/* Duration Stats + Recent Failures side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <ChartCard title="Avg Backup Duration by Server">
          {durations.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#F5F5F5' }}>
                  {['Server', 'Avg', 'Min', 'Max', 'Jobs'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', textAlign: 'left', color: '#555', fontWeight: 600, borderBottom: '1px solid #eee' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {durations.map((d, i) => (
                  <tr key={d.server_name} style={{ background: i % 2 === 0 ? 'white' : '#FAFAFA' }}>
                    <td style={{ padding: '8px 10px', fontWeight: 600, color: '#1F4E79' }}>{d.server_name}</td>
                    <td style={{ padding: '8px 10px', color: '#4CAF50', fontWeight: 600 }}>{formatDuration(d.avg_duration_seconds)}</td>
                    <td style={{ padding: '8px 10px', color: '#888' }}>{formatDuration(d.min_duration_seconds)}</td>
                    <td style={{ padding: '8px 10px', color: '#888' }}>{formatDuration(d.max_duration_seconds)}</td>
                    <td style={{ padding: '8px 10px', color: '#888' }}>{d.job_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>No completed jobs yet</div>
          )}
        </ChartCard>

        <ChartCard title="Recent Failures">
          {failures.length > 0 ? (
            <div style={{ maxHeight: 280, overflowY: 'auto' }}>
              {failures.map(f => (
                <div key={f.job_id} style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, color: '#1F4E79', fontSize: 13 }}>{f.server_name}</span>
                    <span style={{ fontSize: 11, color: '#aaa' }}>{formatDate(f.created_at)}</span>
                  </div>
                  <div style={{ fontSize: 12, color: '#f44336', background: '#FFEBEE', padding: '4px 8px', borderRadius: 4 }}>
                    {f.error_message || 'Unknown error'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>✓</div>
              <div style={{ color: '#4CAF50', fontWeight: 600 }}>No recent failures!</div>
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
