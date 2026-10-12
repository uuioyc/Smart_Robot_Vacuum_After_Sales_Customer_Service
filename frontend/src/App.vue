<!--
frontend/
├── index.html                    ← 整个项目只有一个 HTML 页面
├── src/
│   ├── main.js                   ← 把 App.vue 挂载到 index.html
│   ├── App.vue                   ← 唯一的根组件，里面只有 <router-view />
│   ├── views/
│   │   ├── Login.vue             ← 不是独立页面，是组件
│   │   └── Chat.vue              ← 不是独立页面，是组件
│   └── router/
│       └── index.js              ← 决定 router-view 里显示谁


-->


<template>
  <!-- 路由出口：根据当前 URL 显示对应页面 -->
  <router-view />
</template>

<script setup>
</script>

<style>
/* 全局样式 */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif;
  background: #f5f5f5;
}

* {
  box-sizing: border-box;
}
</style>