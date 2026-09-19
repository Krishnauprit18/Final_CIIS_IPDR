import axios, { InternalAxiosRequestConfig } from 'axios';

export const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const LEGACY_LOCAL_BASE = 'http://localhost:8000';

function applyAuth(config: InternalAxiosRequestConfig) {
  const token = localStorage.getItem('ipdr_token');
  if (token) {
    if (typeof (config.headers as any)?.set === 'function') {
      (config.headers as any).set('Authorization', `Bearer ${token}`);
    } else {
      (config.headers as any).Authorization = `Bearer ${token}`;
    }
  }
  return config;
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  withCredentials: true,
});

apiClient.interceptors.request.use(applyAuth);

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = axios.post(
      `${API_BASE_URL}/auth/refresh`,
      {},
      { withCredentials: true },
    )
      .then((response) => {
        const token = response.data?.token || response.data?.access_token;
        if (!token) return null;
        localStorage.setItem('ipdr_token', token);
        if (response.data?.username) {
          localStorage.setItem('ipdr_username', response.data.username);
        }
        return token as string;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;

    if (
      error?.response?.status === 401 &&
      original &&
      !original._retry &&
      !String(original.url || '').includes('/auth/refresh')
    ) {
      original._retry = true;
      const token = await refreshAccessToken();

      if (token) {
        if (typeof (original.headers as any)?.set === 'function') {
          (original.headers as any).set('Authorization', `Bearer ${token}`);
        } else {
          (original.headers as any).Authorization = `Bearer ${token}`;
        }
        return apiClient(original);
      }
    }

    if (error?.response?.status === 401) {
      localStorage.removeItem('ipdr_token');
      localStorage.removeItem('ipdr_username');
    }
    return Promise.reject(error);
  },
);

// Transitional adapter for the isolated legacy analytics module.
axios.interceptors.request.use((config) => {
  if (typeof config.url === 'string' && config.url.startsWith(LEGACY_LOCAL_BASE)) {
    config.url = `${API_BASE_URL}${config.url.slice(LEGACY_LOCAL_BASE.length)}`;
  }
  config.withCredentials = true;
  return applyAuth(config as InternalAxiosRequestConfig);
});

export default apiClient;
