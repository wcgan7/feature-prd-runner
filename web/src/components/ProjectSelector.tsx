import { useState, useEffect } from 'react'
import './ProjectSelector.css'

interface Project {
  name: string
  path: string
  status: string
  last_run: string | null
  phases_total: number
  phases_completed: number
}

interface Props {
  currentProject: string | null
  onProjectChange: (projectPath: string) => void
}

export default function ProjectSelector({ currentProject, onProjectChange }: Props) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showDropdown, setShowDropdown] = useState(false)

  useEffect(() => {
    fetchProjects()
  }, [])

  const fetchProjects = async () => {
    try {
      const response = await fetch('/api/projects')
      if (response.ok) {
        const data = await response.json()
        setProjects(Array.isArray(data) ? data : [])
      }
    } catch (err) {
      console.error('Failed to fetch projects:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleProjectSelect = (projectPath: string) => {
    onProjectChange(projectPath)
    setShowDropdown(false)
  }

  const getCurrentProjectName = () => {
    if (!currentProject) return 'No project selected'
    const project = projects.find((p) => p.path === currentProject)
    return project ? project.name : currentProject.split('/').pop() || 'Unknown'
  }

  const getStatusClass = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'active':
        return 'active'
      case 'idle':
        return 'idle'
      case 'error':
        return 'error'
      default:
        return 'default'
    }
  }

  if (loading) {
    return <div className="project-selector-loading">Loading projects...</div>
  }

  if (projects.length === 0) {
    return <div className="project-selector-empty">No projects found</div>
  }

  return (
    <div className="project-selector">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="project-selector-trigger"
      >
        <span className="project-selector-icon">📁</span>
        <span>{getCurrentProjectName()}</span>
        <span className="project-selector-chevron">▼</span>
      </button>

      {showDropdown && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setShowDropdown(false)}
            className="project-selector-backdrop"
          />

          {/* Dropdown */}
          <div className="project-selector-dropdown">
            {projects.map((project) => (
              <div
                key={project.path}
                onClick={() => handleProjectSelect(project.path)}
                className={`project-item ${project.path === currentProject ? 'active' : ''}`}
              >
                <div className="project-item-content">
                  <div className="project-item-main">
                    <div className="project-item-header">
                      <span className="project-item-name">{project.name}</span>
                      <div
                        className={`project-item-status ${getStatusClass(project.status)}`}
                      />
                    </div>
                    <div className="project-item-path">{project.path}</div>
                    {project.phases_total > 0 && (
                      <div className="project-item-progress">
                        {project.phases_completed} / {project.phases_total} phases completed
                      </div>
                    )}
                  </div>
                  {project.path === currentProject && (
                    <div className="project-item-badge">Active</div>
                  )}
                </div>
              </div>
            ))}

            <div className="project-selector-footer">
              {projects.length} project{projects.length !== 1 ? 's' : ''} found
            </div>
          </div>
        </>
      )}
    </div>
  )
}
