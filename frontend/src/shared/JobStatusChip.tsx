import { Chip } from '@mui/material';
import { JobStatus } from '../jobs/api';

interface Props {
  status: JobStatus;
}

export default function JobStatusChip({ status }: Props) {
  const color = status === 'SUCCEEDED'
    ? 'success'
    : status === 'FAILED'
      ? 'error'
      : status === 'RUNNING'
        ? 'warning'
        : 'default';

  const label = status === 'RUNNING' ? 'Processing' : status[0] + status.slice(1).toLowerCase();

  return <Chip size="small" label={label} color={color as any} />;
}
