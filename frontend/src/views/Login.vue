<template>
  <div class="login-container">
    <div class="login-box">
      <h1>扫地机器人客服</h1>
      <p class="subtitle">请登录后使用</p>
      <!-- 用户名输入框 -->
      <!-- v-model 双向绑定 -->
      <!-- @keyup.enter 按回车也能触发登录 -->
      <input
        v-model="username"
        placeholder="用户名"
        @keyup.enter="handleLogin"
      />
       <!-- 密码输入框，type=password 会隐藏字符 -->
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        @keyup.enter="handleLogin"
      />
      <button @click="handleLogin" :disabled="loading">
        {{loading ? '登陆中...': '登陆/注册'}}
      </button>
      <p v-if="error" class="error">{{error}}</p>
    </div>

  </div>
</template>

<script setup>
  import {ref} from "vue";
  import {useRouter} from 'vue-router'
  const username = ref('')
  const password = ref('')
  const loading = ref(false)
  const error = ref('')

  // useRouter：拿到路由对象，用来跳转页面
  const router = useRouter()

  const handleLogin = async () => {
    if (!username.value || !password.value) {
      error.value = "请输入用户名和密码"
      return
    }
    loading.value = true
    error.value = ''

    try {
      let res = await fetch('http://localhost:8080/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          username: username.value,
          password: password.value
        })
      })
      if (res.status == 401) {
        res = await fetch('http://localhost:8080/api/register', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            username: username.value,
            password: password.value
          })
        })
      }
      if (!res.ok) {
        const data = await res.json() //res.json返回的是promise所以需要await
        throw new Error(data.detail || '登录失败')
        //A || B   →  如果 A 是"真值"，返回 A；否则返回 B
      }

      const data = await res.json()

      localStorage.setItem('token', data.token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('username', data.username)

      router.push('/chat')
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f0f2f5;
}

.login-box {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

h1 {
  text-align: center;
  margin: 0;
  font-size: 22px;
  color: #333;
}

.subtitle {
  text-align: center;
  color: #999;
  margin: 0 0 10px 0;
  font-size: 14px;
}

input {
  padding: 12px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #007bff;
}

button {
  padding: 12px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}

button:hover:not(:disabled) {
  background: #0056b3;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.error {
  color: #e74c3c;
  font-size: 14px;
  text-align: center;
  margin: 0;
}
</style>