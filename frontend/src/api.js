import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

export const serversApi = {
  list:   () => api.get('/servers/'),
  get:    (id) => api.get(`/servers/${id}/`),
  create: (data) => api.post('/servers/', data),
  delete: (id) => api.delete(`/servers/${id}/`),
};

export const backupsApi = {
  list:   () => api.get('/backups/'),
  get:    (id) => api.get(`/backups/${id}/`),
  create: (data) => api.post('/backups/', data),
  update: (id, data) => api.put(`/backups/${id}/`, data),
  deploy: (id) => api.post(`/backups/${id}/deploy`),
  delete: (id) => api.delete(`/backups/${id}/`),
};

export const jobsApi = {
  list:      (params) => api.get('/jobs/', { params }),
  get:       (id) => api.get(`/jobs/${id}/`),
  trigger:   (serverId) => api.post('/jobs/trigger', { server_id: serverId }),
  getLatest: (serverId) => api.get(`/jobs/server/${serverId}/latest`),
};

export const statsApi = {
  overview:         () => api.get('/stats/overview'),
  jobsOverTime:     (days = 30) => api.get('/stats/jobs-over-time', { params: { days } }),
  successByServer:  (days = 30) => api.get('/stats/success-rate-by-server', { params: { days } }),
  recentFailures:   (limit = 10) => api.get('/stats/recent-failures', { params: { limit } }),
  jobDurationStats: (days = 30) => api.get('/stats/job-duration-stats', { params: { days } }),
};

export default api;
