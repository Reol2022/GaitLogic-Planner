import {describe,it,expect} from 'vitest';
import {shallowMount,flushPromises} from '@vue/test-utils';
import SidebarPreferencesDialog from './SidebarPreferencesDialog.vue';
import {defaultSidebarPreferences} from '@/utils/sidebarPreferences';
const stubs={ElDialog:{template:'<section><slot/><slot name="footer"/></section>'},ElSelect:{template:'<div><slot/></div>'},ElOption:true,ElCollapse:{template:'<div><slot/></div>'},ElCollapseItem:{template:'<div><slot/></div>'},ElCheckbox:{template:'<span><slot/></span>'},ElButton:{template:'<button><slot/></button>'}};
describe('SidebarPreferencesDialog',()=>{
  it('edits a copy and cancel does not save',async()=>{
    const preferences=defaultSidebarPreferences();const wrapper=shallowMount(SidebarPreferencesDialog,{props:{modelValue:false,preferences,admin:false,devices:true},global:{stubs}});
    await wrapper.setProps({modelValue:true});await flushPromises();
    await wrapper.get('[aria-label="下移训练记录"]').trigger('click');
    expect(preferences.groupOrder).toEqual([]);
    await wrapper.findAll('button').find(button=>button.text()==='取消')!.trigger('click');
    expect(wrapper.emitted('save')).toBeUndefined();expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false]);
    wrapper.unmount();
  });
  it('saves changed order and only restores defaults when explicitly saved',async()=>{
    const preferences=defaultSidebarPreferences();const wrapper=shallowMount(SidebarPreferencesDialog,{props:{modelValue:false,preferences,admin:false,devices:true},global:{stubs}});
    await wrapper.setProps({modelValue:true});
    await wrapper.get('[aria-label="下移训练记录"]').trigger('click');
    await wrapper.findAll('button').find(button=>button.text()==='保存设置')!.trigger('click');
    expect((wrapper.emitted('save')![0][0] as typeof preferences).groupOrder[0]).toBe('readiness');
    await wrapper.findAll('button').find(button=>button.text()==='恢复默认')!.trigger('click');
    expect(wrapper.emitted('save')).toHaveLength(1);
    await wrapper.findAll('button').find(button=>button.text()==='保存设置')!.trigger('click');
    expect((wrapper.emitted('save')![1][0] as typeof preferences).groupOrder).toEqual([]);wrapper.unmount();
  });
});
