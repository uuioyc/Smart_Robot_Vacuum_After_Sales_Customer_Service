<template>
  <div class="app-layout">
    <!-- ===== 左侧栏 ===== -->
    <div class="sidebar">
      <button class="new-chat-btn" @click="handleNewChat">
        + 新建对话
      </button>

      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.id"
          :class="['session-item', { active: s.id === currentSessionId }]"
          @click="handleSwitchSession(s.id)"
        >
          <span class="session-title">{{ s.title }}</span>
          <button class="delete-btn" @click.stop="handleDeleteSession(s.id)">×</button>
        </div>
      </div>
    </div>

    <!-- ===== 右侧聊天区 ===== -->
    <div class="chat-container">
      <div class="top-bar">
        <span>欢迎，{{ username }}</span>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>

      <div class="messages">
    <!-- 空对话时显示引导页 -->
    <div v-if="messages.length === 0" class="welcome">
      <h2>👋 你好，我是扫地机器人客服</h2>
      <p class="welcome-sub">可以试试问我：</p>
      <div class="suggestions">
        <div
          v-for="(q, idx) in suggestions"
          :key="idx"
          class="suggestion"
          @click="sendSuggestion(q)"
        >
          {{ q }}
        </div>
      </div>
    </div>

    <!-- 有消息时正常显示 -->
    <div
      v-for="(msg, idx) in messages"
      :key="idx"
      :class="['message', msg.role]"
    >
      <div class="bubble">
        <!-- 加载动画：思考中和答案都为空时显示 -->
        <span v-if="msg.role === 'assistant' && !msg.content && !msg.thinking && loading" class="dot-loading">
          <span></span><span></span><span></span>
        </span>

        <!-- 思考过程（可折叠） -->
        <details v-if="msg.thinking" class="thinking-block">
          <summary>思考过程</summary>
          <div class="thinking-content">{{ msg.thinking }}</div>
        </details>

        <!-- 正式答案 -->
        <span v-if="msg.content">{{ msg.content }}</span>
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
          {{ loading ? '思考中...' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>


<script setup>
import {ref, onMounted} from 'vue'
import { useRouter } from 'vue-router'

//ref让数据变成响应式,当value改变时，用到他的模版计算属性等等自动更新
//可以包装任何类型

const input = ref('')
const messages = ref([])
const loading = ref(false)
const router = useRouter()
const currentSessionId = ref(
    localStorage.getItem("session_id")
    ? parseInt(localStorage.getItem("session_id"))
    : null
)     // 当前会话 id
const username = ref(localStorage.getItem("username") || '用户')
const sessions = ref([])
// ===== 引导页的示例问题 =====
const suggestions = [
  '滤网多久换一次？',
  '机器人不充电怎么办？',
  '小户型适合买什么型号？',
  '最近潮湿该怎么保养？'
]

// ===== 点击示例 → 自动填入并发送 =====
const sendSuggestion = (text) => {
  input.value = text
  send()
}
const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('username')
  localStorage.removeItem("session_id")
  router.push('/login')
}

onMounted(async () => {
  await loadSessions()
  if(!currentSessionId.value) return
  try{
    const token = localStorage.getItem("token")
    const res = await fetch(
        `http://localhost:8080/api/sessions/${currentSessionId.value}/messages`,
        {
          headers:{'Authorization': `Bearer ${token}`}
        }
    )
    if(res.status == 401){
      localStorage.removeItem("token")
      router.push("/login")
      return
    }
    if(!res.ok) return
    const data = await res.json()
    messages.value = data.map(m => ({
      role: m.role,
      content: m.content
    }))
  } catch (e) {
    console.error("加载历史消息失败:", e)
  }
})

const loadSessions = async () => {
  const token = localStorage.getItem("token")
  try{
    const res = await fetch('http://localhost:8080/api/sessions',
        {headers: { 'Authorization': `Bearer ${token}` }}
    )
    if(!res.ok) return
    sessions.value = await res.json()
  }catch (e) {
    console.error("拉取会话失败:", e)
  }
}

const handleNewChat = () =>{
  currentSessionId.value = null
  localStorage.removeItem("session_id")
  messages.value = []
}
const handleSwitchSession = async (sessionId) =>{
  if(sessionId == currentSessionId.value) return
  currentSessionId.value = sessionId
  localStorage.setItem("session_id", sessionId)
  const token = localStorage.getItem("token")

  try{
    const res = await fetch(
        `http://localhost:8080/api/sessions/${sessionId}/messages`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    )
    if(!res.ok) return
    const data = await res.json()
    messages.value = data.map(m => ({
      role: m.role,
      content: m.content
    }))
  }catch (e) {
    console.error("加载消息失败:", e)
  }
}

const handleDeleteSession = async (sessionId) => {
  if(!confirm('确定删除这个会话？')) return
  const token = localStorage.getItem("token")
  try{
    await fetch(`http://localhost:8080/api/sessions/${sessionId}`,{
      method:'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    })
    await loadSessions()
    if(sessionId === currentSessionId.value){
      currentSessionId.value = null
      localStorage.removeItem("session_id")
      messages.value = []
    }
  }catch (e) {
    console.error("删除失败：", e)
  }
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
  const token = localStorage.getItem('token')
  const userMessage = input.value
  messages.value.push({role:'user', content: userMessage})

  input.value = ''
  loading.value = true

  //先放一条空的AI消息，等会填字
  messages.value.push({role:'assistant', content:'', thinking:''})

  // 组装历史消息（去掉最后两条：当前用户消息 + 空 AI 消息）
  const history = messages.value.slice(0, -2).map(m => ({
    role:m.role,
    content:m.content,
    thinking:''
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
        session_id:currentSessionId.value,
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
      const {done, value} = await reader.read() //反复要数据
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
          if(obj.type == 'session_id'){
            currentSessionId.value = obj.session_id
            localStorage.setItem("session_id", obj.session_id)
            continue
          }
          // 思考过程 → 覆盖（不是追加）
          if (obj.type === 'thinking' && obj.content){
            messages.value[messages.value.length - 1].thinking = obj.content
          }
          // 正式答案 → 追加
          if (obj.type === 'content' && obj.content){
            messages.value[messages.value.length - 1].content += obj.content
          }
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

/* ===== 整体布局：左右两栏 ===== */
.app-layout {
  display: flex;
  height: 100vh;
}

/* ===== 左侧栏 ===== */
.sidebar {
  width: 260px;
  background: #f7f7f8;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  padding: 12px;
}

.new-chat-btn {
  padding: 10px;
  background: white;
  color: #333;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 12px;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: #f0f0f0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-item {
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: #333;
}

.session-item:hover {
  background: #ececec;
}

.session-item.active {
  background: #e0e0e0;
  font-weight: 500;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.delete-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  display: none;
  line-height: 1;
}

.session-item:hover .delete-btn {
  display: block;
}

.delete-btn:hover {
  color: #e74c3c;
}

/* ===== 右侧聊天区（原来是 chat-container）===== */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0 20px 20px 20px;
  overflow: hidden;
}

/* ===== 思考过程折叠 ===== */
.thinking-block {
  margin-bottom: 10px;
  border-left: 3px solid #ddd;
  padding-left: 10px;
}

.thinking-block summary {
  cursor: pointer;
  color: #888;
  font-size: 13px;
  user-select: none;
  list-style: none;
}

.thinking-block summary::before {
  content: '▶ ';
  font-size: 10px;
  margin-right: 4px;
}

.thinking-block[open] summary::before {
  content: '▼ ';
}

.thinking-block summary:hover {
  color: #333;
}

.thinking-content {
  margin-top: 8px;
  color: #666;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  background: #f9f9f9;
  padding: 10px;
  border-radius: 6px;
}
</style>