interface TouchPoint { clientX: number; clientY: number }
export interface TouchInput { touches: ArrayLike<TouchPoint>; changedTouches: ArrayLike<TouchPoint> }

export function swipeHandlers(onSwipe: (direction: number) => void) {
  let start: TouchPoint | null = null
  function cancel() { start = null }
  return {
    cancel,
    start(event: TouchInput) {
      cancel()
      const point = event.touches[0]
      if (event.touches.length === 1 && point) {
        start = { clientX: point.clientX, clientY: point.clientY }
      }
    },
    move(event: TouchInput) {
      if (event.touches.length !== 1) cancel()
      const point = event.touches[0]
      if (!start || !point) return
      const dx = Math.abs(point.clientX - start.clientX)
      const dy = Math.abs(point.clientY - start.clientY)
      if (dy > 16 && dy >= dx) cancel()
    },
    end(event: TouchInput) {
      const first = start
      cancel()
      const point = event.changedTouches[0]
      if (!first || !point || event.touches.length !== 0 || event.changedTouches.length !== 1) return
      const dx = point.clientX - first.clientX
      const dy = point.clientY - first.clientY
      if (Math.abs(dx) >= 52 && Math.abs(dx) > Math.abs(dy) * 1.5) onSwipe(dx < 0 ? 1 : -1)
    },
  }
}

export const mainTabs = ['/pages/today/index', '/pages/training/index', '/pages/coach/index', '/pages/workspace/index', '/pages/profile/index']

export function tabSwipe(current: string, switchTab: (path: string) => void) {
  return swipeHandlers(direction => {
    const index = mainTabs.indexOf(current)
    const target = mainTabs[index + direction]
    if (index >= 0 && target) switchTab(target)
  })
}
