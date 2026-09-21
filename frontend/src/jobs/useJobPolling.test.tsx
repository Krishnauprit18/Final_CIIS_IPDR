import { act, render, screen, waitFor } from '@testing-library/react';
import { getJob } from './api';
import { useJobPolling } from './useJobPolling';

jest.mock('./api', () => ({
  getJob: jest.fn(),
}));

function Probe({ jobId }: { jobId: number | null }) {
  const { job, error } = useJobPolling(jobId, 10);
  return (
    <div>
      <span data-testid="status">{job?.status || 'idle'}</span>
      <span data-testid="error">{error || ''}</span>
    </div>
  );
}

const mockedGetJob = getJob as jest.MockedFunction<typeof getJob>;

afterEach(() => {
  jest.clearAllMocks();
  jest.useRealTimers();
});

test('polling stops after a terminal job status', async () => {
  mockedGetJob.mockResolvedValueOnce({
    id: 7,
    case_id: 1,
    status: 'SUCCEEDED',
    progress: 100,
    attempt_count: 1,
  });

  render(<Probe jobId={7} />);

  await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('SUCCEEDED'));
  expect(mockedGetJob).toHaveBeenCalledTimes(1);
});

test('polling surfaces a transient error and retries', async () => {
  jest.useFakeTimers();
  mockedGetJob
    .mockRejectedValueOnce(new Error('temporary API outage'))
    .mockResolvedValueOnce({
      id: 8,
      case_id: 1,
      status: 'SUCCEEDED',
      progress: 100,
      attempt_count: 2,
    });

  render(<Probe jobId={8} />);

  await act(async () => {
    await Promise.resolve();
  });
  expect(screen.getByTestId('error')).toHaveTextContent('temporary API outage');

  await act(async () => {
    jest.advanceTimersByTime(10);
    await Promise.resolve();
  });
  await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('SUCCEEDED'));
  expect(mockedGetJob).toHaveBeenCalledTimes(2);
});
