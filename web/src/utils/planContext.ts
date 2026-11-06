import type {PlanContext} from '@/types/planContext';
export function acceptedMileage(context:PlanContext){
  return Object.fromEntries(Object.entries(context.suggestions).filter(([key,value])=>['current_weekly_mileage_km','recent_4w_avg_mileage_km'].includes(key) && typeof value==='number' && Number.isFinite(value) && value>=0 && value<=300));
}
export function mileageSource(value:number,accepted:number|undefined){
  return accepted===undefined?'用户填写':value===accepted?'已接受自动统计（已记录数据）':'用户手动修改，覆盖已接受的表单值；原始训练事实不变';
}
