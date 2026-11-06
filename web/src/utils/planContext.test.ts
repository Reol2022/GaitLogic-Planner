import {describe,it,expect} from 'vitest';
import {acceptedMileage,mileageSource} from './planContext';
import type {PlanContext} from '@/types/planContext';
describe('Plan Context acceptance',()=>{
  it('only accepts valid known mileage fields and never copies constraints',()=>{
    const context={suggestions:{current_weekly_mileage_km:42,recent_4w_avg_mileage_km:NaN,can_double_run:1,available_training_days_per_week:7}} as unknown as PlanContext;
    expect(acceptedMileage(context)).toEqual({current_weekly_mileage_km:42});
    expect(context.suggestions.recent_4w_avg_mileage_km).toBeNaN();
  });
  it('does not silently replace a user edit and describes provenance',()=>{
    expect(mileageSource(45,undefined)).toBe('用户填写');
    expect(mileageSource(40,40)).toContain('已接受自动统计');
    expect(mileageSource(45,40)).toContain('用户手动修改');
  });
});
