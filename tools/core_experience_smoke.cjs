// Optional browser smoke test. Synthetic responses only; no production login or API calls.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = process.env.UI_BASE_URL || 'http://127.0.0.1:5188';
const output = process.env.UI_ARTIFACT_DIR;
if (!output) throw new Error('UI_ARTIFACT_DIR must name a private screenshot directory');
const today = new Date();
const day = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;
const viewports=process.env.UI_VIEWPORTS_JSON ? JSON.parse(process.env.UI_VIEWPORTS_JSON) : [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]];

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, ...(process.env.UI_BROWSER_CHANNEL ? { channel: process.env.UI_BROWSER_CHANNEL } : {}) });
  try {
    for (const [name, viewport] of viewports) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      const errors = [];
      let activeScenario = false;
      let coachWrites=0,syncWrites=0;
      const conversation={id:'synthetic-conversation',title:'合成长对话',status:'active',created_at:day+'T08:00:00',updated_at:day+'T08:00:00'};
      const workout = { id:101, cycle_id:1, block_id:1, workout_date:day, weekday:'测试日期', planned_content:'合成轻松跑：保持舒适，不追求速度', planned_distance_km:8, target_pace_text:'以既定计划为准', main_type_normalized:'easy', session_index:1, sort_order:1, is_locked:false, plan_version:1,workout_log:{status_normalized:'completed_normal',actual_distance_km:5,actual_duration_seconds:1800} };
      const cycle = { id:1, name:'合成训练周期', goal:'合成半马训练目标', status:'active', start_date:day, end_date:day };
      page.on('pageerror', error => errors.push(error.message));
      await context.addInitScript(() => {
        localStorage.setItem('gaitlogic_access_token', `header.${btoa(JSON.stringify({ sub:'101' }))}.signature`);
        localStorage.setItem('gaitlogic:experience:101:welcome-dismissed', '1');
      });
      await page.route('**/api/**', async route => {
        const url = new URL(route.request().url());
        if (!url.pathname.startsWith('/api/')) return route.continue();
        const p = url.pathname.replace(/^\/api/, '');
        if(p.startsWith('/integrations/garmin/') && route.request().method()==='POST')syncWrites++;
        let data = {};
        let status = 200;
        if (p === '/auth/me') data = { id:101, username:'synthetic-runner', nickname:'测试跑者', role:'user' };
        else if (p === '/system/settings') data = { auth_entry_mode:'page' };
        else if (p === '/onboarding/status') data = { should_show_welcome:false };
        else if (p === '/training-cycles') data = activeScenario ? [cycle] : [];
        else if (p === '/training-cycles/active' && activeScenario) data = cycle;
        else if (p.startsWith('/training-blocks')) data = [];
        else if (p==='/training-cycles/lifecycle' && activeScenario) data={state:'active'};
        else if (p.includes('active')) status = 404;
        else if (p === '/today') data = activeScenario ? [workout] : [];
        else if (p === '/planned-workouts' && activeScenario) data=[workout];
        else if (p === '/training-plan/overview' && activeScenario) data={has_active_cycle:true,active_cycle:cycle,lifecycle:{state:'active'},week_start:day,week_end:day,week_workouts:[workout],primary_actions:[],advanced_links:[]};
        else if (p === '/dashboard' && activeScenario) data={planned_distance_km:8,actual_distance_km:5,completion_rate:62.5,workout_count:1,completed_count:1,missed_count:0,avg_rpe:null,max_pain_level:0,main_type_distribution:{easy:1}};
        else if (p === '/dashboard/today') data = { today:day, lifecycle:{ state:'active' }, tasks:[], data_sync:{ connected_count:0, providers:[] } };
        else if (p === '/training-readiness/today' && activeScenario) data = { recovery_checkin_completed:false, assessment:{ status:'watch', data_quality:'low', reasons_json:['合成恢复关注提醒'], metrics_json:{load_change_percentage:null} } };
        else if (p.includes('today-dashboard')) data = { today:day, lifecycle:{ state:'empty' }, tasks:[], data_sync:{ connected_count:0, providers:[] } };
        else if (p.includes('today') && p !== '/today') status = 403;
        else if (p === '/data-sync/providers') data = { providers:[] };
        else if (p === '/data-sync/activities') data = { activities:[] };
        else if (p === '/coach/conversations') data = { items:[conversation], total:1, page:1, page_size:20 };
        else if (p.endsWith('/messages') && route.request().method()==='GET') data={items:Array.from({length:18},(_,n)=>({id:'synthetic-message-'+n,role:n%2?'assistant':'user',content:`合成训练讨论 ${n+1}：仅用于布局测试，不是真实跑者数据。`+'说明文字。'.repeat(12),status:'completed',sequence_no:n+1,evidence_refs:[],warnings:[],limitations:[],tool_calls:[],created_at:day+'T08:00:00'})),total:18,page:1,page_size:50};
        else if (p.endsWith('/messages') && route.request().method()==='POST'){coachWrites++;data={};}
        else if (p === '/integrations/garmin/status') data = { connected:true, provider:'garmin', status:'connected', auto_import_enabled:true };
        else if (p === '/integrations/garmin/sync-jobs') data = [{ id:101, sync_mode:'recent_7d', status:'failed', provider:'garmin', error_code:'PROVIDER_UNAVAILABLE', safe_error_message:'合成服务暂不可用', fetched_count:0, created_count:0, updated_count:0, needs_review_count:0, failed_count:0, updated_at:'2026-11-05T12:00:00Z' }];
        else if (p === '/integrations/garmin/activities') data = [{id:201,activity_date:day,activity_name:'合成轻松跑活动',distance_m:5000,duration_seconds:1800,average_pace_seconds_per_km:360,average_heart_rate_bpm:130,processing_status:'imported',resolution_status:'unplanned',apply_status:'applied',workout_log_id:101,planned_workout_id:null}];
        await route.fulfill({ status, contentType:'application/json', body:JSON.stringify(data) });
      });
      for (const route of ['/welcome','/today','/training-plan','/dashboard','/weekly-review','/coach?topic=today','/data-sync/garmin','/my']) {
        await page.goto(base + route);
        await page.locator('h1:visible').first().waitFor({ state:'visible', timeout:15000 });
        await page.waitForTimeout(650);
        const slug = route.split('?')[0].replaceAll('/', '') || 'home';
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        assert.equal(overflow, false, `${name} ${route}: page horizontal overflow`);
        await page.screenshot({ path:path.join(output, `${name}-${slug}.png`), fullPage:true });
        console.log('PASS', name, route);
        if(viewport.width<=768 && route==='/welcome'){
          await page.getByRole('button',{name:'先记录和了解训练'}).click();
          await page.getByRole('button',{name:'稍后连接，继续'}).click();
          const finish=page.getByRole('button',{name:'查看记录入口'});await finish.scrollIntoViewIfNeeded();assert((await finish.boundingBox()).height>=44);
          await page.screenshot({path:path.join(output,`${name}-guide-step3.png`),fullPage:true});
        }
        if(viewport.width<=768 && route==='/coach?topic=today'){
          const input=page.getByRole('textbox',{name:'发送给 AI 教练的消息'});await input.fill('手机回车应换行');await input.press('Enter');assert.equal(coachWrites,0);
          const send=page.getByRole('button',{name:'发送',exact:true});const rect=await send.boundingBox();const nav=await page.locator('.mobile-bottom-nav').boundingBox();
          assert(rect && nav && rect.y+rect.height<=nav.y+1,`${name}: send button hidden by navigation`);
          await page.getByRole('button',{name:'历史会话'}).click();await page.getByRole('heading',{name:'历史会话'}).waitFor();await page.keyboard.press('Escape');
          const list=page.locator('.message-list');await list.evaluate(element=>element.scrollTop=0);assert.equal(await list.evaluate(element=>element.scrollTop),0);
          await page.screenshot({path:path.join(output,`${name}-coach-composer.png`),fullPage:true});
        }
        if(viewport.width<=768 && route==='/data-sync/garmin'){
          await page.locator('.el-segmented__item').filter({hasText:'自定义'}).click();
          await page.getByLabel('开始时间',{exact:true}).fill('2026-11-06T10:00');
          await page.getByLabel('结束时间',{exact:true}).fill('2026-11-05T10:00');
          await page.getByRole('button',{name:'开始同步',exact:true}).click();
          assert.equal(syncWrites,0,'Invalid mobile date range must not start a sync');
          await page.locator('.sync-history>summary').click();
          assert(await page.locator('[aria-label="同步任务卡片"] .mobile-record-card').isVisible());
          assert(await page.locator('[aria-label="设备活动卡片"] .mobile-record-card').isVisible());
          await page.screenshot({path:path.join(output,`${name}-sync-cards.png`),fullPage:true});
        }
      }
      activeScenario = true;
      await page.goto(base + '/today');
      await page.getByText(workout.planned_content, { exact:true }).first().waitFor();
      assert(await page.locator('.el-alert').filter({hasText:'合成恢复关注提醒'}).first().isVisible(),'Important recovery warning must remain outside collapsed tools');
      assert(await page.getByRole('button',{name:'请教练解释这天的安排',exact:true}).isVisible(),'Original coach action must be restored');
      assert(await page.locator('.training-journey').isVisible(),'Original journey navigation must be restored');
      if(viewport.width<=768){
        await page.locator('.focus-heading .el-date-editor input').click();
        const picker=page.locator('.el-picker-panel:visible');await picker.waitFor();
        const box=await picker.boundingBox();assert(box && box.x>=-1 && box.x+box.width<=viewport.width+1,`${name}: date picker exceeds viewport`);
        await page.keyboard.press('Escape');
        await picker.waitFor({state:'hidden'});
      }
      await page.screenshot({ path:path.join(output, `${name}-today-active.png`), fullPage:true });
      console.log('PASS', name, 'today with synthetic plan');
      await page.goto(base+'/dashboard');
      await page.locator('.chart canvas').first().waitFor();
      assert.equal(await page.locator('.chart canvas').count(),4,'All original charts must render without opening a disclosure');
      assert.equal(await page.locator('.quiet-disclosure').count(),0);
      await page.screenshot({path:path.join(output,`${name}-records-overview.png`),fullPage:true});
      console.log('PASS',name,'original statistics restored');
      await page.goto(base+'/training-plan');await page.locator('.week-list').waitFor();assert(await page.getByRole('button',{name:'训练日历',exact:true}).isVisible());
      await page.screenshot({path:path.join(output,`${name}-plan-active.png`),fullPage:true});
      console.log('PASS',name,'original plan layout restored');
      assert.deepEqual(errors, [], `${name}: browser errors`);
      await context.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
