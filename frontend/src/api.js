import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

export const serversApi = {
  list:                (params) => api.get('/servers/', { params }),
  get:                 (id) => api.get(`/servers/${id}/`),
  create:              (data) => api.post('/servers/', data),
  update:              (id, data) => api.put(`/servers/${id}/`, data),
  delete:              (id) => api.delete(`/servers/${id}/`),
  checkSubscription:   (id) => api.get(`/servers/${id}/check-subscription/`),
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

export const orgsApi = {
  list:         () => api.get('/organizations/'),
  get:          (id) => api.get(`/organizations/${id}/`),
  create:       (data) => api.post('/organizations/', data),
  update:       (id, data) => api.put(`/organizations/${id}/`, data),
  delete:       (id) => api.delete(`/organizations/${id}/`),
  addMember:    (orgId, data) => api.post(`/organizations/${orgId}/members/`, data),
  removeMember: (orgId, userId) => api.delete(`/organizations/${orgId}/members/${userId}/`),
};

export const notificationsApi = {
  list:   (params) => api.get('/notifications/', { params }),
  create: (data) => api.post('/notifications/', data),
  update: (id, data) => api.put(`/notifications/${id}/`, data),
  delete: (id) => api.delete(`/notifications/${id}/`),
};

export const verificationsApi = {
  list:    (params) => api.get('/verifications/', { params }),
  get:     (id) => api.get(`/verifications/${id}/`),
  trigger: (jobId) => api.post(`/verifications/trigger/${jobId}/`),
};

export const restoresApi = {
  list:   (params) => api.get('/restores/', { params }),
  get:    (id) => api.get(`/restores/${id}/`),
  create: (data) => api.post('/restores/', data),
  cancel: (id) => api.delete(`/restores/${id}/`),
};

export const drTemplatesApi = {
  list:   () => api.get('/dr-templates/'),
  get:    (id) => api.get(`/dr-templates/${id}/`),
  create: (data) => api.post('/dr-templates/', data),
  update: (id, data) => api.put(`/dr-templates/${id}/`, data),
  delete: (id) => api.delete(`/dr-templates/${id}/`),
};

export const reportsApi = {
  weekly:  () => api.get('/reports/weekly/'),
  monthly: () => api.get('/reports/monthly/'),
};

export default api;
