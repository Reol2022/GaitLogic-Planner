export interface PlanTrainingBasis {
  record_count:number; recent_28d_record_count:number;
  recent_4w_avg_recorded_km:number|null; previous_4w_avg_recorded_km:number|null;
  training_days_per_week_28d:number|null; last_training_date:string|null;
  last_record_updated_at:string|null; longest_recorded_activity:{date:string;distance_km:number;source:string}|null;
  complete_for_recorded_data:boolean; sync_coverage_verified:boolean;
  distance_missing_count:number; duplicate_candidate_count:number; unresolved_activity_count:number;
  limitations:string[];
}
export interface PlanContext {
  schema_version:string; as_of_date:string; timezone:string;fingerprint:string;
  runner_facts:{training?:PlanTrainingBasis;last_sync_at?:string|null;last_sync_status?:string|null;performances?:Array<{provenance:string;distance:string;result_seconds:number;updated_at:string}>;recovery?:{freshness:string;missing_fields:string[]}};
  suggestions:Partial<Record<'current_weekly_mileage_km'|'recent_4w_avg_mileage_km',number>>;
  feasibility:Array<{code:string;message:string;severity:string}>;
  hard_constraints?:{available_training_days_per_week:number;fixed_rest_days:string[];can_double_run:boolean;daily_available_minutes:Record<string,number>;excluded_workout_types:string[]};
}
