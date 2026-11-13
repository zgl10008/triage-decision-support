<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Manage from './components/Manage.vue'
import Statistics from './components/Statistics.vue'
import Login from './components/Login.vue'
import SystemAdmin from './components/SystemAdmin.vue'
import InjuryAssessmentSystem from './components/InjuryAssessmentSystem.vue'

const hasToken = () => !!localStorage.getItem('authToken')

const resolveInitialRoute = () => {
  const route = window.location.hash.slice(1) || ''
  if (route) return route
  return hasToken() ? '/manage' : '/login'
}

const currentRoute = ref(resolveInitialRoute())
const hasAdminRole = () => {
  try {
    const roles = JSON.parse(localStorage.getItem('authRoles') || '[]')
    return Array.isArray(roles) && roles.includes('ADMIN')
  } catch {
    return false
  }
}

const normalizeRoute = (route) => {
  if (!route || route === '/') {
    return hasToken() ? '/manage' : '/login'
  }
  if ((route === '/manage' || route === '/statistics' || route === '/admin') && !hasToken()) {
    return '/login'
  }
  if (route === '/admin' && !hasAdminRole()) {
    return '/manage'
  }
  return route
}

const handleHashChange = () => {
  const route = window.location.hash.slice(1) || ''
  const finalRoute = normalizeRoute(route)
  if (finalRoute !== route) {
    window.location.hash = finalRoute
    return
  }
  currentRoute.value = finalRoute
}

const navigateTo = (path) => {
  const finalRoute = normalizeRoute(path)
  window.location.hash = finalRoute
  currentRoute.value = finalRoute
}

onMounted(() => {
  handleHashChange()
  window.addEventListener('hashchange', handleHashChange)
})

onUnmounted(() => {
  window.removeEventListener('hashchange', handleHashChange)
})
</script>

<template>
  <div id="app">
    <Login v-if="currentRoute === '/login'" :navigate-to="navigateTo" />
    <Manage v-else-if="currentRoute === '/manage'" :navigate-to="navigateTo" />
    <Statistics v-else-if="currentRoute === '/statistics'" :navigate-to="navigateTo" />
    <SystemAdmin v-else-if="currentRoute === '/admin'" :navigate-to="navigateTo" />
    <InjuryAssessmentSystem v-else-if="currentRoute === '/field'" />
    <div v-else class="not-found">
      <h1>页面未找到</h1>
      <button @click="navigateTo('/login')">返回后台</button>
    </div>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  overflow: hidden;
}
#app { height: 100vh; width: 100vw; }
.not-found {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  height: 100vh; color: white; text-align: center;
}
.not-found h1 { font-size: 3rem; margin-bottom: 2rem; text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5); }
.not-found button {
  padding: 1rem 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white; border: none; border-radius: 8px; font-size: 1.1rem; cursor: pointer;
  transition: all 0.3s ease;
}
.not-found button:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4); }
</style>
