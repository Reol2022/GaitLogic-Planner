import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";

import App from "./App.vue";
import PageHeader from "./components/PageHeader.vue";
import router from "./router";
import "./styles/global.css";

createApp(App).component("PageHeader", PageHeader).use(router).use(ElementPlus, { locale: zhCn }).mount("#app");
