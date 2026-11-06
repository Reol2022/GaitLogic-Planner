import {beforeEach,describe,it,expect,vi} from 'vitest';
import {api,adminUser,login,logout,verify} from './api';

describe('management console session separation',()=>{
  beforeEach(()=>{sessionStorage.clear();localStorage.clear();adminUser.value=null;});
  it('does not borrow the runner token',async()=>{
    localStorage.setItem('gaitlogic_access_token','runner-only');
    expect(await verify()).toBe(false);
    logout();expect(localStorage.getItem('gaitlogic_access_token')).toBe('runner-only');
  });
  it('rejects a normal runner after login',async()=>{
    vi.spyOn(api,'post').mockResolvedValueOnce({data:{access_token:'synthetic'}});
    vi.spyOn(api,'get').mockResolvedValueOnce({data:{id:2,role:'user',status:'active'}});
    await expect(login('synthetic-runner','synthetic-password')).rejects.toThrow('管理权限');
    expect(adminUser.value).toBeNull();expect(sessionStorage.length).toBe(0);
    vi.restoreAllMocks();
  });
  it('retains only a session token for an active administrator',async()=>{
    vi.spyOn(api,'post').mockResolvedValueOnce({data:{access_token:'synthetic'}});
    vi.spyOn(api,'get').mockResolvedValueOnce({data:{id:1,username:'synthetic-admin',role:'admin',status:'active'}});
    await login('synthetic-admin','synthetic-password');
    expect(adminUser.value?.id).toBe(1);expect(localStorage.length).toBe(0);
    logout();expect(sessionStorage.length).toBe(0);vi.restoreAllMocks();
  });
});
