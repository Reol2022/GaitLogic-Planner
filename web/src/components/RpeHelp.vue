<template>
  <el-popover placement="top" :width="300" trigger="click">
    <template #reference>
      <button class="rpe-help" type="button" aria-label="查看 RPE 说明">?</button>
    </template>
    <div class="rpe-guide">
      <strong>RPE：主观用力程度</strong>
      <p><b>0–1</b> 休息或几乎没有用力</p>
      <p><b>2–3</b> 很轻松，可以自由交谈</p>
      <p><b>4–5</b> 轻松到中等，呼吸开始加深</p>
      <p><b>6–7</b> 较吃力，只能说短句</p>
      <p><b>8–9</b> 很吃力，接近极限</p>
      <p><b>10</b> 最大努力，无法继续维持</p>
    </div>
  </el-popover>
</template>

<style scoped>
.rpe-help {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  margin-left: 5px;
  padding: 0;
  border: 1px solid #98a2b3;
  border-radius: 50%;
  color: #667085;
  background: #ffffff;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  cursor: pointer;
}

.rpe-help:hover,
.rpe-help:focus-visible {
  border-color: var(--primary);
  color: var(--primary);
  outline: none;
}

.rpe-guide strong {
  display: block;
  margin-bottom: 10px;
  color: var(--text);
}

.rpe-guide p {
  margin: 6px 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.45;
}

.rpe-guide b {
  display: inline-block;
  min-width: 38px;
  color: var(--text);
}
</style>
