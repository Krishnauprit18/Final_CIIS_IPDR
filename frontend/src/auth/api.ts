import apiClient from '../api/client';

export interface AuthUser { username: string; token: string }

export async function login(username: string, password: string): Promise<AuthUser> {
  const { data } = await apiClient.post('/auth/login', { username, password });
  if (!data?.success) throw new Error(data?.message || 'Login failed');
  return { username: data.username, token: data.token };
}

export async function register(payload: Record<string, string>) {
  const { data } = await apiClient.post('/auth/register', payload);
  return data;
}

export async function verifySession() {
  return apiClient.get('/auth/verify');
}

export async function logout() {
  return apiClient.post('/auth/logout');
}
