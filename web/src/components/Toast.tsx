import { useEffect, useState } from 'react'
import {
  Box,
  IconButton,
  Paper,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { keyframes } from '@mui/system'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface ToastMessage {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastProps {
  toast: ToastMessage
  onDismiss: (id: string) => void
}

function Toast({ toast, onDismiss }: ToastProps) {
  const [isExiting, setIsExiting] = useState(false)
  const duration = toast.duration || 5000
  const enterAnimation = keyframes`
    from {
      opacity: 0;
      transform: translateX(100%);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  `
  const exitAnimation = keyframes`
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(100%);
    }
  `
  const progressAnimation = keyframes`
    from { transform: scaleX(1); }
    to { transform: scaleX(0); }
  `

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true)
      setTimeout(() => onDismiss(toast.id), 200)
    }, duration)

    return () => clearTimeout(timer)
  }, [toast.id, duration, onDismiss])

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(() => onDismiss(toast.id), 200)
  }

  const getIcon = () => {
    switch (toast.type) {
      case 'success':
        return '✓'
      case 'error':
        return '✕'
      case 'warning':
        return '!'
      case 'info':
        return 'i'
      default:
        return null
    }
  }

  const typeStyles = {
    success: {
      iconBg: 'success.light',
      iconColor: 'success.dark',
      progressBg: 'success.main',
      borderColor: 'success.main',
    },
    error: {
      iconBg: 'error.light',
      iconColor: 'error.dark',
      progressBg: 'error.main',
      borderColor: 'error.main',
    },
    warning: {
      iconBg: 'warning.light',
      iconColor: 'warning.dark',
      progressBg: 'warning.main',
      borderColor: 'warning.main',
    },
    info: {
      iconBg: 'info.light',
      iconColor: 'info.dark',
      progressBg: 'info.main',
      borderColor: 'info.main',
    },
  }[toast.type]

  return (
    <Paper
      elevation={8}
      sx={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 1.5,
        p: 2,
        borderLeft: 4,
        borderColor: typeStyles.borderColor,
        position: 'relative',
        overflow: 'hidden',
        animation: `${isExiting ? exitAnimation : enterAnimation} 0.2s ${isExiting ? 'ease-in' : 'ease-out'} forwards`,
      }}
    >
      <Box
        sx={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '0.875rem',
          fontWeight: 700,
          flexShrink: 0,
          bgcolor: typeStyles.iconBg,
          color: typeStyles.iconColor,
        }}
      >
        {getIcon()}
      </Box>
      <Typography variant="body2" sx={{ flex: 1, color: 'text.primary', lineHeight: 1.45 }}>
        {toast.message}
      </Typography>
      <IconButton
        size="small"
        onClick={handleDismiss}
        aria-label="Dismiss"
        sx={{ color: 'text.secondary', mt: -0.5, mr: -0.75 }}
      >
        <span aria-hidden>×</span>
      </IconButton>
      <Box
        sx={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: 3,
          width: '100%',
          transformOrigin: 'left',
          bgcolor: typeStyles.progressBg,
          animation: `${progressAnimation} ${duration}ms linear forwards`,
        }}
      />
    </Paper>
  )
}

interface ToastContainerProps {
  toasts: ToastMessage[]
  onDismiss: (id: string) => void
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  if (toasts.length === 0) return null

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 24,
        right: isMobile ? 16 : 24,
        left: isMobile ? 16 : 'auto',
        zIndex: (t) => t.zIndex.snackbar,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        maxWidth: isMobile ? 'none' : 400,
        pointerEvents: 'none',
        '& > *': {
          pointerEvents: 'auto',
        },
      }}
    >
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </Box>
  )
}

export default Toast
