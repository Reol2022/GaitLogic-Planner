// Browser acceptance with synthetic API responses, never a real provider/account.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const output=process.env.UI_ARTIFACT_DIR;if(!output)throw new Error('Private UI_ARTIFACT_DIR required');
const base=process.env.UI_BASE_URL || 'http://127.0.0.1:5189';
(async()=>{fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({channel:'msedge',headless:true});
try{for(const [name,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
 const context=await browser.newContext({viewport});const page=await context.newPage();const errors=[];let generated=null,applyBody=null,applyFail=false;
 page.on('pageerror',error=>errors.push(error.message));
 await context.addInitScript(()=>{localStorage.setItem('gaitlogic_access_token',`header.${btoa(JSON.stringify({sub:'101'}))}.signature`);localStorage.setItem('gaitlogic:experience:101:welcome-dismissed','1');});
 const basis={schema_version:'2.0',as_of_date:'2026-11-06',timezone:'Asia/Shanghai',fingerprint:'synthetic',suggestions:{current_weekly_mileage_km:35,recent_4w_avg_mileage_km:35},feasibility:[],runner_facts:{last_sync_at:'2026-11-06T08:00:00',performances:[],training:{record_count:56,recent_28d_record_count:28,recent_4w_avg_recorded_km:35,previous_4w_avg_recorded_km:30,training_days_per_week_28d:7,longest_recorded_activity:{date:'2026-11-05',distance_km:8,source:'GARMIN'},complete_for_recorded_data:true,limitations:['合成记录，不代表完整设备同步'],last_record_updated_at:'2026-11-06T08:00:00'},recovery:{freshness:'PARTIAL',missing_fields:['sleep_score']}}};
 const draft={id:55,job_id:66,title:'合成个性化计划',status:'draft',created_at:'2026-11-06T08:00:00',updated_at:'2026-11-06T08:00:00',start_date:'2026-11-09',end_date:'2026-11-15',summary:'基于合成训练事实的测试草稿',risk_notes:['需要人工确认'],workouts:[{id:1,workout_date:'2026-11-10',weekday:'周二',block_name:'Week 1',planned_content:'合成轻松跑',focus_note:'控制强度，状态不佳降级',main_type_raw:'E',main_type_normalized:'easy',planned_distance_km:8,sort_order:1}]};
 await page.route('**/api/**',async route=>{
  const p=new URL(route.request().url()).pathname;if(!p.startsWith('/api/'))return route.continue();let data={},status=200;
  if(p==='/api/auth/me')data={id:101,username:'synthetic-plan',role:'user'};
  else if(p==='/api/system/settings')data={auth_entry_mode:'page'};
  else if(p==='/api/data-sync/providers')data={providers:[]};
  else if(p==='/api/ai-plan/quota')data={model_name:'synthetic-provider',remaining_count:3,can_generate:true,cooldown_seconds:0};
  else if(p==='/api/ai-plan/context')data=basis;
  else if(p==='/api/ai-plan/context/assess')data={...basis,feasibility:[{code:'SYNTHETIC_WARNING',severity:'warning',message:'合成恢复信息部分缺失，请确认。'}]};
  else if(p==='/api/ai-plan/generate'){generated=route.request().postDataJSON();data={draft_id:55,job_id:66,title:draft.title,workouts:draft.workouts};}
  else if(p==='/api/ai-plan/drafts')data=generated?[draft]:[];
  else if(p==='/api/ai-plan/drafts/55')data=draft;
  else if(p==='/api/ai-plan-drafts/55/validate')data={evaluation:{final_action:'allow'},message:'合成规则通过'};
  else if(p==='/api/ai-plan/drafts/55/apply'){applyBody=route.request().postDataJSON();if(applyFail){status=400;data={message:'合成已有活跃周期，未应用'};}else data={message:'计划已保存，暂未启用',cycle_id:77,cycle_status:'draft',activated:false};}
  else if(p==='/api/training-cycles')data=[];
  await route.fulfill({status,json:data});
 });
 await page.goto(base+'/ai-plan');await page.getByRole('heading',{name:'自动获取训练基础',exact:true}).waitFor();
 const field=label=>page.locator('.el-form-item').filter({has:page.locator('.el-form-item__label').filter({hasText:label})}).first().locator('input').first();
 const current=field('当前周跑量 km');await current.fill('45');await current.press('Tab');
 await Promise.all([page.waitForResponse(response=>new URL(response.url()).pathname==='/api/ai-plan/context'),page.getByRole('button',{name:'重新获取',exact:true}).click()]);assert.equal(await current.inputValue(),'45');
 await page.getByRole('button',{name:'确认采用跑量到表单',exact:true}).click();await page.getByRole('button',{name:'采用统计值',exact:true}).click();assert.equal(await current.inputValue(),'35');
 await current.fill('46');await current.press('Tab');await page.getByText('用户手动修改，覆盖已接受的表单值；原始训练事实不变',{exact:true}).waitFor();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:path.join(output,name+'-context.png'),fullPage:false});
 await page.getByRole('button',{name:'生成草稿',exact:true}).click();await page.getByRole('button',{name:'了解限制，生成草稿',exact:true}).click();await page.getByRole('heading',{name:'合成个性化计划',exact:true}).waitFor();
 assert.equal(generated.current_weekly_mileage_km,46);assert.equal(generated.use_training_context,true);
 await page.waitForFunction(()=>!document.querySelector('.generation-overlay'));
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 // A failed application must not navigate away or discard the preview.
 applyFail=true;await page.getByRole('button',{name:'保存并启用',exact:true}).click();await page.locator('.el-message-box').getByRole('button',{name:'保存并启用',exact:true}).click();
 await page.getByText('合成已有活跃周期，未应用',{exact:true}).first().waitFor();assert(new URL(page.url()).pathname==='/ai-plan');assert.equal(applyBody.activate,true);
 await page.screenshot({path:path.join(output,name+'-draft.png'),fullPage:false});
 applyFail=false;await page.getByRole('button',{name:'仅保存，暂不启用',exact:true}).click();await page.locator('.el-message-box').getByRole('button',{name:'仅保存',exact:true}).click();await page.waitForURL('**/cycles?cycle_id=77');assert.equal(applyBody.activate,false);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);console.log('PASS',name,'explicit fill/manual override/preflight/generation/failed activation/save-only navigation');await context.close();
}}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
