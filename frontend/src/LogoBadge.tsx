import React from 'react';
import { Box } from '@mui/material';

type LogoBadgeProps = {
  src?: string;
  alt?: string;
  width?: number; // px
  top?: number;   // px
  left?: number;  // px
  zIndex?: number;
};

/**
 * Fixed-position logo badge shown at the very top-left of the viewport,
 * intentionally independent from the left navigation drawer.
 */
const LogoBadge: React.FC<LogoBadgeProps> = ({
  src = '/bharatsarkar.jpeg',
  alt = 'Bharat Sarkar',
  width = 160,
  top = 12,
  left = 12,
  zIndex = 1500,
}) => {
  return (
    <Box
      sx={{
        position: 'fixed',
        top,
        left,
        width,
        height: 'auto',
        zIndex,
        // Keep this visually distinct and floating
        pointerEvents: 'none',
      }}
    >
      <img
        src={src}
        alt={alt}
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
        style={{ display: 'block', width: '100%', height: 'auto', objectFit: 'contain' }}
      />
    </Box>
  );
};

export default LogoBadge;

