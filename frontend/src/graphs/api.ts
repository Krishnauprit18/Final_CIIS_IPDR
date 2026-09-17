import apiClient from '../api/client';

export async function getGraph(limit = 50) {
  const { data } = await apiClient.get('/graph', { params: { limit } });
  return data;
}

export async function getCorrelation() {
  const { data } = await apiClient.get('/correlation/a2b');
  return data;
}
