<template>

  <div class="chat-container">
    <div class="top-bar">
      <span>欢迎，{{ username }}</span>
      <button class="logout-btn" @click="handleLogout">退出登录</button>
    </div>

    <h1>扫地机器人客服</h1>
    <div class="messages">
      <div v-for="(msg, idx) in messages" :key = idx :class = "['message', msg.role]">
        <!--['message', msg.role]是一个数组，代表有两个class-->
        <div class="bubble">
          <span>{{msg.content}}</span>
        </div>
      </div>
    </div>
    <div class="input-area">
      <input
        v-model="input"
        @keyup.enter="send"
        placeholder="请输入问题..."
        :disabled="loading"
      />
      <button @click="send" :disabled="loading">
        {{loading? '思考中...': '发送'}}
      </button>
    </div>
  </div>
</template>


<script setup>
import {ref} from 'vue'
import { useRouter } from 'vue-router'

//ref让数据变成响应式,当value改变时，用到他的模版计算属性等等自动更新
//可以包装任何类型

const input = ref('')
const messages = ref([])
const loading = ref(false)
const token = localStorage.getItem('token')
const router = useRouter()

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('username')
  router.push('/login')
}

const send = async () =>{
/*
*   async的作用
*   加了 async 后，返回值会被包装成 Promise：
    await 只能在 async 函数里用，或者模块顶层用。
    它的作用是等待一个 Promise 完成，并拿到结果。
    如果 await 的 Promise 失败，会抛出异常，可以被 catch 捕获。
*
* */
  //空输入 或 正在加载
  if(!input.value.trim() || loading.value) return

  const userMessage = input.value
  messages.value.push({role:'user', content: userMessage})

  input.value = ''
  loading.value = true

  //先放一条空的AI消息，等会填字
  messages.value.push({role:'assistant', content:''})

  // 组装历史消息（去掉最后两条：当前用户消息 + 空 AI 消息）
  const history = messages.value.slice(0, -2).map(m => ({
    role:m.role,
    content:m.content
  }))

  try{
    const response = await fetch('http://localhost:8080/api/chat',{
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'Authorization':`Bearer ${token}`
      },
      body:JSON.stringify({
        message:userMessage,
        session_id:'test',
        history:history
      })
    })
    //检查响应状态
    if(!response.ok) throw new Error(`HTTP ${response.status}`)
    //拿到流式读取器
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while(true){
      const {done, value} = await reader.read()
      if (done) break;
      //这个done是read的返回里面带的，就是看读没读完

      //二进制转字符串，累积到 buffer
      buffer += decoder.decode(value, {stream:true})

      //按换行切分，最后一行可能不完整，留到下次
      const lines = buffer.split('\n')
      buffer = lines.pop()
      //这里结束以后buffer里面存的就是最后不完整的一行

      //按行切分完以后，
      for (const line of lines){
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') break //此时所有后台返回的数据都读完了

        try {
          const obj = JSON.parse(data)
          messages.value[messages.value.length - 1].content += obj.content
        }catch (e) {}
      }
    }
  }catch (e) {
    //出错时显示错误
    messages.value[messages.value.length - 1].content = '出错了：' + e.message
  } finally {
    // 15. 不管成功失败，都要关闭 loading
    loading.value = false
  }
/*后端                                 前端
对象 → 字符串 → 字节流  ──网络──>  字节流 → 字符串 → 对象
* */
}
</script>
<style scoped>
.chat-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  width: 100vh;
  height: 100vh;               /* 占满整屏高度 */
  box-sizing: border-box;
}

h1 {
  font-size: 20px;
  margin: 0 0 16px 0;
  text-align: center;
  color: #333;
}

/* ===== 消息区 ===== */
.messages {
  flex: 1;                     /* 自动占满剩余高度 */
  overflow-y: auto;
  border: 1px solid #ddd;
  padding: 16px;
  margin-bottom: 12px;
  background: #fafafa;
  border-radius: 8px;
}

.message {
  display: flex;
  margin: 12px 0;
}
.message.user {
  justify-content: flex-end;
}
.message.assistant {
  justify-content: flex-start;
}

.bubble {
  text-align: left;
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  word-wrap: break-word;
  line-height: 1.5;
  white-space: pre-wrap;       /* 保留换行符 */
}

/*.message.user是同时拥有message和user属性的*/
/*.message.user .bubble是message和user下面的 bubble，注意这个空格*/
.message.user .bubble {
  background: #007bff;
  color: white;
}
.message.assistant .bubble {
  background: #f0f0f0;
  color: #333;
}

/* ===== 加载动画（跳动小点） ===== */
.dot-loading {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  height: 20px;
}
.dot-loading span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}
.dot-loading span:nth-child(1) { animation-delay: -0.32s; }
.dot-loading span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* ===== 输入区 ===== */
.input-area {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.input-area input {
  flex: 1;
  padding: 14px 16px;
  font-size: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s;
}
.input-area input:focus {
  border-color: #007bff;
}
.input-area input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.input-area button {
  padding: 14px 28px;
  font-size: 15px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}
.input-area button:hover:not(:disabled) {
  background: #0056b3;
}
.input-area button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: white;
  border-bottom: 1px solid #eee;
  margin-bottom: 12px;
}

.logout-btn {
  padding: 6px 14px;
  background: #f0f0f0;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.logout-btn:hover {
  background: #e0e0e0;
}
</style>