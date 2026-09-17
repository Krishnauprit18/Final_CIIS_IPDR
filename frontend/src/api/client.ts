import axios from 'axios';

export const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('ipdr_token');
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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

export default apiClient;
