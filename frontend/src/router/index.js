// 引入路由相关函数
import { createRouter, createWebHistory } from 'vue-router'

import Login from '../views/Login.vue'
import Chat from '../views/Chat.vue'

const routes = [
    {path:'/', redirect:'/chat'},
    {path:'/login', component:Login},
    {path:'/chat', component:Chat, meta:{requiresAuth: true}}
]
//createWebHistory()	URL 不带 #（如 /chat 不是 /#/chat）
const router = createRouter({
    history:createWebHistory(),
    routes
})

router.beforeEach((to, from, next) =>{
    const token = localStorage.getItem('token')
    if (to.meta.requiresAuth && !token){
        next('/login')
    }
    else if(to.path == '/login' && token){
        next('/chat')
    }
    else{
        next()
    }
})

export default router
