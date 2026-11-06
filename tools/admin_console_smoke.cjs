// UI-only acceptance with synthetic responses. Never connects to real accounts.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const output=process.env.UI_ARTIFACT_DIR;
if(!output)throw new Error('Set a private UI_ARTIFACT_DIR');
const base=process.env.UI_BASE_URL || 'http://127.0.0.1:5189/admin.html';
const config={model_name:'synthetic-model',timeout_seconds:120,ai_plan_daily_limit:3,ai_plan_cooldown_seconds:60,temperature:0.4,top_p:0.9,max_tokens_per_week:1600,max_tokens_cap:24000};
const viewports=process.env.UI_VIEWPORTS_JSON ? JSON.parse(process.env.UI_VIEWPORTS_JSON) : [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]];
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL || 'msedge'});
  try{
    for(const [name,viewport] of viewports){
      const context=await browser.newContext({viewport});const page=await context.newPage();const errors=[];let writes=0;
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(new URL('/control/login?redirect=%2Fcontrol%2Flogin',base).href);
      await page.waitForURL('**/admin.html#/login');
      await page.route('**/api/**',async route=>{
        const request=route.request(),url=new URL(request.url());if(!url.pathname.startsWith('/api/'))return route.continue();
        const endpoint=url.pathname;
        let data={};
        if(endpoint==='/api/auth/login')data={access_token:'synthetic-ui-token'};
        else if(endpoint==='/api/auth/me')data={id:101,username:'synthetic-admin',role:'admin',status:'active'};
        else if(endpoint.endsWith('/overview'))data={users_total:50,users_active:48,sync_jobs:{succeeded:30,queued:1}};
        else if(endpoint.endsWith('/users'))data={items:[{id:102,username:'synthetic-runner',nickname:'合成测试账号',email:null,role:'user',status:'active'}],total:1};
        else if(endpoint.endsWith('/ai'))data={config,fingerprint:'a'.repeat(64),source:'database',initialized:true,has_api_key:true,profiles:[{task:'COACH_ANALYSIS',profile:'coach_analysis',model:'synthetic-model',thinking_enabled:false,timeout_seconds:60}],notice:'仅课表配置可以发布，Coach 档位只读。'};
        else if(endpoint.endsWith('/ai/revisions'))data=[{id:1,status:'DRAFT',config_json:config,created_at:'2026-11-06T00:00:00'}];
        else if(endpoint.endsWith('/audit'))data={items:[{id:1,actor_user_id:101,action:'AI_DRAFT_CREATED',target_type:'ai_revision',target_id:1,changed_fields:['model_name'],created_at:'2026-11-06T00:00:00'}],total:1};
        else if(endpoint.endsWith('/publish')){writes++;data={};}
        else return route.fulfill({status:404,json:{message:'Unexpected synthetic request'}});
        await route.fulfill({status:200,json:data});
      });
      await page.goto(base+'#/login');await page.getByRole('heading',{name:'欢迎回来'}).waitFor();
      await page.screenshot({path:path.join(output,name+'-login.png'),fullPage:true});
      await page.getByLabel('用户名').fill('synthetic-admin');await page.getByLabel('密码',{exact:true}).fill('synthetic-password');
      await page.getByRole('button',{name:'进入控制台'}).click();await page.getByRole('heading',{name:'运行概览'}).waitFor();
      for(const [route,title] of [['/','运行概览'],['/users','用户管理'],['/ai','AI 配置'],['/audit','操作审计']]){
        await page.goto(base+'#'+route);await page.getByRole('heading',{name:title,exact:true}).waitFor();
        await page.waitForTimeout(250);
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+route+' horizontal overflow');
        await page.screenshot({path:path.join(output,name+'-'+(route.slice(1)||'overview')+'.png'),fullPage:true});
        if(route==='/ai'){
          await page.getByRole('button',{name:'发布此草稿'}).click();await page.getByRole('button',{name:'取消',exact:true}).click();
          assert.equal(writes,0,'Cancel must not publish');
        }
        if(viewport.width<=768 && route==='/users'){
          const cards=page.locator('[aria-label="用户卡片"]');assert(await cards.isVisible());
          await cards.getByRole('button',{name:'管理权限'}).click();await page.getByRole('dialog').waitFor();
          const dialog=await page.getByRole('dialog').boundingBox();assert(dialog.width<=viewport.width && dialog.x>=0);
          await page.getByRole('button',{name:'取消',exact:true}).click();
        }
        if(viewport.width<=768 && route==='/audit')assert(await page.locator('[aria-label="审计记录卡片"]').isVisible());
        console.log('PASS',name,route);
      }
      assert.deepEqual(errors,[]);await context.close();
    }
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
