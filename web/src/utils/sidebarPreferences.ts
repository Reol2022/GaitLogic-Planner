import {sidebarGroups, sidebarShortcuts, type SidebarGroup, type SidebarItem} from './sidebarNavigation';

export interface SidebarPreferences {
  version: 1;
  shortcuts: string[];
  mobileShortcuts: string[];
  hiddenGroups: string[];
  hiddenItems: string[];
  groupOrder: string[];
  itemOrder: Record<string, string[]>;
}
const catalog = sidebarGroups(true, true);
const groupIds = catalog.map(group => group.id);
const paths = [...sidebarShortcuts, ...catalog.flatMap(group => group.items)].map(item => item.path);
const internalPaths = paths.filter(path => !path.includes('#'));
function strings(value: unknown, allowed: string[]) {
  return Array.isArray(value) ? [...new Set(value.filter((item): item is string => typeof item === 'string' && allowed.includes(item)))] : [];
}
export function defaultSidebarPreferences(): SidebarPreferences {
  return {version: 1, shortcuts: sidebarShortcuts.map(item => item.path), mobileShortcuts:['/today','/training-plan','/dashboard','/coach'], hiddenGroups: [], hiddenItems: [], groupOrder: [], itemOrder: {}};
}
export function normalizeSidebarPreferences(value: unknown): SidebarPreferences {
  if (!value || typeof value !== 'object' || (value as {version?: unknown}).version !== 1) return defaultSidebarPreferences();
  const raw = value as Partial<SidebarPreferences>;
  const itemOrder: Record<string, string[]> = {};
  for (const group of catalog) itemOrder[group.id] = strings(raw.itemOrder?.[group.id], group.items.map(item => item.path));
  return {version: 1, shortcuts: Array.isArray(raw.shortcuts) ? strings(raw.shortcuts, internalPaths).slice(0, 6) : defaultSidebarPreferences().shortcuts,
    mobileShortcuts:Array.isArray(raw.mobileShortcuts) ? strings(raw.mobileShortcuts,internalPaths).slice(0,4) : defaultSidebarPreferences().mobileShortcuts,
    hiddenGroups: strings(raw.hiddenGroups, groupIds), hiddenItems: strings(raw.hiddenItems, paths), groupOrder: strings(raw.groupOrder, groupIds), itemOrder};
}
export function configuredMobileNavigation(admin:boolean,devices:boolean,value:SidebarPreferences):SidebarItem[]{
  const preferences=normalizeSidebarPreferences(value);
  return configuredSidebar(admin,devices,{...preferences,shortcuts:preferences.mobileShortcuts}).shortcuts;
}
export function sidebarPreferenceKey(userId: number | null) {
  return userId !== null && Number.isSafeInteger(userId) && userId > 0 ? `gaitlogic:sidebar:${userId}:v1` : null;
}
export function loadSidebarPreferences(userId: number | null): SidebarPreferences {
  const key = sidebarPreferenceKey(userId);
  try { return key ? normalizeSidebarPreferences(JSON.parse(localStorage.getItem(key) || 'null')) : defaultSidebarPreferences(); }
  catch { return defaultSidebarPreferences(); }
}
export function saveSidebarPreferences(userId: number | null, preferences: SidebarPreferences): boolean {
  const key = sidebarPreferenceKey(userId);
  if (!key) return false;
  try { localStorage.setItem(key, JSON.stringify(normalizeSidebarPreferences(preferences))); return true; }
  catch { return false; }
}
export function ordered<T>(items: T[], order: string[], id: (item: T) => string): T[] {
  return [...items].sort((a, b) => {
    const rank = (item: T) => order.includes(id(item)) ? order.indexOf(id(item)) : order.length + items.indexOf(item);
    return rank(a) - rank(b);
  });
}
/** Project preferences onto the authorized catalog, never the other way around. */
export function configuredSidebar(admin: boolean, devices: boolean, value: SidebarPreferences): {shortcuts: SidebarItem[]; groups: SidebarGroup[]} {
  const preferences = normalizeSidebarPreferences(value);
  const available = sidebarGroups(admin, devices);
  const choices = [...sidebarShortcuts, ...available.flatMap(group => group.items).filter(item => !item.external)];
  const shortcuts = preferences.shortcuts.flatMap(path => {
    const item = choices.find(candidate => candidate.path === path);
    return item ? [{...item, icon: item.icon || available.find(group => group.items.some(child => child.path === path))?.icon || 'home'}] : [];
  });
  const groups = ordered(available, preferences.groupOrder, group => group.id)
    .filter(group => !preferences.hiddenGroups.includes(group.id))
    .map(group => ({...group, items: ordered(group.items, preferences.itemOrder[group.id] || [], item => item.path).filter(item => !preferences.hiddenItems.includes(item.path) && !shortcuts.some(shortcut => shortcut.path === item.path))}))
    .filter(group => group.items.length > 0);
  return {shortcuts, groups};
}
