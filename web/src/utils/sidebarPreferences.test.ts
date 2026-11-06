import {beforeEach,describe,it,expect,vi} from 'vitest';
import {configuredMobileNavigation,configuredSidebar,defaultSidebarPreferences,loadSidebarPreferences,normalizeSidebarPreferences,saveSidebarPreferences,sidebarPreferenceKey} from './sidebarPreferences';
describe('sidebar user preferences',()=>{
  beforeEach(()=>{vi.restoreAllMocks();localStorage.clear();});
  it('restores defaults for corrupt and future formats',()=>{
    localStorage.setItem(sidebarPreferenceKey(1)!, '{broken');
    expect(loadSidebarPreferences(1)).toEqual(defaultSidebarPreferences());
    expect(normalizeSidebarPreferences({version:99})).toEqual(defaultSidebarPreferences());
  });
  it('only accepts catalog IDs, bounded unique shortcuts and safe item order',()=>{
    const prefs=normalizeSidebarPreferences({version:1,shortcuts:['/coach','/coach','https://evil.test','/admin.html#/','/today'],hiddenGroups:['planning','fake'],hiddenItems:['/today','javascript:alert(1)'],itemOrder:{planning:['/cycles','/cycles','/admin/users']}});
    expect(prefs.shortcuts).toEqual(['/coach','/today']);expect(prefs.hiddenGroups).toEqual(['planning']);
    expect(prefs.hiddenItems).toEqual(['/today']);expect(prefs.itemOrder.planning).toEqual(['/cycles']);
    expect(normalizeSidebarPreferences({version:1,shortcuts:['/today','/coach','/todos','/cycles','/blocks','/dashboard','/workouts']}).shortcuts).toHaveLength(6);
  });
  it('keeps per-user data separate and never persists an anonymous preference',()=>{
    const prefs=defaultSidebarPreferences();prefs.hiddenGroups=['planning'];
    expect(saveSidebarPreferences(1,prefs)).toBe(true);expect(loadSidebarPreferences(1).hiddenGroups).toEqual(['planning']);
    expect(loadSidebarPreferences(2).hiddenGroups).toEqual([]);expect(saveSidebarPreferences(null,prefs)).toBe(false);
    expect(sidebarPreferenceKey(-1)).toBeNull();
  });
  it('fails safely when browser storage is unavailable',()=>{
    vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('denied');});
    vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('denied');});
    expect(loadSidebarPreferences(1)).toEqual(defaultSidebarPreferences());expect(saveSidebarPreferences(1,defaultSidebarPreferences())).toBe(false);
  });
  it('cannot use saved preferences to enable admin or device features',()=>{
    const prefs=defaultSidebarPreferences();prefs.shortcuts=['/admin/users','/data-sync/garmin','/coach'];prefs.groupOrder=['administration','devices'];
    const projected=configuredSidebar(false,false,prefs);
    expect(projected.shortcuts.map(item=>item.path)).toEqual(['/coach']);
    expect(projected.groups.some(group=>group.id==='administration')).toBe(false);
    expect(projected.groups.flatMap(group=>group.items).some(item=>item.path==='/data-sync/garmin')).toBe(false);
  });
  it('orders groups and children, hides items, removes empty groups and avoids duplicate menu IDs',()=>{
    const prefs=defaultSidebarPreferences();prefs.shortcuts=['/cycles'];prefs.groupOrder=['planning','readiness'];prefs.itemOrder={planning:['/blocks','/workouts']};prefs.hiddenItems=['/ai-plan'];prefs.hiddenGroups=['activities'];
    const projected=configuredSidebar(false,true,prefs);
    expect(projected.groups[0].id).toBe('planning');expect(projected.groups[0].items.slice(0,2).map(item=>item.path)).toEqual(['/blocks','/workouts']);
    expect(projected.groups.flatMap(group=>group.items).map(item=>item.path)).not.toContain('/cycles');
    expect(projected.groups.flatMap(group=>group.items).map(item=>item.path)).not.toContain('/ai-plan');
    expect(projected.groups.some(group=>group.id==='activities')).toBe(false);
    prefs.hiddenItems=['/data-management'];expect(configuredSidebar(false,false,prefs).groups.some(group=>group.id==='devices')).toBe(false);
  });
  it('reset restores defaults and newly introduced catalog entries remain visible',()=>{
    const prefs=normalizeSidebarPreferences({version:1,shortcuts:[],groupOrder:['planning'],itemOrder:{planning:['/cycles']}});
    expect(configuredSidebar(false,true,prefs).groups[0].items.some(item=>item.path==='/weekly-review')).toBe(true);
    saveSidebarPreferences(1,prefs);saveSidebarPreferences(1,defaultSidebarPreferences());expect(loadSidebarPreferences(1).shortcuts).toEqual(defaultSidebarPreferences().shortcuts);
  });
  it('migrates existing saved menus without changing desktop preferences',()=>{
    const prefs=normalizeSidebarPreferences({version:1,shortcuts:['/coach'],hiddenGroups:['activities']});
    expect(prefs.mobileShortcuts).toEqual(['/today','/training-plan','/dashboard','/coach']);
    expect(prefs.shortcuts).toEqual(['/coach']);expect(prefs.hiddenGroups).toEqual(['activities']);
  });
  it('bounds mobile shortcuts, respects order and never enables unauthorized features',()=>{
    const prefs=normalizeSidebarPreferences({version:1,mobileShortcuts:['/coach','/coach','/admin/users','/data-sync/garmin','/weekly-review','/today','https://evil.test']});
    expect(prefs.mobileShortcuts).toEqual(['/coach','/admin/users','/data-sync/garmin','/weekly-review']);
    expect(configuredMobileNavigation(false,false,prefs).map(item=>item.path)).toEqual(['/coach','/weekly-review']);
  });
  it('allows an empty mobile selection and persists it without hiding the fixed more entry',()=>{
    const prefs=defaultSidebarPreferences();prefs.mobileShortcuts=[];saveSidebarPreferences(1,prefs);
    expect(configuredMobileNavigation(false,true,loadSidebarPreferences(1))).toEqual([]);
    expect(loadSidebarPreferences(2).mobileShortcuts).toHaveLength(4);
  });
});
