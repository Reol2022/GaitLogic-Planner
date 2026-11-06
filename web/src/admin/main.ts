import {createApp} from 'vue';
import ElementPlus from 'element-plus';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import 'element-plus/dist/index.css';
import {createRouter,createWebHashHistory} from 'vue-router';
import App from './App.vue';
import Login from './Login.vue';
import Overview from './Overview.vue';
import Users from './Users.vue';
import AI from './AI.vue';
import Audit from './Audit.vue';
import {verify} from './api';
import './style.css';
import './mobile.css';
const router=createRouter({history:createWebHashHistory(),routes:[
  {path:'/login',component:Login},
  {path:'/',component:Overview,meta:{title:'运行概览'}},
  {path:'/users',component:Users,meta:{title:'用户管理'}},
  {path:'/ai',component:AI,meta:{title:'AI 配置'}},
  {path:'/audit',component:Audit,meta:{title:'操作审计'}},
  {path:'/:pathMatch(.*)*',redirect:'/'},
]});
router.beforeEach(async to=>to.path==='/login' || await verify() ? true : '/login');
createApp(App).use(router).use(ElementPlus,{locale:zhCn}).mount('#app');
