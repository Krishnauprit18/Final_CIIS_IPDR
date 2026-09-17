import { useEffect, useRef, useState } from 'react';
import { getJob, JobRecord } from './api';

const TERMINAL = new Set(['SUCCEEDED', 'FAILED']);

export function useJobPolling(jobId: number | null, intervalMs = 1500) {
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    const stop = () => {
      if (timer.current !== null) {
        window.clearTimeout(timer.current);
        timer.current = null;
      }
    };

    const poll = async () => {
      if (!jobId) return;
      try {
        const next = await getJob(jobId);
        if (cancelled) return;
        setJob(next);
        setError(null);
        if (!TERMINAL.has(next.status)) {
          timer.current = window.setTimeout(poll, intervalMs);
        }
      } catch (err: any) {
        if (cancelled) return;
        setError(err?.response?.data?.detail || err?.message || 'Could not load job status');
        timer.current = window.setTimeout(poll, intervalMs);
      }
    };

    setJob(null);
    setError(null);
    poll();

    return () => {
      cancelled = true;
      stop();
    };
  }, [jobId, intervalMs]);

  return { job, error };
}
