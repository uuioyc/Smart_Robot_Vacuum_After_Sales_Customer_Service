// 引入 Vue 的创建函数
import { createApp } from 'vue'

// 引入根组件
import App from './App.vue'

// 引入路由配置
import router from './router'

// 创建 Vue 应用
const app = createApp(App)

// 挂载路由（让整个应用支持路由）
app.use(router)

// 挂载到页面上的 #app 元素
app.mount('#app')