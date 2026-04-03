import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { getUnreadCount, getInAppNotifications, markAsRead, markAllAsRead, InAppNotification } from '../services/notifications'

export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<InAppNotification[]>([])
  const [loading, setLoading] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Poll unread count every 30 s
  useEffect(() => {
    let mounted = true
    const fetchCount = async () => {
      try {
        const count = await getUnreadCount()
        if (mounted) setUnread(count)
      } catch {
        // silently ignore — user may not be logged in yet
      }
    }
    fetchCount()
    const id = setInterval(fetchCount, 30_000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  async function openDropdown() {
    setOpen((v) => !v)
    if (!open) {
      setLoading(true)
      try {
        const items = await getInAppNotifications(false, 20)
        setNotifications(items)
        setUnread(items.filter((n) => !n.is_read).length)
      } finally {
        setLoading(false)
      }
    }
  }

  async function handleMarkRead(id: string) {
    await markAsRead(id)
    setNotifications((prev) =>
      prev.map((n) => (n.notification_id === id ? { ...n, is_read: true } : n))
    )
    setUnread((c) => Math.max(0, c - 1))
  }

  async function handleMarkAll() {
    await markAllAsRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnread(0)
  }

  const typeColors: Record<string, string> = {
    info: 'bg-blue-50 border-blue-200',
    success: 'bg-green-50 border-green-200',
    warning: 'bg-yellow-50 border-yellow-200',
    error: 'bg-red-50 border-red-200',
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={openDropdown}
        className="relative p-2 rounded-full hover:bg-gray-100 focus:outline-none"
        aria-label="Notifications"
      >
        {/* Bell icon (inline SVG) */}
        <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unread > 0 && (
          <span className="absolute top-1 right-1 inline-flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-red-500 rounded-full">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-50" style={{ width: 420 }}>
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <span className="font-semibold text-gray-800">Notifications</span>
            {unread > 0 && (
              <button
                onClick={handleMarkAll}
                className="text-xs text-blue-600 hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-gray-100">
            {loading && (
              <div className="px-4 py-6 text-center text-sm text-gray-500">Loading…</div>
            )}
            {!loading && notifications.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-gray-500">No notifications</div>
            )}
            {!loading &&
              notifications.map((n) => (
                <div
                  key={n.notification_id}
                  className={`px-4 py-3 flex gap-3 ${n.is_read ? 'opacity-60' : ''} ${typeColors[n.type] || ''} border-l-4`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{n.title}</p>
                    <p className="text-xs text-gray-600 mt-0.5">{n.message}</p>
                    {n.related_workflow_id && (
                      <Link
                        href={`/approvals?highlight=${n.related_workflow_id}`}
                        className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                        onClick={() => setOpen(false)}
                      >
                        View approval →
                      </Link>
                    )}
                  </div>
                  {!n.is_read && (
                    <button
                      onClick={() => handleMarkRead(n.notification_id)}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#9ca3af',
                        padding: '0 2px',
                        fontSize: 14,
                        lineHeight: 1,
                        flexShrink: 0,
                      }}
                      title="Mark as read"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
