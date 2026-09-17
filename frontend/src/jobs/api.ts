import apiClient from '../api/client';

export type JobStatus = 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';

export interface JobRecord {
  id: number;
  case_id: number | null;
  status: JobStatus;
  progress: number;
  attempt_count: number;
  error_message?: string | null;
  result_uri?: string | null;
  created_at?: string;
  updated_at?: string;
}

export async function submitAnalysis(caseId: number, datasetFile: File, caseFile?: File | null) {
  const form = new FormData();
  form.append('dataset_file', datasetFile);
  if (caseFile) form.append('case_file', caseFile);
  const { data } = await apiClient.post(`/cases/${caseId}/analysis`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data as { job_id: number; status: string };
}

export async function getJob(jobId: number): Promise<JobRecord> {
  const { data } = await apiClient.get(`/jobs/${jobId}`);
  return data;
}
