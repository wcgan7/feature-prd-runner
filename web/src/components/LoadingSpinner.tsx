import { Box, CircularProgress, Typography } from '@mui/material'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export default function LoadingSpinner({ size = 'md', className = '', label }: Props) {
  const sizeValue = {
    sm: 16,
    md: 24,
    lg: 40,
  }[size]

  return (
    <Box className={className} sx={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
      <CircularProgress size={sizeValue} thickness={4} role="status" aria-label={label || 'Loading'} />
      {label && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {label}
        </Typography>
      )}
    </Box>
  )
}
