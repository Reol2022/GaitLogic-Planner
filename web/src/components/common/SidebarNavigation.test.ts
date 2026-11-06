import {beforeEach,describe,it,expect,vi} from 'vitest';
import {flushPromises,shallowMount} from '@vue/test-utils';
import {defineComponent} from 'vue';
import SidebarNavigation from './SidebarNavigation.vue';
const state=vi.hoisted(()=>({path:'/workouts/123/log',open:vi.fn()}));
vi.mock('vue-router',()=>({useRoute:()=>state}));
const Menu=defineComponent({setup(_,ctx){ctx.expose({open:state.open});return {};},template:'<div><slot/></div>'});
function page(collapsed=false){return shallowMount(SidebarNavigation,{props:{admin:false,devices:false,collapsed},global:{stubs:{ElMenu:Menu,ElMenuItemGroup:{template:'<section><slot/></section>'},ElMenuItem:{template:'<div><slot/><slot name="title"/></div>'},ElSubMenu:{template:'<section><slot name="title"/><slot/></section>'},ElIcon:{template:'<i/>'}}}});}
describe('SidebarNavigation state',()=>{
  beforeEach(()=>{state.path='/workouts/123/log';state.open.mockClear();});
  it('opens the current group but does not force popups in icon mode',async()=>{
    const wrapper=page();await flushPromises();expect(state.open).toHaveBeenCalledWith('planning');wrapper.unmount();
    state.open.mockClear();const collapsed=page(true);await flushPromises();expect(state.open).not.toHaveBeenCalled();collapsed.unmount();
  });
  it('updates admin and device visibility without accepting a user ID',async()=>{
    const wrapper=page();await flushPromises();expect(wrapper.text()).not.toContain('管理后台');expect(wrapper.text()).not.toContain('Garmin 同步');
    await wrapper.setProps({admin:true,devices:true});await flushPromises();expect(wrapper.text()).toContain('Garmin 同步');expect(wrapper.find('a[href="/admin.html#/"]').exists()).toBe(true);
    await wrapper.setProps({admin:false,devices:false});expect(wrapper.find('a[href="/admin.html#/"]').exists()).toBe(false);wrapper.unmount();
  });
});
