// Synthetic UI verification only. Never calls a real LLM or reads a real account.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const output=process.env.UI_ARTIFACT_DIR;if(!output)throw new Error('Private UI_ARTIFACT_DIR required');
const base=process.env.UI_BASE_URL || 'http://127.0.0.1:5189';
(async()=>{
 fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{for(const [name,viewport,reducedMotion] of [['desktop',{width:1440,height:1000},'no-preference'],['mobile',{width:390,height:844},'no-preference'],['small-mobile',{width:320,height:740},'reduce']]){
  const context=await browser.newContext({viewport,reducedMotion});const page=await context.newPage();let created=false,stored=[],stage='QUEUED',release,fail=false,postCount=0;const errors=[];
  page.on('pageerror',error=>{errors.push(error.message);console.error('Synthetic browser error:',error.message);});
  await context.addInitScript(()=>localStorage.setItem('gaitlogic_access_token',`x.${btoa(JSON.stringify({sub:'101'}))}.x`));
  const conversation={id:'synthetic-gilo',title:'合成训练讨论',status:'active',created_at:'2026-11-06T08:00:00',updated_at:'2026-11-06T08:00:00',message_count:0};
  await page.route('**/api/**',async route=>{
   const p=new URL(route.request().url()).pathname;if(!p.startsWith('/api/'))return route.continue();const method=route.request().method();let data={},status=200;
   if(p==='/api/auth/me')data={id:101,username:'synthetic',role:'user'};
   else if(p==='/api/system/settings')data={auth_entry_mode:'page'};
   else if(p==='/api/data-sync/providers')data={providers:[]};
   else if(p==='/api/coach/conversations' && method==='GET')data={items:created?[conversation]:[],total:created?1:0,page:1,page_size:20};
   else if(p==='/api/coach/conversations' && method==='POST'){created=true;data=conversation;}
   else if(p.endsWith('/messages') && method==='GET')data={items:stored,total:stored.length,page:1,page_size:50};
   else if(p.endsWith('/status'))data={conversation_id:conversation.id,message_id:'synthetic-answer',message_status:'pending',client_turn_id:'synthetic-turn',progress:{stage,sequence:stage==='QUEUED'?1:3,summary:stage==='FACTS_READY'?[{code:'SYNTHETIC_RECORD_COUNT',message:'合成训练记录',count:18}]:[],terminal:false}};
   else if(p.endsWith('/messages') && method==='POST'){
    postCount++;if(fail){status=503;data={code:'PROVIDER_UNAVAILABLE',message:'合成服务暂不可用'};}
    else{await new Promise(resolve=>release=resolve);stored=[{id:'synthetic-question',role:'user',content:'请分析合成训练数据',status:'completed',sequence_no:1,evidence_refs:[],warnings:[],limitations:[],tool_calls:[]},{id:'synthetic-answer',role:'assistant',content:'这是一条合成训练分析，仅供界面验收。\n近期训练连续性需要结合恢复情况判断。',status:'completed',sequence_no:2,evidence_refs:[],warnings:[{code:'SYNTHETIC_WARNING',message:'合成风险提醒：重要警告仍需保留。'}],limitations:[{code:'SYNTHETIC_LIMIT',message:'合成数据不代表真实训练。'}],tool_calls:[]}];data={conversation_id:conversation.id,message_id:'synthetic-answer',status:'completed',content:stored[1].content};}
   }
   await route.fulfill({status,json:data});
  });
  await page.goto(base+'/coach');await page.screenshot({path:path.join(output,name+'-initial.png'),fullPage:false});await page.getByRole('heading',{name:/你好，我是\s*Gilo/}).waitFor();
  assert.equal(postCount,0);assert(await page.getByRole('heading',{name:'和 Gilo 聊训练'}).isVisible());
  await page.goto(base+'/coach?topic=today&date=2026-11-06&from=%2Fmy');
  await page.getByRole('button',{name:'放入新对话',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('.context-entry'));
  await page.waitForURL(url=>!url.searchParams.has('topic') && !url.searchParams.has('date'));
  assert.equal(new URL(page.url()).searchParams.get('from'),'/my');
  assert((await page.getByRole('textbox',{name:'发送给 AI 教练的消息'}).inputValue()).includes('2026-11-06'));
  assert.equal(postCount,0,'Preparing an entry must not send a model request');
  await page.reload();await page.locator('.composer').waitFor();assert.equal(await page.locator('.context-entry').count(),0);
  if(reducedMotion==='reduce')assert.equal(await page.locator('.gilo-welcome .gilo-orbit').evaluate(el=>getComputedStyle(el).animationName),'none');
  await page.screenshot({path:path.join(output,name+'-welcome.png'),fullPage:false});
  await page.getByRole('button',{name:/今天怎么练/}).click();await page.locator('.gilo-signal').waitFor();assert.equal(postCount,1);
  stage='FACTS_READY';await page.getByText('已获取训练事实，正在组织分析',{exact:true}).waitFor();
  await page.getByText('查看已获取信息',{exact:true}).click();await page.getByText('合成训练记录：18 条',{exact:false}).waitFor();
  await page.screenshot({path:path.join(output,name+'-progress.png'),fullPage:false});
  release();await page.getByText('这是一条合成训练分析，仅供界面验收。',{exact:false}).waitFor();await page.waitForFunction(()=>!document.querySelector('.gilo-signal'));
  await page.waitForFunction(()=>!document.querySelector('.composer button.is-loading'));
  assert(await page.getByText('合成风险提醒：重要警告仍需保留。',{exact:true}).isVisible());
  const list=page.locator('.message-list');assert(await list.evaluate(el=>el.scrollHeight-el.scrollTop<=el.clientHeight+3));
  if(viewport.width<=768){
   const send=await page.getByRole('button',{name:'发送',exact:true}).boundingBox(),nav=await page.locator('.mobile-bottom-nav').boundingBox();assert(send.y+send.height<=nav.y+1);
   await page.getByRole('button',{name:'历史会话',exact:true}).click();await page.getByRole('heading',{name:'历史会话',exact:true}).waitFor();await page.keyboard.press('Escape');
  }
  await page.screenshot({path:path.join(output,name+'-answer.png'),fullPage:false});
  fail=true;await page.getByRole('textbox',{name:'发送给 AI 教练的消息'}).fill('合成失败请求');await page.getByRole('button',{name:'发送',exact:true}).click();
  await page.locator('.submit-error').waitFor();await page.waitForFunction(()=>!document.querySelector('.gilo-signal'));assert(await page.getByRole('button',{name:'重试',exact:true}).isVisible());
  // Reload a persisted long conversation; chat and history remain independently scrollable.
  stored=Array.from({length:40},(_,index)=>({...stored[index%2],id:'synthetic-long-'+index,sequence_no:index+1,content:'合成长对话第'+(index+1)+'条。'+'训练说明。'.repeat(18)}));
  await page.reload();await page.getByText('合成长对话第40条。',{exact:false}).waitFor();
  assert(await list.evaluate(el=>el.scrollHeight-el.scrollTop<=el.clientHeight+3));
  if(viewport.width>768){const before=await page.locator('.desktop-conversations').boundingBox();await list.evaluate(el=>el.scrollTop=0);const after=await page.locator('.desktop-conversations').boundingBox();assert.equal(after.y,before.y);}
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
  console.log('PASS',name,'Gilo welcome, real-stage UI, answer, safety notices, failure effects, mobile history/composer and reduced motion');await context.close();
 }}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
