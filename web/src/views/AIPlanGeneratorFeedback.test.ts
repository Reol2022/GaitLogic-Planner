import {flushPromises,shallowMount} from '@vue/test-utils';
import {beforeEach,describe,it,expect,vi} from 'vitest';
import ElementPlus from 'element-plus';
import AIPlanGenerator from './AIPlanGenerator.vue';
import type {AIPlanGeneratePayload} from '@/types/models';

const mock=vi.hoisted(()=>({generate:vi.fn(),assess:vi.fn(),push:vi.fn()}));
vi.mock('vue-router',()=>({useRouter:()=>({push:mock.push})}));
vi.mock('@/api/usageEvents',()=>({trackUsageEvent:vi.fn()}));
vi.mock('@/api/aiPlan',()=>({
 generateAIPlan:mock.generate, assessAIPlanContext:mock.assess,
 getAIPlanQuota:vi.fn().mockResolvedValue({can_generate:true,remaining_count:5}),
 getAIPlanDrafts:vi.fn().mockResolvedValue([]),getAIPlanContext:vi.fn().mockResolvedValue(null),
 getAIPlanDraftDetail:vi.fn(),applyAIPlanDraft:vi.fn(),exportAIPlanDraft:vi.fn(),rejectAIPlanDraft:vi.fn(),
}));
describe('AI plan date and failure feedback',()=>{
 beforeEach(()=>{vi.clearAllMocks();mock.assess.mockResolvedValue({feasibility:[]});});
 function render(){return shallowMount(AIPlanGenerator,{global:{plugins:[ElementPlus],renderStubDefaultSlot:true,stubs:{RouterLink:true,PageHeader:true,ElTable:{template:'<div/>'}}}});}
 function state(wrapper:ReturnType<typeof render>){return wrapper.vm as unknown as {form:AIPlanGeneratePayload;syncWeeksFromRace():void;generate():Promise<void>};}
 it('matches a race without producing its own conflicting recommendation',async()=>{
  const wrapper=render();await flushPromises();const vm=state(wrapper);
  Object.assign(vm.form,{plan_start_date:'2026-11-09',target_race_date:'2027-02-10',plan_weeks:8});
  vm.syncWeeksFromRace();await flushPromises();
  expect(vm.form.plan_weeks).toBe(14);expect(vm.form.plan_start_date).toBe('2026-11-09');
  expect(wrapper.find('.date-summary').classes()).not.toContain('invalid');
  expect(wrapper.find('.date-summary').text()).toContain('最后一周 3 天');wrapper.unmount();
 });
 it('shows exact conflicting input and a one-click correction',async()=>{
  const wrapper=render();await flushPromises();const vm=state(wrapper);
  Object.assign(vm.form,{plan_start_date:'2026-11-09',target_race_date:'2027-02-10',plan_weeks:15});await flushPromises();
  expect(wrapper.find('.date-summary').text()).toContain('当前填写 15 周');
  expect(wrapper.find('.date-summary').classes()).toContain('invalid');
  vm.syncWeeksFromRace();await flushPromises();expect(wrapper.find('.date-summary').classes()).not.toContain('invalid');wrapper.unmount();
 });
 it('keeps a model validation failure visible and preserves the user input',async()=>{
  const message='模型已返回课表，但训练与固定休息日冲突。本次未保存为可应用草稿，未扣除成功生成额度。';
  mock.generate.mockRejectedValue({response:{status:400,data:{code:'AI_PLAN_CONSTRAINT_VIOLATION',message}}});
  const wrapper=render();await flushPromises();const vm=state(wrapper);
  await vm.generate();await flushPromises();
  expect(wrapper.find('[role="alert"]').attributes('title')).toBe(message);
  expect(vm.form.plan_weeks).toBe(8);expect(mock.generate).toHaveBeenCalledTimes(1);wrapper.unmount();
 });
});
