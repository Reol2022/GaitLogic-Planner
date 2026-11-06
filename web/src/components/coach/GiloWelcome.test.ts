import {mount} from '@vue/test-utils';
import {describe,it,expect} from 'vitest';
import GiloWelcome from './GiloWelcome.vue';
import GiloAvatar from './GiloAvatar.vue';
describe('Gilo visual identity',()=>{
  it('shows identity and sends only the selected question',async()=>{
    const wrapper=mount(GiloWelcome);expect(wrapper.text()).toContain('你好，我是 Gilo');expect(wrapper.text()).toContain('计划变更由你确认');
    await wrapper.findAll('button')[0].trigger('click');expect(wrapper.emitted('select')).toEqual([['今天怎么练？']]);wrapper.unmount();
  });
  it('does not allow repeated quick prompts while busy',()=>{
    const wrapper=mount(GiloWelcome,{props:{disabled:true}});expect(wrapper.findAll('button').every(button=>button.element.disabled)).toBe(true);wrapper.unmount();
  });
  it('keeps decorative artwork out of accessibility announcements and animates only on request',()=>{
    const wrapper=mount(GiloAvatar);expect(wrapper.attributes('aria-hidden')).toBe('true');expect(wrapper.classes()).not.toContain('is-active');wrapper.unmount();
  });
});
