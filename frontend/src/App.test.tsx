import { render, screen } from '@testing-library/react';
import App from './App';

jest.mock('axios', () => {
  const client = {
    get: jest.fn(() => Promise.resolve({ data: {} })),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    put: jest.fn(() => Promise.resolve({ data: {} })),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
    defaults: {
      headers: { common: {} },
    },
  };

  return {
    __esModule: true,
    default: {
      ...client,
      create: jest.fn(() => client),
    },
  };
});

test('renders IPDR application shell', async () => {
  render(<App />);
  const dashboardElement = await screen.findByText(/IPDR Analysis/i);
  expect(dashboardElement).toBeInTheDocument();
});
