<template>
  <div class="manage-page">
    <header class="page-header">
      <div>
        <h1>伤情数据后台</h1>
        <p>伤员信息维护与详情查看</p>
      </div>
      <div class="header-actions">
        <span class="user">当前用户：{{ username }}</span>
        <button class="btn btn-secondary" @click="goToStatistics">数据统计</button>
        <button
          class="btn btn-secondary"
          :disabled="!isAdmin"
          :title="isAdmin ? '' : '仅系统管理员可访问'"
          @click="goToAdmin"
        >
          系统管理
        </button>
        <button class="btn btn-danger" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <main class="content-grid">
      <section class="panel">
        <div class="panel-head">
          <h2>伤员信息管理</h2>
        </div>

        <div class="query-bar">
          <input
            v-model.trim="keyword"
            class="ipt"
            placeholder="按 UID 或姓名查询"
            @keyup.enter="handleQuery"
          />
          <button class="btn btn-primary" @click="handleQuery">查询</button>
          <button class="btn btn-ghost" @click="resetQuery">重置</button>
          <div class="meta">共 {{ total }} 条</div>
        </div>

        <div v-if="loading" class="state">加载中...</div>
        <div v-else-if="objectList.length === 0" class="state">暂无数据</div>
        <div v-else class="list-wrap">
          <div class="list-head">
            <span>UID / 姓名</span>
            <span>伤情时间</span>
            <span>操作</span>
          </div>
          <div
            v-for="row in objectList"
            :key="row.uid"
            :class="['list-item', { active: selectedRow?.uid === row.uid }]"
            @click="selectRow(row)"
          >
            <div class="line1">{{ row.uid }} / {{ row.name || '-' }}</div>
            <div class="line2">{{ formatInjuryTime(row) }}</div>
            <div class="line3">
              <button class="mini" @click.stop="openEditModal(row)">修改</button>
              <button class="mini danger" @click.stop="openDeleteModal(row)">删除</button>
            </div>
          </div>
        </div>

        <div class="pager">
          <div class="pager-left">
            <span>第 {{ pageNum }} / {{ totalPages }} 页</span>
            <select v-model.number="pageSize" class="page-size" @change="changePageSize">
              <option :value="5">5 条/页</option>
              <option :value="10">10 条/页</option>
              <option :value="20">20 条/页</option>
            </select>
          </div>
          <div class="pager-right">
            <button class="btn btn-ghost" :disabled="!canPrev" @click="changePage(pageNum - 1)">
              上一页
            </button>
            <button class="btn btn-ghost" :disabled="!canNext" @click="changePage(pageNum + 1)">
              下一页
            </button>
          </div>
        </div>
      </section>

      <section class="panel detail-panel">
        <div class="panel-head">
          <h2>伤员详情</h2>
        </div>
        <div v-if="!selectedObject" class="state">请从左侧选择伤员</div>
        <div v-else-if="loadingDetail" class="state">详情加载中...</div>
        <div v-else-if="detailData" class="detail-grid">
          <div class="cell"><label>UID</label><span>{{ detailData.uid }}</span></div>
          <div class="cell"><label>姓名</label><span>{{ detailData.name || '-' }}</span></div>
          <div class="cell"><label>性别</label><span>{{ getSexText(detailData.sex) }}</span></div>
          <div class="cell"><label>年龄</label><span>{{ detailData.age ?? '-' }}</span></div>
          <div class="cell"><label>伤情时间</label><span>{{ formatInjuryTime(detailData) }}</span></div>
          <div class="cell"><label>血型</label><span>{{ detailData.blood || '-' }}</span></div>
          <div class="cell"><label>创伤</label><span>{{ detailData.isTraumaInjury ? '是' : '否' }}</span></div>
          <div class="cell"><label>Glasgow</label><span>{{ detailData.glasgow ?? '-' }}</span></div>
          <div class="cell"><label>PHI</label><span>{{ detailData.phi ?? '-' }}</span></div>
          <div class="cell"><label>START</label><span>{{ detailData.startColor || '-' }}</span></div>
          <div class="cell"><label>CRAMS</label><span>{{ detailData.crams ?? '-' }}</span></div>
          <div class="cell"><label>心率</label><span>{{ detailData.heartRate ?? '-' }}</span></div>
          <div class="cell">
            <label>血压</label>
            <span>{{ detailData.systolicPressure ?? '-' }}/{{ detailData.diastolicPressure ?? '-' }}</span>
          </div>
          <div class="cell"><label>呼吸频率</label><span>{{ detailData.respiratoryRate ?? '-' }}</span></div>
          <div class="cell"><label>血氧</label><span>{{ detailData.oxygenSaturation ?? '-' }}</span></div>
          <div class="cell"><label>体温</label><span>{{ detailData.temperature ?? '-' }}</span></div>
          <div class="cell"><label>处置建议</label><span class="badge">{{ getSuggestionText(detailData.suggestion) }}</span></div>
          <div class="cell wide"><label>受伤部位</label><span>{{ formatInjuryParts(detailData) }}</span></div>
        </div>
        <div v-else class="state">详情加载失败</div>
      </section>
    </main>

    <div v-if="showEditModal" class="modal-mask">
      <div class="modal-card modal-large">
        <div class="modal-head">
          <h3>修改伤员信息</h3>
          <button class="icon-close" @click="closeEditModal">×</button>
        </div>
        <div class="modal-body form-grid">
          <div class="form-item">
            <label>UID</label>
            <input class="ipt" :value="editForm.uid" disabled />
          </div>
          <div class="form-item">
            <label>姓名</label>
            <input class="ipt" v-model.trim="editForm.name" maxlength="30" />
          </div>
          <div class="form-item">
            <label>性别</label>
            <select class="ipt" v-model.number="editForm.sex">
              <option :value="0">未知</option>
              <option :value="1">男</option>
              <option :value="2">女</option>
            </select>
          </div>
          <div class="form-item">
            <label>年龄</label>
            <input class="ipt" type="number" min="0" max="120" step="1" v-model.number="editForm.age" />
          </div>
          <div class="form-item">
            <label>血型</label>
            <input class="ipt" v-model.trim="editForm.blood" maxlength="10" placeholder="A/B/AB/O/未知" />
          </div>
          <div class="form-item">
            <label>伤情时间</label>
            <input class="ipt" :value="editForm.vitalTimestamp || '-'" disabled />
          </div>

          <div class="form-item full-row checkbox-row">
            <label><input type="checkbox" v-model="editForm.isTraumaInjury" /> 创伤</label>
            <label><input type="checkbox" v-model="editForm.headInjury" /> 头部</label>
            <label><input type="checkbox" v-model="editForm.leftArm" /> 左臂</label>
            <label><input type="checkbox" v-model="editForm.rightArm" /> 右臂</label>
            <label><input type="checkbox" v-model="editForm.leftLeg" /> 左腿</label>
            <label><input type="checkbox" v-model="editForm.rightLeg" /> 右腿</label>
            <label><input type="checkbox" v-model="editForm.chest" /> 胸部</label>
            <label><input type="checkbox" v-model="editForm.abdomen" /> 腹部</label>
          </div>

          <div class="form-item"><label>Glasgow</label><input class="ipt" type="number" min="3" max="15" step="1" v-model.number="editForm.glasgow" /></div>
          <div class="form-item"><label>PHI</label><input class="ipt" type="number" min="0" max="12" step="1" v-model.number="editForm.phi" /></div>
          <div class="form-item">
            <label>START</label>
            <select class="ipt" v-model="editForm.startColor">
              <option value="">-</option>
              <option value="red">red</option>
              <option value="yellow">yellow</option>
              <option value="green">green</option>
              <option value="black">black</option>
            </select>
          </div>
          <div class="form-item"><label>CRAMS</label><input class="ipt" type="number" min="0" max="12" step="1" v-model.number="editForm.crams" /></div>
          <div class="form-item"><label>心率</label><input class="ipt" type="number" min="20" max="250" step="1" v-model.number="editForm.heartRate" /></div>
          <div class="form-item"><label>收缩压</label><input class="ipt" type="number" min="40" max="300" step="1" v-model.number="editForm.systolicPressure" /></div>
          <div class="form-item"><label>舒张压</label><input class="ipt" type="number" min="20" max="200" step="1" v-model.number="editForm.diastolicPressure" /></div>
          <div class="form-item"><label>呼吸频率</label><input class="ipt" type="number" min="0" max="80" step="1" v-model.number="editForm.respiratoryRate" /></div>
          <div class="form-item"><label>血氧</label><input class="ipt" type="number" min="0" max="100" step="1" v-model.number="editForm.oxygenSaturation" /></div>
          <div class="form-item"><label>体温</label><input class="ipt" type="number" min="30" max="45" step="0.1" v-model.number="editForm.temperature" /></div>

          <div class="form-item full-row">
            <label>处置建议</label>
            <select class="ipt" v-model.number="editForm.suggestion">
              <option :value="1">收容</option>
              <option :value="2">后送</option>
            </select>
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn btn-ghost" @click="closeEditModal" :disabled="modalSubmitting">取消</button>
          <button class="btn btn-primary" @click="submitEditModal" :disabled="modalSubmitting">确定</button>
        </div>
      </div>
    </div>

    <div v-if="showDeleteModal" class="modal-mask">
      <div class="modal-card modal-small">
        <div class="modal-head">
          <h3>删除确认</h3>
          <button class="icon-close" @click="closeDeleteModal">×</button>
        </div>
        <div class="modal-body">
          <p class="confirm-text">确认删除该伤员数据吗？</p>
          <p class="confirm-sub">{{ deleteTarget?.uid }} - {{ deleteTarget?.name || '未命名' }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn btn-ghost" @click="closeDeleteModal" :disabled="modalSubmitting">取消</button>
          <button class="btn btn-danger" @click="submitDeleteModal" :disabled="modalSubmitting">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import assessmentApi from '../api/assessments.js'
import authApi from '../api/auth.js'

const props = defineProps({ navigateTo: Function })

const objectList = ref([])
const selectedRow = ref(null)
const detailData = ref(null)
const loading = ref(false)
const loadingDetail = ref(false)
const selectedObject = ref(false)
const username = ref(localStorage.getItem('authUser') || '-')
const keyword = ref('')
const isAdmin = ref(false)

const pageNum = ref(1)
const pageSize = ref(10)
const total = ref(0)
const serverPages = ref(1)
const totalPages = computed(() => Math.max(1, Number(serverPages.value || 1)))
const canPrev = computed(() => pageNum.value > 1)
const canNext = computed(() => pageNum.value < totalPages.value)

const showEditModal = ref(false)
const showDeleteModal = ref(false)
const modalSubmitting = ref(false)
const deleteTarget = ref(null)

const editForm = reactive({
  uid: '',
  name: '',
  sex: 0,
  age: 0,
  blood: '',
  isTraumaInjury: false,
  headInjury: false,
  leftArm: false,
  rightArm: false,
  leftLeg: false,
  rightLeg: false,
  chest: false,
  abdomen: false,
  glasgow: 3,
  phi: 0,
  startColor: '',
  crams: 0,
  heartRate: 20,
  systolicPressure: 40,
  diastolicPressure: 20,
  respiratoryRate: 0,
  oxygenSaturation: 0,
  temperature: 36.5,
  vitalTimestamp: '',
  suggestion: 1,
  sourceRow: null
})

const num = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isNaN(parsed) ? fallback : parsed
}

const clampInt = (value, min, max, fallback = min) => {
  const parsed = Math.round(num(value, fallback))
  return Math.min(max, Math.max(min, parsed))
}

const clampDecimal = (value, min, max, fallback = min) => {
  const parsed = num(value, fallback)
  const rounded = Math.round(parsed * 10) / 10
  return Math.min(max, Math.max(min, rounded))
}

const normalizeSuggestion = (value) => (Number(value) === 2 ? 2 : 1)

const normalizeBlood = (value) => {
  const text = String(value || '').trim().toUpperCase()
  if (text === 'UNKNOWN') return '未知'
  return text
}

const validateBloodType = (value) => {
  const blood = normalizeBlood(value)
  if (!blood) return true
  return ['A', 'B', 'AB', 'O', '未知'].includes(blood)
}

const validateEditForm = () => {
  if (editForm.name && editForm.name.length > 30) return '姓名长度不能超过 30 个字符'
  if (!validateBloodType(editForm.blood)) return '血型仅允许 A、B、AB、O 或 未知'
  if (num(editForm.age, 0) < 0 || num(editForm.age, 0) > 120) return '年龄必须在 0 到 120 之间'
  if (num(editForm.glasgow, 0) < 3 || num(editForm.glasgow, 0) > 15) return 'Glasgow 必须在 3 到 15 之间'
  if (num(editForm.phi, 0) < 0 || num(editForm.phi, 0) > 12) return 'PHI 必须在 0 到 12 之间'
  if (num(editForm.crams, 0) < 0 || num(editForm.crams, 0) > 12) return 'CRAMS 必须在 0 到 12 之间'
  if (num(editForm.heartRate, 0) < 20 || num(editForm.heartRate, 0) > 250) return '心率必须在 20 到 250 之间'
  if (num(editForm.systolicPressure, 0) < 40 || num(editForm.systolicPressure, 0) > 300) return '收缩压必须在 40 到 300 之间'
  if (num(editForm.diastolicPressure, 0) < 20 || num(editForm.diastolicPressure, 0) > 200) return '舒张压必须在 20 到 200 之间'
  if (num(editForm.diastolicPressure, 0) > num(editForm.systolicPressure, 0)) return '舒张压不能大于收缩压'
  if (num(editForm.respiratoryRate, 0) < 0 || num(editForm.respiratoryRate, 0) > 80) return '呼吸频率必须在 0 到 80 之间'
  if (num(editForm.oxygenSaturation, 0) < 0 || num(editForm.oxygenSaturation, 0) > 100) return '血氧必须在 0 到 100 之间'
  if (num(editForm.temperature, 0) < 30 || num(editForm.temperature, 0) > 45) return '体温必须在 30.0 到 45.0 之间'
  if (editForm.startColor && !['red', 'yellow', 'green', 'black'].includes(editForm.startColor)) return 'START 分级无效'
  return ''
}

const goToLogin = () => {
  localStorage.removeItem('authToken')
  localStorage.removeItem('authUser')
  localStorage.removeItem('authRoles')
  if (props.navigateTo) props.navigateTo('/login')
  else window.location.hash = '/login'
}

const checkAuth = async () => {
  try {
    const res = await authApi.me()
    if (res.code !== 0) {
      goToLogin()
      return false
    }
    username.value = res.data?.username || username.value
    const roles = res.data?.roles || res.data?.role_codes || []
    localStorage.setItem('authRoles', JSON.stringify(roles))
    isAdmin.value = Array.isArray(roles) && roles.includes('ADMIN')
    return true
  } catch {
    goToLogin()
    return false
  }
}

const normalizeRow = (row) => ({
  ...row,
  isTraumaInjury: !!(row?.isTraumaInjury || row?.is_trauma_injury),
  headInjury: !!(row?.headInjury || row?.head_injury),
  leftArm: !!(row?.leftArm || row?.left_arm),
  rightArm: !!(row?.rightArm || row?.right_arm),
  leftLeg: !!(row?.leftLeg || row?.left_leg),
  rightLeg: !!(row?.rightLeg || row?.right_leg),
  vitalTimestamp: row?.vitalTimestamp ?? row?.vital_timestamp ?? '',
  startColor: row?.startColor ?? row?.start_color ?? '',
  heartRate: row?.heartRate ?? row?.heart_rate ?? null,
  systolicPressure: row?.systolicPressure ?? row?.systolic_pressure ?? null,
  diastolicPressure: row?.diastolicPressure ?? row?.diastolic_pressure ?? null,
  respiratoryRate: row?.respiratoryRate ?? row?.respiratory_rate ?? null,
  oxygenSaturation: row?.oxygenSaturation ?? row?.oxygen_saturation ?? null,
  suggestion: normalizeSuggestion(row?.suggestion)
})

const refreshList = async () => {
  loading.value = true
  try {
    const res = await assessmentApi.getPatientPage(pageNum.value, pageSize.value, keyword.value)
    const pageData = res.data || {}
    objectList.value = (pageData.records || []).map(normalizeRow)
    total.value = Number(pageData.total || 0)
    serverPages.value = Number(pageData.pages || 1)
    pageNum.value = Number(pageData.current || pageNum.value || 1)
  } catch {
    alert('获取分页列表失败，请检查后端服务')
  } finally {
    loading.value = false
  }
}

const handleQuery = async () => {
  pageNum.value = 1
  await refreshList()
}

const resetQuery = async () => {
  keyword.value = ''
  pageNum.value = 1
  await refreshList()
}

const changePage = async (nextPage) => {
  if (nextPage < 1 || nextPage > totalPages.value) return
  pageNum.value = nextPage
  await refreshList()
}

const changePageSize = async () => {
  pageNum.value = 1
  await refreshList()
}

const openEditModal = (row) => {
  editForm.uid = row.uid
  editForm.name = row.name || ''
  editForm.sex = [0, 1, 2].includes(num(row.sex, 0)) ? num(row.sex, 0) : 0
  editForm.age = clampInt(row.age, 0, 120, 0)
  editForm.blood = row.blood || ''
  editForm.isTraumaInjury = !!row.isTraumaInjury
  editForm.headInjury = !!row.headInjury
  editForm.leftArm = !!row.leftArm
  editForm.rightArm = !!row.rightArm
  editForm.leftLeg = !!row.leftLeg
  editForm.rightLeg = !!row.rightLeg
  editForm.chest = !!row.chest
  editForm.abdomen = !!row.abdomen
  editForm.glasgow = clampInt(row.glasgow, 3, 15, 3)
  editForm.phi = clampInt(row.phi, 0, 12, 0)
  editForm.startColor = row.startColor || ''
  editForm.crams = clampInt(row.crams, 0, 12, 0)
  editForm.heartRate = clampInt(row.heartRate, 20, 250, 20)
  editForm.systolicPressure = clampInt(row.systolicPressure, 40, 300, 40)
  editForm.diastolicPressure = clampInt(row.diastolicPressure, 20, 200, 20)
  editForm.respiratoryRate = clampInt(row.respiratoryRate, 0, 80, 0)
  editForm.oxygenSaturation = clampInt(row.oxygenSaturation, 0, 100, 0)
  editForm.temperature = clampDecimal(row.temperature, 30, 45, 36.5)
  editForm.vitalTimestamp = row.vitalTimestamp || ''
  editForm.suggestion = normalizeSuggestion(row.suggestion)
  editForm.sourceRow = { ...row }
  showEditModal.value = true
}

const closeEditModal = () => {
  if (modalSubmitting.value) return
  showEditModal.value = false
}

const submitEditModal = async () => {
  if (!editForm.uid) return
  const validationMessage = validateEditForm()
  if (validationMessage) {
    alert(validationMessage)
    return
  }
  modalSubmitting.value = true
  try {
    const payload = {
      ...editForm.sourceRow,
      uid: editForm.uid,
      name: editForm.name || '',
      sex: [0, 1, 2].includes(num(editForm.sex, 0)) ? num(editForm.sex, 0) : 0,
      age: clampInt(editForm.age, 0, 120, 0),
      blood: normalizeBlood(editForm.blood),
      isTraumaInjury: !!editForm.isTraumaInjury,
      headInjury: !!editForm.headInjury,
      leftArm: !!editForm.leftArm,
      rightArm: !!editForm.rightArm,
      leftLeg: !!editForm.leftLeg,
      rightLeg: !!editForm.rightLeg,
      chest: !!editForm.chest,
      abdomen: !!editForm.abdomen,
      glasgow: clampInt(editForm.glasgow, 3, 15, 3),
      phi: clampInt(editForm.phi, 0, 12, 0),
      startColor: editForm.startColor || null,
      crams: clampInt(editForm.crams, 0, 12, 0),
      heartRate: clampInt(editForm.heartRate, 20, 250, 20),
      systolicPressure: clampInt(editForm.systolicPressure, 40, 300, 40),
      diastolicPressure: clampInt(editForm.diastolicPressure, 20, 200, 20),
      respiratoryRate: clampInt(editForm.respiratoryRate, 0, 80, 0),
      oxygenSaturation: clampInt(editForm.oxygenSaturation, 0, 100, 0),
      temperature: clampDecimal(editForm.temperature, 30, 45, 36.5),
      vitalTimestamp: editForm.sourceRow?.vitalTimestamp ?? editForm.vitalTimestamp ?? '',
      suggestion: normalizeSuggestion(editForm.suggestion)
    }
    const res = await assessmentApi.updateAssessment(payload)
    alert(res.msg)
    showEditModal.value = false
    await refreshList()
    if (selectedRow.value?.uid === payload.uid) {
      await selectRow(payload)
    }
  } finally {
    modalSubmitting.value = false
  }
}

const openDeleteModal = (row) => {
  deleteTarget.value = row
  showDeleteModal.value = true
}

const closeDeleteModal = () => {
  if (modalSubmitting.value) return
  showDeleteModal.value = false
  deleteTarget.value = null
}

const submitDeleteModal = async () => {
  if (!deleteTarget.value?.uid) return
  modalSubmitting.value = true
  try {
    const res = await assessmentApi.deleteAssessment(deleteTarget.value.uid)
    alert(res.msg)
    showDeleteModal.value = false
    deleteTarget.value = null
    if (selectedRow.value?.uid === deleteTarget.value?.uid) {
      selectedRow.value = null
      detailData.value = null
      selectedObject.value = false
    }
    await refreshList()
  } finally {
    modalSubmitting.value = false
  }
}

const selectRow = async (row) => {
  selectedRow.value = row
  selectedObject.value = true
  loadingDetail.value = true
  try {
    const res = await assessmentApi.getPatientDetail(row.uid)
    detailData.value = normalizeRow(res.data)
  } catch {
    alert('获取详情失败，请检查网络或后端接口')
  } finally {
    loadingDetail.value = false
  }
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  const parsed = new Date(dateString)
  if (Number.isNaN(parsed.getTime())) return String(dateString)
  return parsed.toLocaleString('zh-CN')
}

const formatInjuryTime = (row) => formatDate(row?.vitalTimestamp ?? row?.vital_timestamp ?? null)

const formatInjuryParts = (row) => {
  const parts = []
  if (row?.headInjury) parts.push('头部')
  if (row?.leftArm) parts.push('左臂')
  if (row?.rightArm) parts.push('右臂')
  if (row?.leftLeg) parts.push('左腿')
  if (row?.rightLeg) parts.push('右腿')
  if (row?.chest) parts.push('胸部')
  if (row?.abdomen) parts.push('腹部')
  return parts.join('、')
}

const getSexText = (sex) => {
  if (Number(sex) === 1) return '男'
  if (Number(sex) === 2) return '女'
  return '未知'
}

const getSuggestionText = (suggestion) => {
  if (Number(suggestion) === 1) return '收容'
  if (Number(suggestion) === 2) return '后送'
  return '未知'
}

const goToStatistics = () => {
  if (props.navigateTo) props.navigateTo('/statistics')
  else window.location.hash = '/statistics'
}

const goToAdmin = () => {
  if (!isAdmin.value) {
    alert('当前账号无系统管理权限')
    return
  }
  if (props.navigateTo) props.navigateTo('/admin')
  else window.location.hash = '/admin'
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
  await refreshList()
})
</script>

<style scoped>
.manage-page {
  min-height: 100vh;
  padding: 16px;
  color: #e8f6ff;
  background:
    radial-gradient(circle at 20% 0%, #18344a 0%, transparent 45%),
    radial-gradient(circle at 100% 100%, #102435 0%, transparent 40%),
    linear-gradient(145deg, #0a1620, #0f2735);
}

.page-header,
.panel {
  backdrop-filter: blur(8px);
  background: rgba(13, 33, 46, 0.72);
  border: 1px solid rgba(121, 199, 255, 0.26);
  box-shadow: 0 8px 30px rgba(4, 14, 24, 0.45);
  border-radius: 14px;
}

.page-header {
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.content-grid {
  display: grid;
  grid-template-columns: 460px 1fr;
  gap: 12px;
  height: calc(100vh - 104px);
}

.panel {
  padding: 12px;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-head {
  margin-bottom: 10px;
}

.query-bar {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.ipt,
.page-size {
  height: 34px;
  border-radius: 9px;
  border: 1px solid rgba(121, 199, 255, 0.35);
  background: rgba(9, 44, 63, 0.65);
  color: #eaf7ff;
  padding: 0 10px;
}

.list-wrap {
  overflow: auto;
  border: 1px solid rgba(121, 199, 255, 0.22);
  border-radius: 10px;
  background: rgba(6, 28, 40, 0.38);
}

.list-head,
.list-item {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
}

.list-item.active {
  background: rgba(26, 73, 102, 0.55);
}

.line3,
.pager-right {
  display: flex;
  gap: 8px;
}

.pager {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-panel {
  overflow: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.cell {
  border: 1px solid rgba(121, 199, 255, 0.2);
  background: rgba(6, 28, 40, 0.4);
  border-radius: 8px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.cell.wide {
  grid-column: span 2;
}

.badge {
  display: inline-flex;
  width: fit-content;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(46, 200, 255, 0.18);
  border: 1px solid rgba(46, 200, 255, 0.55);
}

.btn,
.mini {
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  padding: 0 12px;
  cursor: pointer;
  color: #eaf7ff;
  font-size: 13px;
}

.mini {
  height: 26px;
  background: rgba(9, 44, 63, 0.7);
}

.btn-primary {
  background: linear-gradient(135deg, #1f8fbf, #2068aa);
}

.btn-secondary,
.btn-ghost {
  background: rgba(9, 44, 63, 0.8);
}

.btn-danger,
.mini.danger {
  background: rgba(85, 28, 38, 0.75);
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(1, 12, 20, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
  padding: 14px;
}

.modal-card {
  width: min(520px, 96vw);
  border-radius: 12px;
  border: 1px solid rgba(121, 199, 255, 0.28);
  background: linear-gradient(160deg, rgba(10, 36, 52, 0.95), rgba(8, 26, 39, 0.95));
}

.modal-large {
  width: min(860px, 96vw);
}

.modal-small {
  width: min(420px, 96vw);
}

.modal-head,
.modal-foot {
  padding: 12px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-body {
  padding: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  max-height: 60vh;
  overflow: auto;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.full-row {
  grid-column: 1 / -1;
}

.checkbox-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

@media (max-width: 1280px) {
  .content-grid {
    grid-template-columns: 1fr;
    height: auto;
  }
}

@media (max-width: 768px) {
  .query-bar,
  .form-grid,
  .detail-grid,
  .list-head,
  .list-item {
    grid-template-columns: 1fr;
  }

  .cell.wide {
    grid-column: auto;
  }

  .checkbox-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
