import { ReactNode } from 'react'
import { Box, Typography } from '@mui/material'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

function EmptyState({ icon, title, description, action, size = 'md' }: EmptyStateProps) {
  const sizeConfig = {
    sm: {
      padding: 2,
      iconSize: 40,
      iconFontSize: '1.25rem',
      titleVariant: 'subtitle2' as const,
      descriptionVariant: 'caption' as const,
      titleMargin: 1,
      iconMargin: 1,
    },
    md: {
      padding: 4,
      iconSize: 64,
      iconFontSize: '1.5rem',
      titleVariant: 'h6' as const,
      descriptionVariant: 'body2' as const,
      titleMargin: 1,
      iconMargin: 2,
    },
    lg: {
      padding: 6,
      iconSize: 80,
      iconFontSize: '2.25rem',
      titleVariant: 'h5' as const,
      descriptionVariant: 'body1' as const,
      titleMargin: 1.5,
      iconMargin: 3,
    },
  }[size]

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        color: 'text.secondary',
        p: sizeConfig.padding,
      }}
    >
      {icon && (
        <Box
          sx={{
            width: sizeConfig.iconSize,
            height: sizeConfig.iconSize,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'action.hover',
            borderRadius: '50%',
            mb: sizeConfig.iconMargin,
            fontSize: sizeConfig.iconFontSize,
            color: 'text.secondary',
          }}
        >
          {icon}
        </Box>
      )}
      <Typography
        variant={sizeConfig.titleVariant}
        sx={{ color: 'text.primary', fontWeight: 600, mb: sizeConfig.titleMargin }}
      >
        {title}
      </Typography>
      {description && (
        <Typography
          variant={sizeConfig.descriptionVariant}
          sx={{ color: 'text.secondary', maxWidth: 320, lineHeight: 1.6 }}
        >
          {description}
        </Typography>
      )}
      {action && <Box sx={{ mt: 3 }}>{action}</Box>}
    </Box>
  )
}

export default EmptyState
