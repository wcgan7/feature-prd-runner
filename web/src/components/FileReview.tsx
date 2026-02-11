import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Chip,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useToast } from '../contexts/ToastContext'
import EmptyState from './EmptyState'
import LoadingSpinner from './LoadingSpinner'

interface FileChange {
  file_path: string
  status: string
  additions: number
  deletions: number
  diff: string
  approved: boolean | null
  comments: string[]
}

interface FileReviewProps {
  taskId?: string
  projectDir?: string
}

const FILE_REVIEW_STYLES = `
.file-review {
  background: var(--color-bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-6);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--spacing-6);
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-6);
  flex-wrap: wrap;
  gap: var(--spacing-4);
}

.review-header h2 {
  margin: 0;
  font-size: var(--text-xl);
}

.review-stats {
  display: flex;
  gap: var(--spacing-4);
  font-size: var(--text-sm);
}

.stat {
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-xl);
  font-weight: var(--font-semibold);
}

.stat.approved {
  background: var(--color-success-100);
  color: var(--color-success-700);
}

.stat.rejected {
  background: var(--color-error-100);
  color: var(--color-error-700);
}

.stat.pending {
  background: var(--color-warning-100);
  color: var(--color-warning-700);
}

.stat.total {
  background: var(--color-primary-100);
  color: var(--color-primary-700);
}

.loading,
.error,
.empty-state {
  padding: var(--spacing-8);
  text-align: center;
  color: var(--color-text-secondary);
}

.error {
  color: var(--color-error-500);
}

.review-container {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: var(--spacing-6);
  height: 600px;
}

.file-list {
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  overflow-y: auto;
  background: var(--color-bg-secondary);
}

.file-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  border-bottom: 1px solid var(--color-border-default);
  cursor: pointer;
  transition: background var(--transition-base);
  position: relative;
}

.file-item:hover {
  background: var(--color-bg-tertiary);
}

.file-item.selected {
  background: var(--color-primary-50);
  border-left: 4px solid var(--color-primary-500);
}

.file-item.approved {
  border-left: 4px solid var(--color-success-500);
}

.file-item.rejected {
  border-left: 4px solid var(--color-error-500);
}

.file-status {
  flex-shrink: 0;
}

.status-icon {
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  color: var(--color-text-inverse);
  font-weight: var(--font-bold);
  text-align: center;
  line-height: 24px;
  font-size: var(--text-sm);
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-changes {
  display: flex;
  gap: var(--spacing-2);
  font-size: var(--text-xs);
  margin-top: var(--spacing-1);
}

.additions {
  color: var(--color-success-700);
  font-weight: var(--font-semibold);
}

.deletions {
  color: var(--color-error-700);
  font-weight: var(--font-semibold);
}

.review-badge {
  position: absolute;
  top: var(--spacing-2);
  right: var(--spacing-2);
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
}

.file-item.approved .review-badge {
  background: var(--color-success-500);
  color: var(--color-text-inverse);
}

.file-item.rejected .review-badge {
  background: var(--color-error-500);
  color: var(--color-text-inverse);
}

.file-detail {
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  background: var(--color-bg-secondary);
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--color-border-default);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.file-path-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.status-badge {
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-sm);
  color: var(--color-text-inverse);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
}

.file-path {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.change-stats {
  display: flex;
  gap: var(--spacing-4);
}

.diff-container {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg-secondary);
}

.diff-view {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: var(--leading-snug);
}

.diff-line {
  padding: 0 var(--spacing-3);
  white-space: pre;
  overflow-x: auto;
}

.diff-line.addition {
  background: var(--color-success-50);
  color: var(--color-text-primary);
}

.diff-line.deletion {
  background: var(--color-error-50);
  color: var(--color-text-primary);
}

.diff-line.hunk {
  background: var(--color-primary-50);
  color: var(--color-text-secondary);
  font-weight: var(--font-semibold);
}

.no-diff {
  padding: var(--spacing-8);
  text-align: center;
  color: var(--color-text-secondary);
}

.review-actions {
  padding: var(--spacing-4);
  border-top: 1px solid var(--color-border-default);
  background: var(--color-bg-primary);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.comment-input {
  width: 100%;
  padding: var(--spacing-3);
  border: 1px solid var(--color-border-default);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: var(--text-sm);
  resize: vertical;
}

.comment-input:focus {
  outline: none;
  border-color: var(--color-primary-500);
  box-shadow: 0 0 0 3px var(--color-primary-100);
}

.comment-input:disabled {
  background: var(--color-bg-secondary);
  cursor: not-allowed;
}

.action-buttons {
  display: flex;
  gap: var(--spacing-3);
  justify-content: flex-end;
}

.approve-btn,
.reject-btn {
  padding: var(--spacing-3) var(--spacing-6);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  cursor: pointer;
  transition: all var(--transition-base);
}

.approve-btn {
  background: var(--color-success-500);
  color: var(--color-text-inverse);
}

.approve-btn:hover:not(:disabled) {
  background: var(--color-success-600);
}

.reject-btn {
  background: var(--color-error-500);
  color: var(--color-text-inverse);
}

.reject-btn:hover:not(:disabled) {
  background: var(--color-error-600);
}

.approve-btn:disabled,
.reject-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.navigation-buttons {
  padding: var(--spacing-4);
  border-top: 1px solid var(--color-border-default);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--color-bg-tertiary);
}

.navigation-buttons button {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--color-primary-500);
  color: var(--color-text-inverse);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: background var(--transition-base);
}

.navigation-buttons button:hover:not(:disabled) {
  background: var(--color-primary-600);
}

.navigation-buttons button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--color-gray-400);
}

.file-counter {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

@media (max-width: 1024px) {
  .review-container {
    grid-template-columns: 1fr;
    height: auto;
  }

  .file-list {
    max-height: 300px;
  }

  .diff-container {
    max-height: 400px;
  }
}

@media (max-width: 768px) {
  .review-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .review-stats {
    flex-wrap: wrap;
  }

  .action-buttons {
    flex-direction: column;
  }

  .approve-btn,
  .reject-btn {
    width: 100%;
  }
}
`

const FileReview = ({ taskId, projectDir }: FileReviewProps) => {
  const [files, setFiles] = useState<FileChange[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<number>(0)
  const [comments, setComments] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState<string | null>(null)
  const toast = useToast()

  useEffect(() => {
    fetchFileChanges()
  }, [taskId, projectDir])

  const fetchFileChanges = async () => {
    try {
      const params = new URLSearchParams()
      if (projectDir) params.append('project_dir', projectDir)
      if (taskId) params.append('task_id', taskId)

      const headers: HeadersInit = {}
      const token = localStorage.getItem('feature-prd-runner-auth-token')
      if (token) headers.Authorization = `Bearer ${token}`

      const response = await fetch(`/api/file-changes?${params}`, { headers })
      if (!response.ok) throw new Error(`HTTP error ${response.status}`)

      const data = await response.json()
      setFiles(Array.isArray(data) ? data : [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch file changes')
    } finally {
      setLoading(false)
    }
  }

  const handleReview = async (filePath: string, approved: boolean) => {
    setSubmitting(filePath)

    try {
      const params = new URLSearchParams()
      if (projectDir) params.append('project_dir', projectDir)

      const headers: HeadersInit = { 'Content-Type': 'application/json' }
      const token = localStorage.getItem('feature-prd-runner-auth-token')
      if (token) headers.Authorization = `Bearer ${token}`

      const response = await fetch(`/api/file-review?${params}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          file_path: filePath,
          approved,
          comment: comments[filePath] || null,
        }),
      })

      if (!response.ok) throw new Error(`HTTP error ${response.status}`)

      setFiles(files.map((f) => (f.file_path === filePath ? { ...f, approved } : f)))
      setComments((prev) => {
        const updated = { ...prev }
        delete updated[filePath]
        return updated
      })

      toast.success(approved ? 'File approved' : 'File rejected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to submit review')
    } finally {
      setSubmitting(null)
    }
  }

  const handleCommentChange = (filePath: string, value: string) => {
    setComments((prev) => ({ ...prev, [filePath]: value }))
  }

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'added': return '#4caf50'
      case 'modified': return '#2196f3'
      case 'deleted': return '#f44336'
      default: return '#9e9e9e'
    }
  }

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'added': return '+'
      case 'modified': return '~'
      case 'deleted': return '-'
      default: return '?'
    }
  }

  const renderDiff = (diff: string) => {
    if (!diff) return <div className="no-diff">No diff available</div>

    return (
      <div className="diff-view">
        {diff.split('\n').map((line, idx) => {
          let className = 'diff-line'
          if (line.startsWith('+') && !line.startsWith('+++')) className += ' addition'
          else if (line.startsWith('-') && !line.startsWith('---')) className += ' deletion'
          else if (line.startsWith('@@')) className += ' hunk'

          return (
            <div key={idx} className={className}>
              {line || ' '}
            </div>
          )
        })}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="file-review">
        <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.5 }}>File Review</Typography>
        <LoadingSpinner label="Loading file changes..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="file-review">
        <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.5 }}>File Review</Typography>
        <EmptyState
          icon={<span>⚠️</span>}
          title="Error loading files"
          description={error}
          size="sm"
        />
      </div>
    )
  }

  if (files.length === 0) {
    return (
      <div className="file-review">
        <Typography variant="h2" sx={{ fontSize: '1.125rem', mb: 1.5 }}>File Review</Typography>
        <EmptyState
          icon={<span>📁</span>}
          title="No file changes to review"
          description="File changes will appear here when they are ready for review."
          size="sm"
        />
      </div>
    )
  }

  const currentFile = files[selectedFile]
  const approvedCount = files.filter((f) => f.approved === true).length
  const rejectedCount = files.filter((f) => f.approved === false).length
  const pendingCount = files.filter((f) => f.approved === null).length

  return (
    <div className="file-review">
      <style>{FILE_REVIEW_STYLES}</style>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} className="review-header" spacing={1} sx={{ mb: 1.5 }}>
        <Typography variant="h2" sx={{ fontSize: '1.125rem' }}>File Review</Typography>
        <Stack direction="row" spacing={0.75} className="review-stats" useFlexGap flexWrap="wrap">
          <Chip className="stat approved" size="small" color="success" variant="outlined" label={`✓ ${approvedCount}`} />
          <Chip className="stat rejected" size="small" color="error" variant="outlined" label={`✗ ${rejectedCount}`} />
          <Chip className="stat pending" size="small" color="warning" variant="outlined" label={`⏳ ${pendingCount}`} />
          <Chip className="stat total" size="small" variant="outlined" label={`Total: ${files.length}`} />
        </Stack>
      </Stack>

      <div className="review-container">
        <div className="file-list">
          {files.map((file, idx) => (
            <Box
              key={file.file_path}
              className={`file-item ${idx === selectedFile ? 'selected' : ''} ${file.approved === true ? 'approved' : file.approved === false ? 'rejected' : ''}`}
              onClick={() => setSelectedFile(idx)}
              sx={{
                border: 1,
                borderColor: idx === selectedFile ? 'primary.main' : 'divider',
                borderRadius: 1,
                p: 1,
                cursor: 'pointer',
                mb: 0.75,
                bgcolor: idx === selectedFile ? 'action.selected' : 'background.default',
              }}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <div className="file-status">
                  <span className="status-icon" style={{ backgroundColor: getStatusColor(file.status) }}>
                    {getStatusIcon(file.status)}
                  </span>
                </div>
                <div className="file-info" style={{ flex: 1 }}>
                  <div className="file-name">{file.file_path}</div>
                  <div className="file-changes">
                    <span className="additions">+{file.additions}</span>
                    <span className="deletions">-{file.deletions}</span>
                  </div>
                </div>
                {file.approved !== null && <div className="review-badge">{file.approved ? '✓' : '✗'}</div>}
              </Stack>
            </Box>
          ))}
        </div>

        <div className="file-detail">
          <Stack direction="row" justifyContent="space-between" alignItems="center" className="detail-header" sx={{ mb: 1 }}>
            <div className="file-path-header">
              <span className="status-badge" style={{ backgroundColor: getStatusColor(currentFile.status) }}>
                {currentFile.status}
              </span>
              <span className="file-path">{currentFile.file_path}</span>
            </div>
            <div className="change-stats">
              <span className="additions">+{currentFile.additions}</span>
              <span className="deletions">-{currentFile.deletions}</span>
            </div>
          </Stack>

          <div className="diff-container">{renderDiff(currentFile.diff)}</div>

          <div className="review-actions">
            <TextField
              className="comment-input"
              placeholder="Add optional comment..."
              value={comments[currentFile.file_path] || ''}
              onChange={(e) => handleCommentChange(currentFile.file_path, e.target.value)}
              disabled={submitting === currentFile.file_path}
              multiline
              minRows={2}
              fullWidth
            />
            <Stack direction="row" spacing={1} className="action-buttons" sx={{ mt: 1 }}>
              <Button
                className="reject-btn"
                variant="outlined"
                color="error"
                onClick={() => handleReview(currentFile.file_path, false)}
                disabled={submitting === currentFile.file_path}
              >
                {submitting === currentFile.file_path ? 'Processing...' : '✗ Reject'}
              </Button>
              <Button
                className="approve-btn"
                variant="contained"
                color="success"
                onClick={() => handleReview(currentFile.file_path, true)}
                disabled={submitting === currentFile.file_path}
              >
                {submitting === currentFile.file_path ? 'Processing...' : '✓ Approve'}
              </Button>
            </Stack>
          </div>

          <div className="navigation-buttons">
            <Button
              onClick={() => setSelectedFile(Math.max(0, selectedFile - 1))}
              disabled={selectedFile === 0}
              variant="outlined"
              size="small"
            >
              ← Previous
            </Button>
            <span className="file-counter">File {selectedFile + 1} of {files.length}</span>
            <Button
              onClick={() => setSelectedFile(Math.min(files.length - 1, selectedFile + 1))}
              disabled={selectedFile === files.length - 1}
              variant="outlined"
              size="small"
            >
              Next →
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default FileReview
