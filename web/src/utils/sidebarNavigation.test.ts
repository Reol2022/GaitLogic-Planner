import {describe,it,expect} from 'vitest';
import {sidebarGroups,sidebarSelection,sidebarShortcuts} from './sidebarNavigation';
describe('GaitLogic grouped navigation',()=>{
  it('keeps admin and provider gates',()=>{
    const ordinary=sidebarGroups(false,false);
    expect(ordinary.some(g=>g.id==='administration')).toBe(false);
    expect(ordinary.flatMap(g=>g.items).some(i=>i.path==='/data-sync/garmin')).toBe(false);
    expect(ordinary.flatMap(g=>g.items).some(i=>i.path==='/data-management')).toBe(true);
    expect(sidebarGroups(true,true).flatMap(g=>g.items).some(i=>i.external && i.path==='/admin.html#/')).toBe(true);
  });
  it('selects the actual leaf and opens its group for deep links',()=>{
    const groups=sidebarGroups(true,true);
    expect(sidebarSelection('/workouts/123/log',groups)).toEqual({activePath:'/workouts',groupId:'planning'});
    expect(sidebarSelection('/data-sync/garmin',groups)).toEqual({activePath:'/data-sync/garmin',groupId:'devices'});
    expect(sidebarSelection('/adaptive-weekly-review',groups).groupId).toBe('planning');
    expect(sidebarSelection('/ai-coach-preference',groups).groupId).toBe('personal');
  });
  it('does not invent fitness or social features and keeps calendar a shortcut',()=>{
    expect(sidebarShortcuts.some(i=>i.path==='/training-calendar')).toBe(true);
    const names=sidebarGroups(false,true).map(g=>g.label).join(' ');
    expect(names).not.toMatch(/营养|朋友|群组|挑战/);
  });
});
