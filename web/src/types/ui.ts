export interface GlobalStatusSummary {
  rawStatus: string
  label: string
  severity: 'success' | 'warning' | 'error' | 'info' | 'default'
  color: 'success' | 'warning' | 'error' | 'info' | 'default' | 'primary'
  icon: string
}
