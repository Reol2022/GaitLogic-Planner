import {describe,it,expect,vi} from 'vitest';
import {shallowMount} from '@vue/test-utils';
import MobileNavigationDrawer from './MobileNavigationDrawer.vue';
import {defaultSidebarPreferences} from '@/utils/sidebarPreferences';
vi.mock('vue-router',()=>({useRoute:()=>({path:'/coach',fullPath:'/coach'})}));
const stubs={ElDrawer:{template:'<aside><slot/><slot name="footer"/></aside>'},ElCollapse:{template:'<div><slot/></div>'},ElCollapseItem:{props:['title'],template:'<section><h3>{{title}}</h3><slot/></section>'},ElButton:{template:'<button><slot/></button>'},RouterLink:{props:['to'],template:'<a :href="to"><slot/></a>'}};
describe('mobile shared navigation',()=>{
  it('shares hidden groups and permission gates, but always preserves profile and settings',()=>{
    const preferences=defaultSidebarPreferences();preferences.hiddenGroups=['planning'];preferences.shortcuts=[];
    const wrapper=shallowMount(MobileNavigationDrawer,{props:{modelValue:true,preferences,admin:false,devices:false},global:{stubs}});
    expect(wrapper.text()).not.toContain('训练与计划');expect(wrapper.text()).not.toContain('管理后台');expect(wrapper.text()).not.toContain('Garmin 同步');
    expect(wrapper.find('a[href="/my"]').exists()).toBe(true);expect(wrapper.text()).toContain('自定义菜单');wrapper.unmount();
  });
  it('allows recovery from an empty menu and closes before customization',async()=>{
    const preferences=defaultSidebarPreferences();preferences.shortcuts=[];preferences.hiddenGroups=['activities','readiness','planning','devices','personal','administration'];
    const wrapper=shallowMount(MobileNavigationDrawer,{props:{modelValue:true,preferences,admin:false,devices:false},global:{stubs}});
    expect(wrapper.text()).toContain('菜单已隐藏');await wrapper.get('button').trigger('click');
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false]);expect(wrapper.emitted('customize')).toHaveLength(1);wrapper.unmount();
  });
});
