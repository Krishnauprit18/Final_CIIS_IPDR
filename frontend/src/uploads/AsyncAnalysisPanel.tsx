import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { submitAnalysis } from '../jobs/api';
import { useJobPolling } from '../jobs/useJobPolling';
import JobStatusChip from '../shared/JobStatusChip';

export default function AsyncAnalysisPanel() {
  const [caseId, setCaseId] = useState('');
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [caseFile, setCaseFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const { job, error: pollError } = useJobPolling(jobId);

  const submit = async () => {
    const parsedCaseId = Number(caseId);
    if (!parsedCaseId || !datasetFile) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await submitAnalysis(parsedCaseId, datasetFile, caseFile);
      setJobId(response.job_id);
    } catch (err: any) {
      setSubmitError(err?.response?.data?.detail || err?.message || 'Could not queue analysis');
    } finally {
      setSubmitting(false);
    }
  };

  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Typography variant="h6" gutterBottom>Asynchronous case analysis</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Files are uploaded first; heavy normalization, correlation and anomaly detection run in the worker queue.
      </Typography>

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }}>
        <TextField
          label="Case ID"
          type="number"
          size="small"
          value={caseId}
          onChange={(event) => setCaseId(event.target.value)}
        />
        <Button component="label" variant="outlined">
          {datasetFile ? datasetFile.name : 'Choose IPDR dataset'}
          <input hidden type="file" onChange={(event) => setDatasetFile(event.target.files?.[0] ?? null)} />
        </Button>
        <Button component="label" variant="outlined" color="inherit">
          {caseFile ? caseFile.name : 'Case document (optional)'}
          <input hidden type="file" onChange={(event) => setCaseFile(event.target.files?.[0] ?? null)} />
        </Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={submitting || !caseId || !datasetFile}
        >
          {submitting ? 'Queueing…' : 'Queue analysis'}
        </Button>
      </Stack>

      {(submitError || pollError) && (
        <Alert severity="error" sx={{ mt: 2 }}>{submitError || pollError}</Alert>
      )}

      {job && (
        <Box sx={{ mt: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="body2">Job #{job.id}</Typography>
            <JobStatusChip status={job.status} />
            <Typography variant="body2" color="text.secondary">Attempt {job.attempt_count ?? 0}</Typography>
          </Stack>
          <LinearProgress
            variant="determinate"
            value={job.status === 'FAILED' ? progress : progress}
            sx={{ height: 10, borderRadius: 5 }}
          />
          <Typography variant="caption" color="text.secondary">
            {job.status === 'QUEUED' && 'Queued'}
            {job.status === 'RUNNING' && `Processing ${progress}%`}
            {job.status === 'SUCCEEDED' && 'Completed'}
            {job.status === 'FAILED' && 'Failed'}
          </Typography>
          {job.error_message && <Alert severity="error" sx={{ mt: 1 }}>{job.error_message}</Alert>}
          {job.result_uri && (
            <Typography variant="body2" sx={{ mt: 1, wordBreak: 'break-all' }}>
              Result: {job.result_uri}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
}
