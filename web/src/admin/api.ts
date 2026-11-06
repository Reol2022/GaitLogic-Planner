import axios from 'axios';
import { ref } from 'vue';
const key='gaitlogic_admin_session';
export const adminUser=ref<{id:number;username:string;role:string}|null>(null);
export const api=axios.create({baseURL:'/api',timeout:20000});
api.interceptors.request.use(config=>{
  const token=sessionStorage.getItem(key);
  if(token) config.headers.Authorization=`Bearer ${token}`;
  return config;
});
api.interceptors.response.use(response=>response,error=>{
  if(error.response?.status===401 || error.response?.status===403) logout();
  return Promise.reject(error);
});
export function logout(){sessionStorage.removeItem(key);adminUser.value=null;}
export async function verify(){
  if(!sessionStorage.getItem(key)) return false;
  try {
    const {data}=await api.get('/auth/me');
    if(data.role!=='admin' || data.status!=='active'){logout();return false;}
    adminUser.value=data;return true;
  } catch {logout();return false;}
}
export async function login(username:string,password:string){
  logout();
  const {data}=await api.post('/auth/login',{username,password});
  sessionStorage.setItem(key,data.access_token);
  if(!await verify()) throw new Error('该账号没有管理权限。');
}
export function errorText(error:unknown){
  if(axios.isAxiosError(error)) return error.response?.data?.message || '请求失败，请检查服务连接或稍后重试。';
  return error instanceof Error ? error.message : '请求失败。';
}
export const consoleApi='/admin/console';
