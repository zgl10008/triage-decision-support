<template>
  <div class="statistics-page">
    <header class="header card">
      <div>
        <h1>伤情数据统计</h1>
        <p class="subtitle">按记录总量、人群特征、评分分布与受伤部位进行统计</p>
      </div>
      <div class="actions">
        <span class="user-chip">用户：{{ username }}</span>
        <span class="time-chip">更新时间：{{ lastUpdatedText }}</span>
        <button class="btn btn-refresh" :disabled="loading" @click="loadData">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="btn" @click="goToManage">返回管理页</button>
        <button class="btn btn-logout" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <div v-if="loading" class="state loading-state card">统计数据加载中...</div>
    <div v-else-if="loadError" class="state error-state card">{{ loadError }}</div>

    <template v-else>
      <section class="cards">
        <div class="card metric-card">
          <div class="label">总记录数</div>
          <div class="value">{{ totalRecords }}</div>
          <div class="hint">所有伤员评估记录</div>
        </div>
      </section>

      <section class="panel-grid">
        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>各性别占比</h3>
          </div>
          <div v-if="genderStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in genderStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>年龄分布</h3>
            <span class="panel-desc">0-18，19-30，31-45，45-60，60+</span>
          </div>
          <div v-if="ageStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in ageStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>血型分布</h3>
          </div>
          <div v-if="bloodStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in bloodStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>受伤部位统计</h3>
          </div>
          <div v-if="injuryPartStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in injuryPartStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>Glasgow 分数分布</h3>
            <span class="panel-desc">3-8 重度，9-12 中度，13-15 轻度</span>
          </div>
          <div v-if="glasgowStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in glasgowStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>START 分级分布</h3>
            <span class="panel-desc">按颜色分类</span>
          </div>
          <div v-if="startStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in startStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>简易创伤计分法</h3>
            <span class="panel-desc">0-5 危重伤，6-9 重伤，10-11 中度伤，12 轻度</span>
          </div>
          <div v-if="cramsStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in cramsStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>

        <section class="panel card">
          <div class="panel-title-wrap">
            <h3>PHI 分数统计</h3>
            <span class="panel-desc">小于 3 分为轻伤，3-7 分为中伤，大于 7 分为重伤</span>
          </div>
          <div v-if="phiStats.length === 0" class="state">暂无数据</div>
          <div v-else class="stat-list">
            <div v-for="item in phiStats" :key="item.name" class="stat-item">
              <div class="stat-main">
                <span class="stat-name">{{ item.name }}</span>
                <span class="stat-percent">{{ item.percent }}%</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: `${item.percent}%` }"></div>
              </div>
              <div class="stat-count">{{ item.count }} 例</div>
            </div>
          </div>
        </section>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import assessmentApi from '../api/assessments.js'
import authApi from '../api/auth.js'

const props = defineProps({
  navigateTo: {
    type: Function,
    required: false
  }
})

const loading = ref(false)
const loadError = ref('')
const username = ref(localStorage.getItem('authUser') || '-')
const rows = ref([])
const lastUpdated = ref(null)

const totalRecords = computed(() => rows.value.length)

const lastUpdatedText = computed(() => {
  if (!lastUpdated.value) return '-'
  return new Date(lastUpdated.value).toLocaleString('zh-CN', { hour12: false })
})

const getRowValue = (row, camelKey, snakeKey = null) => row?.[camelKey] ?? row?.[snakeKey ?? camelKey] ?? null

const percentOfTotal = (count) => {
  if (totalRecords.value === 0) return '0.0'
  return ((count / totalRecords.value) * 100).toFixed(1)
}

const buildStats = (entries) =>
  entries.map(([name, count]) => ({
    name,
    count,
    percent: percentOfTotal(count)
  }))

const normalizeSex = (value) => {
  const normalized = String(value ?? '').trim()
  if (normalized === '1' || normalized === '男') return '男'
  if (normalized === '2' || normalized === '女') return '女'
  return '未知'
}

const normalizeBlood = (value) => {
  const blood = String(value ?? '').trim().toUpperCase()
  if (!blood || blood === 'UNKNOWN') return '未知'
  if (['A', 'B', 'AB', 'O'].includes(blood)) return blood
  return '未知'
}

const normalizeStart = (value) => {
  const color = String(value ?? '').trim().toLowerCase()
  const mapping = {
    red: '红色',
    yellow: '黄色',
    green: '绿色',
    black: '黑色'
  }
  return mapping[color] || '未分级'
}

const hasInjuryFlag = (row, keys) =>
  keys.some((key) => {
    const value = row?.[key]
    return value === true || value === 1 || value === '1'
  })

const genderStats = computed(() => {
  const count = { 男: 0, 女: 0, 未知: 0 }
  rows.value.forEach((row) => {
    count[normalizeSex(getRowValue(row, 'sex'))] += 1
  })
  return buildStats(Object.entries(count))
})

const ageStats = computed(() => {
  const count = {
    '0-18': 0,
    '19-30': 0,
    '31-45': 0,
    '45-60': 0,
    '60+': 0,
    未知: 0
  }

  rows.value.forEach((row) => {
    const age = Number(getRowValue(row, 'age'))
    if (!Number.isFinite(age) || age < 0) {
      count.未知 += 1
    } else if (age <= 18) {
      count['0-18'] += 1
    } else if (age <= 30) {
      count['19-30'] += 1
    } else if (age <= 45) {
      count['31-45'] += 1
    } else if (age <= 60) {
      count['45-60'] += 1
    } else {
      count['60+'] += 1
    }
  })

  return buildStats(Object.entries(count))
})

const bloodStats = computed(() => {
  const count = { A: 0, B: 0, AB: 0, O: 0, 未知: 0 }
  rows.value.forEach((row) => {
    count[normalizeBlood(getRowValue(row, 'blood'))] += 1
  })
  return buildStats(Object.entries(count))
})

const injuryPartStats = computed(() => {
  const definitions = [
    ['头部', ['headInjury', 'head_injury']],
    ['左臂', ['leftArm', 'left_arm']],
    ['右臂', ['rightArm', 'right_arm']],
    ['左腿', ['leftLeg', 'left_leg']],
    ['右腿', ['rightLeg', 'right_leg']],
    ['胸部', ['chest']],
    ['腹部', ['abdomen']]
  ]

  const count = Object.fromEntries(definitions.map(([label]) => [label, 0]))
  rows.value.forEach((row) => {
    definitions.forEach(([label, keys]) => {
      if (hasInjuryFlag(row, keys)) {
        count[label] += 1
      }
    })
  })

  return buildStats(Object.entries(count)).sort((a, b) => b.count - a.count)
})

const glasgowStats = computed(() => {
  const count = { 重度: 0, 中度: 0, 轻度: 0, 未知: 0 }
  rows.value.forEach((row) => {
    const score = Number(getRowValue(row, 'glasgow'))
    if (!Number.isFinite(score)) {
      count.未知 += 1
    } else if (score >= 3 && score <= 8) {
      count.重度 += 1
    } else if (score >= 9 && score <= 12) {
      count.中度 += 1
    } else if (score >= 13 && score <= 15) {
      count.轻度 += 1
    } else {
      count.未知 += 1
    }
  })
  return buildStats(Object.entries(count))
})

const startStats = computed(() => {
  const count = { 红色: 0, 黄色: 0, 绿色: 0, 黑色: 0, 未分级: 0 }
  rows.value.forEach((row) => {
    count[normalizeStart(getRowValue(row, 'startColor', 'start_color'))] += 1
  })
  return buildStats(Object.entries(count))
})

const cramsStats = computed(() => {
  const count = { 危重伤: 0, 重伤: 0, 中度伤: 0, 轻度: 0, 未知: 0 }
  rows.value.forEach((row) => {
    const score = Number(getRowValue(row, 'crams'))
    if (!Number.isFinite(score)) {
      count.未知 += 1
    } else if (score >= 0 && score <= 5) {
      count.危重伤 += 1
    } else if (score >= 6 && score <= 9) {
      count.重伤 += 1
    } else if (score >= 10 && score <= 11) {
      count.中度伤 += 1
    } else if (score === 12) {
      count.轻度 += 1
    } else {
      count.未知 += 1
    }
  })
  return buildStats(Object.entries(count))
})

const phiStats = computed(() => {
  const count = { 轻伤: 0, 中伤: 0, 重伤: 0, 未知: 0 }
  rows.value.forEach((row) => {
    const score = Number(getRowValue(row, 'phi'))
    if (!Number.isFinite(score)) {
      count.未知 += 1
    } else if (score < 3) {
      count.轻伤 += 1
    } else if (score <= 7) {
      count.中伤 += 1
    } else {
      count.重伤 += 1
    }
  })
  return buildStats(Object.entries(count))
})

const goToLogin = () => {
  localStorage.removeItem('authToken')
  localStorage.removeItem('authUser')
  if (props.navigateTo) {
    props.navigateTo('/login')
  } else {
    window.location.hash = '/login'
  }
}

const goToManage = () => {
  if (props.navigateTo) {
    props.navigateTo('/manage')
  } else {
    window.location.hash = '/manage'
  }
}

const checkAuth = async () => {
  try {
    const res = await authApi.me()
    if (res.code !== 0) {
      goToLogin()
      return false
    }
    username.value = res.data?.username || username.value
    return true
  } catch {
    goToLogin()
    return false
  }
}

const loadData = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const res = await assessmentApi.getPatientList()
    rows.value = Array.isArray(res.data) ? res.data : []
    lastUpdated.value = Date.now()
  } catch {
    loadError.value = '获取统计数据失败，请检查后端服务状态'
  } finally {
    loading.value = false
  }
}

const handleLogout = async () => {
  try {
    await authApi.logout()
  } finally {
    goToLogin()
  }
}

onMounted(async () => {
  const ok = await checkAuth()
  if (!ok) return
  await loadData()
})
</script>

<style scoped>
.statistics-page {
  --bg-1: #0a1620;
  --bg-2: #0f2735;
  --panel: rgba(13, 33, 46, 0.7);
  --line: rgba(121, 199, 255, 0.26);
  --text: #e8f6ff;
  --sub: #aac5d7;
  --accent: #2ec8ff;
  --accent-2: #1f8fbf;
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  padding: 20px;
  background:
    radial-gradient(circle at 20% 0%, #18344a 0%, transparent 45%),
    radial-gradient(circle at 100% 100%, #102435 0%, transparent 40%),
    linear-gradient(145deg, var(--bg-1), var(--bg-2));
  color: var(--text);
  scrollbar-width: thin;
  scrollbar-color: rgba(46, 200, 255, 0.75) rgba(9, 44, 63, 0.45);
}

.statistics-page::-webkit-scrollbar {
  width: 10px;
}

.statistics-page::-webkit-scrollbar-track {
  background: rgba(9, 44, 63, 0.45);
}

.statistics-page::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(46, 200, 255, 0.85), rgba(32, 104, 170, 0.9));
}

.statistics-page::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(83, 215, 255, 0.95), rgba(46, 200, 255, 0.95));
}

.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(4, 14, 24, 0.45);
  backdrop-filter: blur(8px);
}

.header {
  padding: 18px;
  margin-bottom: 16px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

h1 {
  margin: 0;
  font-size: 28px;
}

.subtitle {
  margin-top: 6px;
  color: var(--sub);
  font-size: 14px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.user-chip,
.time-chip {
  height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 8px;
  background: rgba(9, 44, 63, 0.5);
  color: var(--sub);
  font-size: 13px;
  border: 1px solid rgba(121, 199, 255, 0.35);
}

.btn {
  height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(121, 199, 255, 0.35);
  background: rgba(9, 44, 63, 0.8);
  color: var(--text);
  border-radius: 8px;
  cursor: pointer;
}

.btn-refresh {
  background: linear-gradient(135deg, var(--accent-2), #2068aa);
}

.btn-logout {
  background: rgba(85, 28, 38, 0.75);
}

.cards {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.metric-card {
  padding: 14px;
}

.label,
.hint,
.panel-desc,
.state {
  color: var(--sub);
}

.value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}

.hint {
  margin-top: 8px;
  font-size: 12px;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  padding: 16px;
}

.panel-title-wrap {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.panel-title-wrap h3 {
  margin: 0;
  font-size: 20px;
}

.stat-list {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.stat-item {
  display: grid;
  grid-template-columns: 180px 1fr 76px;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  background: rgba(6, 28, 40, 0.38);
  border-radius: 10px;
  border: 1px solid rgba(121, 199, 255, 0.2);
}

.stat-main {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.stat-name {
  font-weight: 600;
}

.bar-track {
  position: relative;
  height: 10px;
  border-radius: 8px;
  background: rgba(121, 199, 255, 0.2);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--accent) 0%, #2068aa 100%);
}

.stat-count {
  text-align: right;
  font-weight: 600;
}

.loading-state,
.error-state {
  margin-bottom: 12px;
  padding: 14px 16px;
}

.error-state {
  background: rgba(85, 28, 38, 0.75);
}

@media (max-width: 1240px) {
  .panel-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .statistics-page {
    padding: 14px;
  }

  .header {
    flex-direction: column;
    align-items: stretch;
  }

  .actions {
    justify-content: flex-start;
  }

  .stat-item {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .stat-count {
    text-align: left;
  }
}
</style>
