import apiClient from '../api/client';

export async function getSuspiciousActivity() {
  const { data } = await apiClient.get('/suspicious/comprehensive-analysis');
  return data;
}
