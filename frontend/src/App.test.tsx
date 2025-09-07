import { render, screen } from '@testing-library/react';
import App from './App';

test('renders dashboard component', () => {
  render(<App />);
  const dashboardElement = screen.getByText(/IPDR Analysis/i);
  expect(dashboardElement).toBeInTheDocument();
});
