import apiClient from '../api/client';

export async function getSearchStatistics() {
  const { data } = await apiClient.get('/search/statistics');
  return data;
}

export async function getData(query = '') {
  const { data } = await apiClient.get('/data', { params: { query } });
  return data;
}
