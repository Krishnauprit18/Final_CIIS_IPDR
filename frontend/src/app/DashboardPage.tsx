import { Box } from '@mui/material';
import AsyncAnalysisPanel from '../uploads/AsyncAnalysisPanel';
import LegacyDashboard from '../analytics/LegacyDashboard';

export default function DashboardPage() {
  return (
    <Box>
      <Box sx={{ px: { xs: 2, md: 3 }, pt: 2, ml: { md: '220px' } }}>
        <AsyncAnalysisPanel />
      </Box>
      <LegacyDashboard />
    </Box>
  );
}
