import {describe,it,expect} from 'vitest';
import {mount} from '@vue/test-utils';
import MobileRecordCard from './MobileRecordCard.vue';
describe('MobileRecordCard',()=>{
  it('preserves supplied facts instead of manufacturing counts',()=>{
    const wrapper=mount(MobileRecordCard,{props:{title:'合成活动'},slots:{default:'<p>距离缺失</p>'}});
    expect(wrapper.text()).toContain('距离缺失');expect(wrapper.find('footer').exists()).toBe(false);
  });
  it('keeps explicit operations separate from the record body',async()=>{
    const wrapper=mount(MobileRecordCard,{props:{title:'合成任务'},slots:{status:'<span>排队中</span>',actions:'<button>取消同步</button>'}});
    expect(wrapper.find('header').text()).toContain('排队中');expect(wrapper.find('footer button').text()).toBe('取消同步');
  });
});
