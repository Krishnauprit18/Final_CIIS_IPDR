import apiClient from '../api/client';

export interface CaseSummary {
  id: number;
  name: string;
  created_by?: string | null;
  created_at?: string;
}

export async function listCases(): Promise<CaseSummary[]> {
  const { data } = await apiClient.get('/cases');
  return Array.isArray(data) ? data : [];
}

export async function createCase(name: string): Promise<CaseSummary> {
  const { data } = await apiClient.post('/cases', { name });
  return data;
}
