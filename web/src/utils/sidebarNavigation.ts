/** Navigation only: server-side authorization remains the authority. */
export interface SidebarItem { path:string; label:string; icon?:string; external?:boolean }
export interface SidebarGroup { id:string; label:string; icon:string; items:SidebarItem[] }
export const sidebarShortcuts:SidebarItem[]=[
  {path:'/today',label:'今日主页',icon:'home'},
  {path:'/training-calendar',label:'训练日历',icon:'calendar'},
  {path:'/todos',label:'待办事项',icon:'bell'},
  {path:'/coach',label:'Gilo 教练',icon:'chat'},
];
export function sidebarGroups(admin:boolean,devices:boolean):SidebarGroup[]{
  const groups:SidebarGroup[]=[
    {id:'activities',label:'训练记录',icon:'activity',items:[{path:'/dashboard',label:'记录与统计'},{path:'/workout-import',label:'导入训练记录'}]},
    {id:'readiness',label:'状态与恢复',icon:'recovery',items:[{path:'/runner-state',label:'训练状态'},{path:'/training-readiness',label:'负荷与恢复'}]},
    {id:'planning',label:'训练与计划',icon:'plan',items:[{path:'/training-plan',label:'计划总览'},{path:'/workouts',label:'每日课表'},{path:'/cycles',label:'训练周期'},{path:'/blocks',label:'训练周与训练块'},{path:'/ai-plan',label:'AI 制定计划'},{path:'/plan-imports',label:'导入课表'},{path:'/weekly-review',label:'智能周复盘'},{path:'/pace-calculator',label:'配速计算器'},{path:'/pace-rules',label:'配速规则'}]},
    {id:'devices',label:'设备与数据',icon:'device',items:[...(devices?[{path:'/data-sync',label:'连接与同步'},{path:'/data-sync/garmin',label:'Garmin 同步'}]:[]),{path:'/data-management',label:'数据管理'}]},
    {id:'personal',label:'个人与设置',icon:'user',items:[{path:'/my',label:'我的主页'},{path:'/ai-coach-preference',label:'教练偏好'},{path:'/feedback',label:'问题反馈'},{path:'/welcome',label:'使用引导'}]},
  ];
  if(admin)groups.push({id:'administration',label:'管理后台',icon:'settings',items:[{path:'/admin.html#/',label:'管理控制台 ↗',external:true},{path:'/admin/users',label:'用户管理（原入口）'},{path:'/admin/ai-settings',label:'AI 设置（原入口）'},{path:'/admin/system-settings',label:'系统设置'},{path:'/admin/rule-governance',label:'科学规则治理'}]});
  return groups;
}
export function sidebarSelection(path:string,groups:SidebarGroup[]){
  const aliases:Record<string,string>={'/adaptive-weekly-review':'/weekly-review','/garmin-sync':'/data-sync/garmin','/excel-import':'/plan-imports','/plan-import':'/training-plan','/my-training-plan':'/training-plan','/admin':'/admin/users'};
  const normalized=aliases[path] || (/^\/workouts\/[^/]+\/log$/.test(path)?'/workouts':path);
  const group=groups.find(item=>item.items.some(child=>!child.external && child.path===normalized));
  return {activePath:normalized,groupId:group?.id};
}
