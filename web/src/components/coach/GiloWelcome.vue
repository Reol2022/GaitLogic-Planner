<template>
  <section class="gilo-welcome" aria-label="Gilo 教练欢迎页">
    <div class="welcome-aura" aria-hidden="true" />
    <GiloAvatar hero active />
    <p class="welcome-eyebrow">YOUR AI RUNNING COACH</p>
    <h2>你好，我是 <span>Gilo</span></h2>
    <p class="welcome-description">读懂每一次训练，陪你跑向下一个目标。<br>也可以叫我吉洛，或洛教练。</p>
    <div class="welcome-prompts">
      <button v-for="item in prompts" :key="item.title" type="button" :disabled="disabled" @click="emit('select',item.prompt)">
        <span class="prompt-icon" aria-hidden="true"><component :is="item.icon" /></span>
        <span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span><span class="prompt-arrow" aria-hidden="true">↗</span>
      </button>
    </div>
    <p class="welcome-boundary">基于已有训练事实分析 · 计划变更由你确认</p>
  </section>
</template>
<script setup lang="ts">
import {Calendar,TrendCharts,Document,ChatDotRound} from '@element-plus/icons-vue';
import GiloAvatar from './GiloAvatar.vue';
defineProps<{disabled?:boolean}>();
const emit=defineEmits<{(event:'select',prompt:string):void}>();
const prompts=[
  {title:'今天怎么练',description:'看看课表和训练重点',prompt:'今天怎么练？',icon:Calendar},
  {title:'最近状态如何',description:'结合训练与恢复聊一聊',prompt:'看看最近状态',icon:TrendCharts},
  {title:'一起复盘本周',description:'回看计划与实际执行',prompt:'帮我复盘本周',icon:Document},
  {title:'聊聊下个目标',description:'讨论接下来的训练安排',prompt:'讨论训练计划',icon:ChatDotRound},
];
</script>
<style scoped>
.gilo-welcome{position:relative;isolation:isolate;width:min(100%,600px);margin:auto;text-align:center;padding:28px 20px}.welcome-aura{position:absolute;z-index:-1;inset:0 5% 25%;pointer-events:none;background:radial-gradient(ellipse at 30% 30%,#c7eeed60,transparent 65%),radial-gradient(ellipse at 70% 40%,#ded9f660,transparent 70%)}.welcome-eyebrow{margin:0 0 10px;font-size:10px;letter-spacing:.19em;color:#6b7891;font-weight:600}.gilo-welcome h2{font-size:32px;letter-spacing:-1px;margin:0 0 14px;color:#22334b;font-weight:600}.gilo-welcome h2 span{background:linear-gradient(110deg,#138e9e,#6266b9);background-clip:text;-webkit-background-clip:text;color:transparent}.welcome-description{font-size:14px;line-height:1.9;color:#67768a;margin:0}.welcome-prompts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:28px 0 18px;text-align:left}.welcome-prompts button{display:flex;align-items:center;gap:10px;min-width:0;min-height:76px;padding:14px;border:1px solid #dde7ed;border-radius:14px;background:#ffffffc9;text-align:left;cursor:pointer;transition:transform .2s,border-color .2s,box-shadow .2s;font-family:inherit}.welcome-prompts button:hover{transform:translateY(-3px);border-color:#92c8d0;box-shadow:0 8px 22px #5281a315}.welcome-prompts button:focus-visible{outline:2px solid #278eab;outline-offset:3px}.welcome-prompts button:disabled{opacity:.5;cursor:default;transform:none}.prompt-icon{flex-shrink:0;display:grid;place-items:center;background:#edf6f8;color:#338b9e;width:32px;height:32px;border-radius:10px}.prompt-icon svg{width:18px;height:18px}.welcome-prompts strong{display:block;font-size:13px;color:#33455d;font-weight:600}.welcome-prompts small{display:block;font-size:11px;color:#78889a;line-height:1.6;margin-top:3px}.prompt-arrow{margin-left:auto;color:#8b9caf}.welcome-boundary{font-size:11px;color:#7a8799;margin:0}@media(max-width:768px){.gilo-welcome{padding:15px 8px}.gilo-welcome h2{font-size:25px}.welcome-prompts{gap:8px;margin-top:20px}.welcome-prompts button{min-height:76px;padding:10px;gap:7px}.prompt-icon{width:26px;height:28px}.prompt-arrow{display:none}.welcome-prompts small{font-size:10px}.welcome-description{font-size:13px}}@media(max-width:360px){.welcome-prompts{grid-template-columns:1fr}.welcome-prompts button{min-height:58px}}@media(prefers-reduced-motion:reduce){.welcome-prompts button{transition:none}.welcome-prompts button:hover{transform:none}}
</style>
