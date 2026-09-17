import axios, { InternalAxiosRequestConfig } from 'axios';

export const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const LEGACY_LOCAL_BASE = 'http://localhost:8000';

function applyAuth(config: InternalAxiosRequestConfig) {
  const token = localStorage.getItem('ipdr_token');
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

apiClient.interceptors.request.use(applyAuth);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('ipdr_token');
      localStorage.removeItem('ipdr_username');
    }
    return Promise.reject(error);
  },
);

// Transitional adapter for the isolated legacy analytics module. The old
// dashboard still builds absolute localhost URLs internally; this interceptor
// rewrites them to REACT_APP_API_BASE_URL so production never depends on the
// user's localhost. New feature modules use apiClient directly.
axios.interceptors.request.use((config) => {
  if (typeof config.url === 'string' && config.url.startsWith(LEGACY_LOCAL_BASE)) {
    config.url = `${API_BASE_URL}${config.url.slice(LEGACY_LOCAL_BASE.length)}`;
  }
  return applyAuth(config as InternalAxiosRequestConfig);
});

export default apiClient;
