import { ReactNode } from 'react'
import './EmptyState.css'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}

function EmptyState({ icon, title, description, action, size = 'md' }: EmptyStateProps) {
  return (
    <div className={`empty-state empty-state-${size}`}>
      {icon && <div className="empty-state-icon">{icon}</div>}
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-description">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  )
}

export default EmptyState
