import {describe,it,expect} from 'vitest';
import {aiPlanCalendar} from './aiPlanCalendar';

describe('AI plan calendar',()=>{
  it('94 days creates 14 training weeks with a 3-day final week, not a conflict',()=>{
    const result=aiPlanCalendar('2026-11-09',14,'2027-02-10');
    expect(result.endDate).toBe('2027-02-10');expect(result.error).toBe('');
    expect(result.recommendedWeeks).toBe(14);expect(result.lastWeekDays).toBe(3);
    expect(result.summary).toContain('共 94 天');expect(result.summary).toContain('最后一周 3 天');
  });
  it('explains excessive weeks with exact dates and an action',()=>{
    const result=aiPlanCalendar('2026-11-09',15,'2027-02-10');
    expect(result.error).toContain('当前填写 15 周');expect(result.error).toContain('最多可安排 14');
    expect(result.error).toContain('按赛事匹配周数');
  });
  it.each([
    ['2026-11-09',1,'2026-11-09',1],['2026-11-09',1,'2026-11-15',7],
    ['2026-11-09',2,'2026-11-16',1],['2028-02-28',1,'2028-03-01',3],
    ['2026-03-07',1,'2026-03-09',3],
  ])('handles same-day, exact weeks, leap day and DST civil dates', (start,weeks,race,last)=>{
    const result=aiPlanCalendar(start,weeks,race);expect(result.endDate).toBe(race);
    expect(result.lastWeekDays).toBe(last);expect(result.error).toBe('');
  });
  it('keeps stage plans valid and explains incomplete race coverage',()=>{
    const result=aiPlanCalendar('2026-11-09',8,'2027-06-01');
    expect(result.endDate).toBe('2027-01-03');expect(result.recommendedWeeks).toBe(16);
    expect(result.summary).toContain('阶段计划');expect(result.error).toBe('');
  });
  it('rejects a race before the start and keeps no-race full weeks',()=>{
    expect(aiPlanCalendar('2026-11-09',8,'2026-11-08').error).toContain('早于');
    expect(aiPlanCalendar('2026-11-09',8).endDate).toBe('2027-01-03');
  });
  it('explains missing or invalid dates and week counts before generation',()=>{
    expect(aiPlanCalendar('',8).error).toContain('开始日期');
    expect(aiPlanCalendar('2026-02-30',8).error).toContain('开始日期');
    expect(aiPlanCalendar('2026-11-09',0).error).toContain('整数');
    expect(aiPlanCalendar('2026-11-09',1.5).error).toContain('整数');
    expect(aiPlanCalendar('2026-11-09',8,'2027-02-30').error).toContain('赛事日期');
  });
});
