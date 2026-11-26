import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

const storageKey = 'gaitlogic.mobile.appearance.v1'
export const darkTheme = ref(true)
let restored = false

function restoreTheme(): void {
  if (restored || typeof uni === 'undefined') return
  try {
    darkTheme.value = uni.getStorageSync(storageKey) !== 'light'
    restored = true
  } catch { /* Local storage is optional; default to dark. */ }
}

function syncChrome(tab: boolean): void {
  if (typeof uni === 'undefined') return
  const dark = darkTheme.value
  if (typeof uni.setNavigationBarColor === 'function') {
    uni.setNavigationBarColor({ frontColor: dark ? '#ffffff' : '#000000', backgroundColor: dark ? '#111419' : '#f3f6f9' })
  }
  if (tab && typeof uni.setTabBarStyle === 'function') {
    uni.setTabBarStyle({ color: dark ? '#afbdcd' : '#526477', selectedColor: dark ? '#8ac7ff' : '#0d5fb3', backgroundColor: dark ? '#1b232d' : '#ffffff', borderStyle: dark ? 'black' : 'white' })
  }
}

export function useTheme(tab: boolean = false) {
  restoreTheme()
  onShow(() => { restoreTheme(); syncChrome(tab) })
  return computed(() => darkTheme.value ? 'theme-dark' : 'theme-light')
}

export function setDarkTheme(enabled: boolean): boolean {
  try { uni.setStorageSync(storageKey, enabled ? 'dark' : 'light') }
  catch { return false }
  restored = true
  darkTheme.value = enabled
  syncChrome(false)
  return true
}
