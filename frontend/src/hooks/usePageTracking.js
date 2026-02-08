import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../api/client'

export function usePageTracking() {
  const { pathname } = useLocation()
  const prev = useRef(null)

  useEffect(() => {
    if (pathname === prev.current) return
    prev.current = pathname

    // Extract author_id from /author/:id paths
    const match = pathname.match(/^\/author\/([^/]+)/)
    const authorId = match ? match[1] : null

    api.trackVisit(pathname, authorId)
  }, [pathname])
}
