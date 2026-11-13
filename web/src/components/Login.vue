<template>
  <div class="login-page">
    <div class="login-card">
      <h2>智能信息管理与辅助决策系统</h2>
      <p class="login-sub">灾害现场伤情辅助决策</p>
      <div class="form-item">
        <label>用户名</label>
        <input v-model.trim="form.username" type="text" placeholder="请输入用户名" />
      </div>
      <div class="form-item">
        <label>密码</label>
        <input v-model="form.password" type="password" placeholder="请输入密码" @keyup.enter="submitLogin" />
      </div>
      <button class="btn-login" :disabled="loading" @click="submitLogin">
        {{ loading ? '登录中...' : '登录' }}
      </button>
      <p class="hint">如需创建账号联系系统管理员</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import authApi from '../api/auth'

const props = defineProps({
  navigateTo: {
    type: Function,
    required: false
  }
})

const form = reactive({
  username: '',
  password: ''
})
const loading = ref(false)

const goManage = () => {
  if (props.navigateTo) {
    props.navigateTo('/manage')
  } else {
    window.location.hash = '/manage'
  }
}

const clearAuth = () => {
  localStorage.removeItem('authToken')
  localStorage.removeItem('authUser')
  localStorage.removeItem('authRoles')
}

const submitLogin = async () => {
  if (!form.username || !form.password) {
    alert('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await authApi.login({
      username: form.username,
      password: form.password
    })
    if (res.code !== 0 || !res.data?.token) {
      alert(res.msg || '登录失败')
      return
    }

    const roles = res.data?.roles || res.data?.role_codes || []
    localStorage.setItem('authToken', res.data.token)
    localStorage.setItem('authUser', res.data.username || form.username)
    localStorage.setItem('authRoles', JSON.stringify(roles))
    goManage()
  } catch {
    alert('登录失败，请检查后端服务与账号密码')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const token = localStorage.getItem('authToken')
  if (!token) return
  try {
    const res = await authApi.me()
    if (res.code === 0) {
      const roles = res.data?.roles || res.data?.role_codes || []
      localStorage.setItem('authRoles', JSON.stringify(roles))
      goManage()
    } else {
      clearAuth()
    }
  } catch {
    clearAuth()
  }
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
}

.login-card {
  width: 380px;
  max-width: calc(100vw - 32px);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 12px;
  padding: 24px;
  color: #fff;
  backdrop-filter: blur(6px);
}

.login-card h2 {
  margin: 0 0 4px;
  font-size: 21px;
  line-height: 1.35;
}

.login-sub {
  margin: 0 0 18px;
  font-size: 13px;
  opacity: 0.75;
}

.form-item {
  margin-bottom: 14px;
}

.form-item label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
}

.form-item input {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  padding: 0 12px;
}

.form-item input::placeholder {
  color: rgba(255, 255, 255, 0.7);
}

.btn-login {
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #1cb5e0 0%, #000851 100%);
}

.btn-login:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  opacity: 0.8;
}
</style>
