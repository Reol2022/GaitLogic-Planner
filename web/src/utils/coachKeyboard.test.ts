import {describe,it,expect} from 'vitest';
import {shouldSubmitCoachMessage} from './coachKeyboard';
const enter={key:'Enter',shiftKey:false,altKey:false,ctrlKey:false,metaKey:false,isComposing:false,keyCode:13};
describe('Coach keyboard policy',()=>{
  it('uses the explicit send button on phones',()=>expect(shouldSubmitCoachMessage(enter,true)).toBe(false));
  it('keeps desktop Enter and Shift Enter distinct',()=>{
    expect(shouldSubmitCoachMessage(enter,false)).toBe(true);
    expect(shouldSubmitCoachMessage({...enter,shiftKey:true},false)).toBe(false);
  });
  it('never sends Chinese composition confirmation',()=>{
    expect(shouldSubmitCoachMessage({...enter,isComposing:true},false)).toBe(false);
    expect(shouldSubmitCoachMessage({...enter,keyCode:229},false)).toBe(false);
  });
});
