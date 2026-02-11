import { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Chip,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import './FileReview.css'
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
