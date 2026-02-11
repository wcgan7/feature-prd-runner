/**
 * Notification bell with a dropdown history panel.
 *
 * Subscribes to the WebSocket `notifications` channel and maintains a
 * persistent list of up to 50 recent notifications. Optionally shows
 * desktop (browser) notifications when permission has been granted.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Badge,
  Box,
  Button,
  Card,
  IconButton,
  Stack,
  Typography,
} from '@mui/material'
import NotificationsIcon from '@mui/icons-material/Notifications'
import { useChannel } from '../../contexts/WebSocketContext'

export interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  timestamp: string
  read: boolean
}

const MAX_NOTIFICATIONS = 50

let _audioCtx: AudioContext | null = null

function playNotificationSound(type: Notification['type'] = 'info') {
  try {
    if (!_audioCtx) {
      _audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    }
    const ctx = _audioCtx
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.connect(gain)
    gain.connect(ctx.destination)

    const freq = type === 'error' ? 440 : type === 'warning' ? 520 : type === 'success' ? 660 : 600
    oscillator.frequency.setValueAtTime(freq, ctx.currentTime)
    oscillator.type = 'sine'
    gain.gain.setValueAtTime(0.08, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3)

    oscillator.start(ctx.currentTime)
    oscillator.stop(ctx.currentTime + 0.3)
  } catch {
    // Audio not available — silently skip
  }
}

function typeIcon(type: Notification['type']): string {
  switch (type) {
    case 'success':
      return '\u2713'
    case 'error':
      return '\u2717'
    case 'warning':
      return '!'
    case 'info':
    default:
      return 'i'
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const seconds = Math.max(0, Math.floor(diff / 1000))

  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)
  const desktopPermRef = useRef<NotificationPermission>(
    typeof window !== 'undefined' && 'Notification' in window
      ? window.Notification.permission
      : 'denied',
  )

  const requestDesktopPermission = useCallback(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) return
    if (desktopPermRef.current !== 'default') return
    window.Notification.requestPermission().then((perm) => {
      desktopPermRef.current = perm
    })
  }, [])

  const showDesktopNotification = useCallback((n: Notification) => {
    if (desktopPermRef.current !== 'granted') return
    try {
      new window.Notification(n.title, {
        body: n.message,
        tag: n.id,
      })
    } catch {
      // Some browsers restrict Notification constructor usage
    }
  }, [])

  useChannel(
    'notifications',
    useCallback(
      (_event: string, data: any) => {
        const incoming: Notification = {
          id: data.id ?? crypto.randomUUID(),
          type: data.type ?? 'info',
          title: data.title ?? 'Notification',
          message: data.message ?? '',
          timestamp: data.timestamp ?? new Date().toISOString(),
          read: false,
        }

        setNotifications((prev) => [incoming, ...prev].slice(0, MAX_NOTIFICATIONS))
        showDesktopNotification(incoming)
        if (soundEnabled) {
          playNotificationSound(incoming.type)
        }
      },
      [showDesktopNotification, soundEnabled],
    ),
  )

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const unreadCount = notifications.filter((n) => !n.read).length

  const handleToggle = () => {
    setOpen((prev) => !prev)
    requestDesktopPermission()
  }

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }

  const clearAll = () => {
    setNotifications([])
    setOpen(false)
  }

  return (
    <Box className="notification-center" ref={containerRef} sx={{ position: 'relative' }}>
      <IconButton
        className="notification-bell-btn"
        onClick={handleToggle}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
        size="small"
      >
        <Badge
          color="error"
          overlap="circular"
          badgeContent={
            unreadCount > 0 ? (
              <span className="notification-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
            ) : null
          }
        >
          <NotificationsIcon className="notification-bell-icon" fontSize="small" />
        </Badge>
      </IconButton>

      {open && (
        <Card
          className="notification-dropdown"
          role="region"
          aria-label="Notifications"
          variant="outlined"
          sx={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 8px)',
            width: 360,
            maxWidth: '80vw',
            zIndex: (theme) => theme.zIndex.modal,
          }}
        >
          <Stack className="notification-dropdown-header" direction="row" justifyContent="space-between" spacing={1} sx={{ p: 1.25, borderBottom: 1, borderColor: 'divider' }}>
            <Typography className="notification-dropdown-title" variant="subtitle2">Notifications</Typography>
            <Stack className="notification-dropdown-actions" direction="row" spacing={0.5}>
              <Button
                className={`notification-action-btn ${soundEnabled ? '' : 'notification-sound-off'}`}
                size="small"
                onClick={() => setSoundEnabled((prev) => !prev)}
                title={soundEnabled ? 'Mute sound alerts' : 'Unmute sound alerts'}
                aria-label={soundEnabled ? 'Mute notifications' : 'Unmute notifications'}
              >
                {soundEnabled ? '\u{1F50A}' : '\u{1F507}'}
              </Button>
              <Button className="notification-action-btn" size="small" onClick={markAllRead} disabled={unreadCount === 0}>
                Mark all read
              </Button>
              <Button className="notification-action-btn" size="small" onClick={clearAll} disabled={notifications.length === 0}>
                Clear all
              </Button>
            </Stack>
          </Stack>

          <Stack className="notification-list" spacing={0} sx={{ maxHeight: 360, overflowY: 'auto' }}>
            {notifications.length === 0 ? (
              <Typography className="notification-empty" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                No notifications
              </Typography>
            ) : (
              notifications.map((n) => (
                <Box
                  key={n.id}
                  className={`notification-item ${n.read ? '' : 'notification-item-unread'} notification-item-${n.type}`}
                  onClick={() =>
                    setNotifications((prev) =>
                      prev.map((item) => (item.id === n.id ? { ...item, read: true } : item)),
                    )
                  }
                  sx={{
                    display: 'flex',
                    gap: 1,
                    alignItems: 'flex-start',
                    p: 1,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    cursor: 'pointer',
                    bgcolor: n.read ? 'transparent' : 'action.hover',
                    '&:last-of-type': { borderBottom: 'none' },
                  }}
                >
                  <Box
                    className={`notification-type-icon notification-type-${n.type}`}
                    sx={{
                      mt: 0.25,
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      color: 'common.white',
                      bgcolor: n.type === 'error' ? 'error.main' : n.type === 'warning' ? 'warning.main' : n.type === 'success' ? 'success.main' : 'info.main',
                      flexShrink: 0,
                    }}
                  >
                    {typeIcon(n.type)}
                  </Box>

                  <Box className="notification-content" sx={{ minWidth: 0, flex: 1 }}>
                    <Typography className="notification-title" variant="body2" sx={{ fontWeight: 700 }}>
                      {n.title}
                    </Typography>
                    <Typography className="notification-message" variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {n.message}
                    </Typography>
                  </Box>

                  <Typography className="notification-time" variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
                    {relativeTime(n.timestamp)}
                  </Typography>
                </Box>
              ))
            )}
          </Stack>
        </Card>
      )}
    </Box>
  )
}
