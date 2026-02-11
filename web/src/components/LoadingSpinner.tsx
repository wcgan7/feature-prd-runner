import './LoadingSpinner.css'

interface Props {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export default function LoadingSpinner({ size = 'md', className = '', label }: Props) {
  const sizeClass = {
    sm: 'loading-spinner-sm',
    md: '',
    lg: 'loading-spinner-lg',
  }[size]

  return (
    <div className={`loading-spinner-container ${className}`}>
      <div className={`loading-spinner ${sizeClass}`} role="status" aria-label={label || 'Loading'} />
      {label && <span className="loading-spinner-label">{label}</span>}
    </div>
  )
}
