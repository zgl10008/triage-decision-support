<template>
  <!-- 创伤伤情评估系统-主容器 -->
  <div class="injury-assessment-system">
    <!-- 患者信息区域 - 顶部核心信息录入区 -->
    <section class="patient-info-header">
      <div class="patient-form-single-line">
        <div class="patient-basic-info">
          <div class="info-group">
            <label>患者ID:</label>
            <input type="text" v-model="patientData.id" class="input-field compact" placeholder="输入ID" />
          </div>
          <div class="info-group">
            <label>姓名:</label>
            <input type="text" v-model="patientData.name" class="input-field compact" placeholder="患者姓名" />
          </div>
          <div class="info-group">
            <label>性别:</label>
            <div class="radio-group compact">
              <label class="radio-label"><input type="radio" v-model="patientData.gender" value="男" /> 男</label>
              <label class="radio-label"><input type="radio" v-model="patientData.gender" value="女" /> 女</label>
            </div>
          </div>
          <div class="info-group">
            <label>年龄:</label>
            <input type="number" v-model="patientData.age" class="input-field compact small" placeholder="年龄" />
          </div>
          <div class="info-group">
            <label>血型:</label>
            <select v-model="patientData.bloodType" class="input-field compact">
              <option value="">请选择血型</option>
              <option v-for="type in bloodTypes" :key="type" :value="type">{{ type }}</option>
            </select>
          </div>
        </div>
        <div class="action-buttons-group">
          <button class="btn-primary" @click="addNewPatient">新增患者</button>
          <button class="btn-cancel" @click="cancelForm">取消</button>
          <button class="btn-secondary" @click="toggleFullscreen">{{ isFullscreen ? '-' : '+' }}</button>
        </div>
      </div>
    </section>

    <!-- 主要内容区域 - 核心三栏布局 -->
    <main class="main-content">
      <!-- 左栏：身体受伤信息+体征测量组件 -->
      <section class="left-column">
        <!-- 人体受伤评估组件-监听伤情/部位/严重度变化 -->
        <HumanBodyModel 
          @injury-type-change="handleInjuryTypeChange" 
          @injured-parts-change="handleInjuredPartsChange"
          @severity-change="handleSeverityChange" 
        />
        <!-- 体征测量滚动容器 -->
        <div class="vital-signs-scroll-container">
          <VitalSigns @vital-data-change="handleVitalDataChange" />
        </div>
      </section>

      <!-- 中栏：评分系统标签页组件 -->
      <section class="center-column">
        <ScoreAssessment @score-change="handleScoreChange" />
      </section>

      <!-- 右栏：患者记录/收容转归/评分汇总/处置建议/拍摄弹窗 -->
      <section class="right-column">
        <!-- 患者记录卡片-拍摄/录像入口 -->
        <div class="patient-records-card">
          <div class="records-header">
            <h4>患者记录</h4>
            <button class="btn-record" @click="openCameraModal">拍摄 / 录像</button>
          </div>
          <p class="records-hint">点击“拍摄 / 录像”在弹窗中完成拍照、录像与媒体查看</p>
        </div>

        <!-- 收容转归单选开关 -->
        <div class="admission-outcome-switch">
          <label class="switch-label">收容转归：</label>
          <div class="switch-container">
            <input type="radio" id="admission" v-model="admissionOutcome" value="收容" />
            <label for="admission" class="switch-option">诊疗收容</label>
            <input type="radio" id="discharge" v-model="admissionOutcome" value="转归" />
            <label for="discharge" class="switch-option">转归后送</label>
          </div>
        </div>

        <!-- 核心操作按钮 -->
        <div class="action-buttons">
          <button class="btn save-btn" @click="saveAssessment">保存评估</button>
        </div>

        <!-- 评分汇总卡片-实时计算各类评分+严重度 -->
        <div class="score-summary-card compact v2">
          <div class="summary-grid">
            <div class="chip">
              <span class="k">GCS</span>
              <span class="v">{{ glasgowTotal }}</span><span class="u">/15</span>
              <span class="b" :class="gcsSeverity.color">{{ gcsSeverity.label }}</span>
            </div>
            <div class="chip">
              <span class="k">START</span>
              <span class="b" :class="startBadge.color">{{ startBadge.label }}</span>
            </div>
            <div class="chip">
              <span class="k">PHI</span>
              <span class="v">{{ phiTotal }}</span>
              <span class="b" :class="phiSeverity.color">{{ phiSeverity.label }}</span>
            </div>
            <div class="chip">
              <span class="k">CRAMS</span>
              <span class="v">{{ cramsTotal }}</span><span class="u">/12</span>
              <span class="b" :class="cramsSeverity.color">{{ cramsSeverity.label }}</span>
            </div>
          </div>
        </div>

        <!-- 处置建议面板-有建议内容时展示+语音播报功能 -->
        <div class="advice-panel-card" v-if="advicePanel.lines && advicePanel.lines.length">
          <div class="advice-panel-header">
            <h4>处置建议</h4>
            <div class="advice-actions">
              <button 
                class="voice-btn" 
                @click="playAdviceVoice"
                :class="{ playing: isVoicePlaying }"
                title="语音播报"
              >
                <span>{{ isVoicePlaying ? '暂停' : '播报' }}</span>
              </button>
            </div>
          </div>
          <div class="advice-tags">
            <span v-if="advicePanel.part" class="tag">{{ advicePanel.part }}</span>
            <span v-if="advicePanel.injury" class="tag">{{ advicePanel.injury }}</span>
          </div>
          <ol class="advice-list-compact">
            <li v-for="(line, idx) in advicePanel.lines" :key="idx">{{ line }}</li>
          </ol>
        </div>

        <!-- 拍摄/录像弹窗 - Teleport挂载到body防止滚动裁切 -->
        <Teleport to="body">
          <div v-if="showCameraModal" class="modal-overlay" @click.self="closeCameraModal">
            <div class="modal-content camera-modal">
              <div class="modal-header">
                <h3 class="modal-title">拍摄 / 录像</h3>
                <button class="modal-close" @click="closeCameraModal">×</button>
              </div>
              <div class="modal-body">
                <div class="camera-host">
                  <CameraModule
                    @photo-captured="handlePhotoCaptured"
                    @video-recorded="handleVideoRecorded"
                    @media-saved="handleMediaSaved"
                    @media-viewed="handleMediaViewed"
                  />
                </div>
              </div>
              <div class="modal-footer">
                <button class="modal-confirm" @click="closeCameraModal">完成</button>
              </div>
            </div>
          </div>
        </Teleport>
      </section>
    </main>
  </div>
</template>

<script setup>
// 引入Vue3核心API
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
// 引入业务子组件
import HumanBodyModel from './HumanBodyModel.vue'
import CameraModule from './CameraModule.vue'
import VitalSigns from './VitalSigns.vue'
import ScoreAssessment from './ScoreAssessment.vue'
// 引入接口请求
import assessmentApi from '../api/assessments.js'

// ===================== 全局状态定义 =====================
// 语音播报相关状态
const isVoicePlaying = ref(false)  // 语音播报播放状态
let speechSynthesisInstance = null // 语音合成实例对象

// 父组件传入的路由跳转方法
const props = defineProps({
  navigateTo: Function
})

// ===================== 评分相关数据 =====================
// 格拉斯哥昏迷评分(GCS) - 睁眼/语言/运动
const glasgowScore = ref({
  eyeOpening: '4',
  verbalResponse: '5',
  motorResponse: '6'
})
// 院前指数评分(PHI) - 收缩压/脉搏/呼吸/意识
const phiScore = ref({
  systolicPressure: '',
  pulse: '',
  breathing: '',
  consciousness: ''
})
// CRAMS评分 - 循环/呼吸/腹部/运动/言语 (此处只绑定了呼吸/胸部/运动)
const cramsScore = ref({ breath: '0', chest: '0', sport: '0' })
// START分诊评分 - 存储颜色标识 red/yellow/green/black
const startScore = ref('')

// ===================== 生命体征数据 =====================
const vitalData = ref({
  heart_rate: 0,               // 心率
  blood_pressure: { systolic: 0, diastolic: 0 }, // 血压(收缩压/舒张压)
  respiratory_rate: 0,         // 呼吸频率
  oxygen_saturation: 0,        // 血氧饱和度
  temperature: 0.0,            // 体温
  timestamp: new Date().toISOString() // 体征采集时间戳
})

// ===================== 伤情相关数据 =====================
const injuredParts = ref([])    // 受伤部位数组
// 处置建议面板数据 - 联动人体模型组件返回的建议内容
const advicePanel = ref({
  part: '',           // 受伤部位(中文)
  injury: '',         // 细分伤情名称
  lines: []           // 处置建议内容数组
})

// ===================== 患者基础信息 =====================
const patientData = ref({
  id: '',       // 患者ID
  name: '',     // 患者姓名
  gender: '',   // 患者性别
  age: '',      // 患者年龄
  bloodType: '' // 患者血型
})
// 血型下拉选项列表
const bloodTypes = ['未知', 'A型', 'B型', 'AB型', 'O型']

// ===================== 监听事件 =====================
// 监听患者年龄/性别变化 - 实时存储到本地缓存
watch([() => patientData.value.age, () => patientData.value.gender], ([newAge, newGender], [oldAge, oldGender]) => {
  if (newAge !== oldAge) {
    localStorage.setItem('age', JSON.stringify(patientData.value.age));
  }
  if (newGender !== oldGender) {
    localStorage.setItem('gender', JSON.stringify(patientData.value.gender));
  }
})

// ===================== 伤情数据 =====================
// 受伤部位选中状态 - 绑定人体模型组件
const injuryData = ref({
  leftArm: false, rightArm: false, leftLeg: false, rightLeg: false,
  headInjury: false, chest: false, abdomen: false
})
// 伤情类型 - 创伤/非创伤
const injuryType = ref('')

// ===================== 媒体相关数据 =====================
const capturedPhoto = ref('')    // 拍摄的照片base64
const capturedVideos = ref([])   // 录制的视频列表
const savedMediaList = ref([])   // 保存的媒体文件列表

// ===================== 治疗选项(未使用，保留兼容) =====================
const treatment = ref({
  firstAid: { cpr: false, bleeding: false, splinting: false, oxygenTherapy: false },
  medication: { painRelief: false, antibiotics: false, anticoagulant: false, sedative: false },
  transfer: ''
})

// ===================== 业务状态 =====================
const admissionOutcome = ref('收容') // 收容转归默认值：诊疗收容
const isFullscreen = ref(false)      // 全屏状态
let previousFullscreen = false       // 上一次全屏状态
let userRequestedExit = false        // 是否用户主动退出全屏

// ===================== 计算方法 - 各类评分总分计算 =====================
/**
 * 计算GCS格拉斯哥评分总分
 */
const calculateGlasgowTotal = () => {
  const eye = parseInt(glasgowScore.value.eyeOpening) || 0
  const verbal = parseInt(glasgowScore.value.verbalResponse) || 0
  const motor = parseInt(glasgowScore.value.motorResponse) || 0
  return eye + verbal + motor
}
/**
 * 计算PHI院前指数总分
 */
const calculatePHITotal = () => {
  const systolic = parseInt(phiScore.value.systolicPressure) || 0
  const pulse = parseInt(phiScore.value.pulse) || 0
  const breathing = parseInt(phiScore.value.breathing) || 0
  const consciousness = parseInt(phiScore.value.consciousness) || 0
  return systolic + pulse + breathing + consciousness
}
/**
 * 计算CRAMS评分总分
 */
const calculateCramsTotal = () => {
  const breath = parseInt(cramsScore.value.breath) || 0
  const chest = parseInt(cramsScore.value.chest) || 0
  const sport = parseInt(cramsScore.value.sport) || 0
  return breath + chest + sport
}

// ===================== 事件处理方法 - 子组件回调 =====================
/**
 * 切换受伤部位选中状态(兼容旧逻辑)
 * @param {String} part 受伤部位字段名
 */
const toggleInjury = (part) => {
  injuryData.value[part] = !injuryData.value[part]
}

/**
 * 监听伤情类型变化 - 创伤/非创伤
 * @param {String} type trauma=创伤 non-trauma=非创伤
 */
const handleInjuryTypeChange = (type) => {
  injuryType.value = type === 'trauma' ? '创伤' : '非创伤'
}

/**
 * 监听受伤部位变化 - 核心联动方法
 * @param {Object} data 人体模型组件返回的伤情数据
 */
const handleInjuredPartsChange = (data) => {
  // 更新受伤部位数组和选中状态
  injuredParts.value = data.parts
  injuryData.value = {
    headInjury: data.parts.includes('head'),
    leftArm: data.parts.includes('leftUpperArm') || data.parts.includes('leftForearm') || data.parts.includes('leftHand'),
    rightArm: data.parts.includes('rightUpperArm') || data.parts.includes('rightForearm') || data.parts.includes('rightHand'),
    leftLeg: data.parts.includes('leftThigh') || data.parts.includes('leftCalf') || data.parts.includes('leftFoot'),
    rightLeg: data.parts.includes('rightThigh') || data.parts.includes('rightCalf') || data.parts.includes('rightFoot'),
    chest: data.parts.includes('chest'),
    abdomen: data.parts.includes('abdomen')
  }
  // 更新处置建议面板数据 - 过滤空内容，保证整洁
  advicePanel.value = {
    part: data.selectedPartName || '',
    injury: data.selectedInjuryName || '',
    lines: Array.isArray(data.advice) ? data.advice.filter(item => item.trim()) : (data.advice ? [data.advice.trim()] : [])
  }
  // 切换伤情时自动停止当前语音播报
  if (isVoicePlaying.value) stopAdviceVoice()
}

/**
 * 监听伤情严重度变化
 * @param {String} severity 严重度等级
 */
const handleSeverityChange = (severity) => {
  console.log('严重程度变化:', severity)
}

/**
 * 监听生命体征数据更新
 * @param {Object} vitalDataUpdate 体征更新数据
 */
const handleVitalDataChange = (vitalDataUpdate) => {
  vitalData.value = { ...vitalData.value, ...vitalDataUpdate }
}

/**
 * 监听各类评分数据更新
 * @param {Object} scoreData 评分更新数据 {type:评分类型, data:评分值}
 */
const handleScoreChange = (scoreData) => {
  if (scoreData.type === 'glasgow') glasgowScore.value = scoreData.data
  else if (scoreData.type === 'phi') phiScore.value = scoreData.data
  else if (scoreData.type === 'start') startScore.value = scoreData.data
  else if (scoreData.type === 'crams') cramsScore.value = scoreData.data
}

// ===================== 摄像头模块事件处理 =====================
/**
 * 照片拍摄完成回调
 * @param {Object} photoData 照片数据
 */
const handlePhotoCaptured = (photoData) => {
  capturedPhoto.value = photoData.data
}
/**
 * 视频录制完成回调
 * @param {Object} videoData 视频数据
 */
const handleVideoRecorded = (videoData) => {
  capturedVideos.value.push(videoData)
}
/**
 * 媒体文件保存完成回调
 * @param {Object} mediaData 媒体数据
 */
const handleMediaSaved = (mediaData) => {
  savedMediaList.value.push(mediaData)
}
/**
 * 媒体文件查看回调
 * @param {Object} mediaData 媒体数据
 */
const handleMediaViewed = (mediaData) => {
  console.log('查看媒体:', mediaData)
}

// ===================== 核心业务方法 - 保存评估数据 =====================
/**
 * 保存评估数据到后端数据库 - 核心提交方法
 */
const saveAssessment = async () => {
  // 基础校验：患者ID不能为空
  if (!patientData.value.id.trim()) {
    alert('请输入患者ID')
    return
  }

  // 数据格式化：性别转数字 1=男 2=女 0=未知
  const sex = patientData.value.gender === '男' ? 1 : patientData.value.gender === '女' ? 2 : 0
  const blood = patientData.value.bloodType || null
  // 计算各类评分总分
  const glasgow = calculateGlasgowTotal()
  const phi = calculatePHITotal()
  const crams = calculateCramsTotal()
  const start_color = startScore.value || null
  // 刷新体征时间戳
  const nowIso = new Date().toISOString()
  vitalData.value.timestamp = nowIso
  // 收容转归转数字 1=收容 2=转归
  const suggestion = admissionOutcome.value === '收容' ? 1 : 2

  // 构造提交给后端的参数体 - 拍平结构适配数据库字段
  const payload = {
    uid: patientData.value.id,
    name: patientData.value.name || '',
    sex,
    age: patientData.value.age ? Number(patientData.value.age) : null,
    blood,
    // 受伤信息布尔值
    is_trauma_injury: injuryType.value === '创伤',
    head_injury: !!injuryData.value.headInjury,
    left_arm: !!injuryData.value.leftArm,
    right_arm: !!injuryData.value.rightArm,
    left_leg: !!injuryData.value.leftLeg,
    right_leg: !!injuryData.value.rightLeg,
    chest: !!injuryData.value.chest,
    abdomen: !!injuryData.value.abdomen,
    // 各类评分总分
    glasgow, phi, start_color, crams,
    // GCS评分细分字段
    gcs_eye_opening: parseInt(glasgowScore.value.eyeOpening),
    gcs_verbal_response: parseInt(glasgowScore.value.verbalResponse),
    gcs_motor_response: parseInt(glasgowScore.value.motorResponse),
    // PHI评分细分字段
    phi_systolic_pressure: parseInt(phiScore.value.systolicPressure),
    phi_pulse: parseInt(phiScore.value.pulse),
    phi_breathing: parseInt(phiScore.value.breathing),
    phi_consciousness: parseInt(phiScore.value.consciousness),
    // CRAMS评分细分字段
    crams_breath: parseInt(cramsScore.value.breath),
    crams_chest: parseInt(cramsScore.value.chest),
    crams_sport: parseInt(cramsScore.value.sport),
    // 生命体征数据
    heart_rate: vitalData.value.heart_rate ?? null,
    systolic_pressure: vitalData.value.blood_pressure?.systolic ?? null,
    diastolic_pressure: vitalData.value.blood_pressure?.diastolic ?? null,
    respiratory_rate: vitalData.value.respiratory_rate ?? null,
    oxygen_saturation: vitalData.value.oxygen_saturation ?? null,
    temperature: vitalData.value.temperature ?? null,
    vital_timestamp: nowIso,
    // 收容转归建议
    suggestion
  }

  // 调用后端接口提交数据
  const submitAssessment = async (payload) => {
    try {
      const resp = await assessmentApi.createAssessment(payload);
      if (resp.code == 0) {
        alert(`评估数据已写入数据库`);
      } else {
        throw new Error(resp.data?.message || '未知错误');
      }
    } catch (error) {
      console.error('保存失败:', error);
      alert('写入数据库失败，请检查后端服务、数据库或网络。');
    }
  }
  await submitAssessment(payload);
}

// ===================== 患者信息操作方法 =====================
/**
 * 生成随机患者ID + 重置表单 + 本地存储ID
 */
const generatePatientId = () => {
  const timestamp = Date.now().toString().slice(-6)
  const randomNum = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `P${timestamp}${randomNum}`
}

/**
 * 新增患者 - 生成ID+刷新页面+存储ID
 */
const addNewPatient = () => {
  patientData.value.id = generatePatientId()
  localStorage.setItem('lastPatientId', patientData.value.id);
  window.location.reload();
  alert(`患者信息已保存！\n患者ID: ${patientData.value.id}\n姓名: ${patientData.value.name}`)
}

/**
 * 取消表单操作 - 清空表单+清除本地存储
 */
const cancelForm = () => {
  if (confirm('确定要取消当前操作并清空表单吗？')) {
    window.location.reload();
    localStorage.removeItem('lastPatientId');
  }
}

/**
 * 重置所有表单数据
 */
const resetForm = () => {
  if (confirm('确定要重置所有数据吗？')) {
    patientData.value = { id: '', name: '', gender: '', age: '', bloodType: '' }
    injuryData.value = { leftArm: false, rightArm: false, leftLeg: false, rightLeg: false, headInjury: false, chest: false, abdomen: false }
    injuryType.value = ''
    capturedPhoto.value = ''
    capturedVideos.value = []
    savedMediaList.value = []
    treatment.value = {
      firstAid: { cpr: false, bleeding: false, splinting: false, oxygenTherapy: false },
      medication: { painRelief: false, antibiotics: false, anticoagulant: false, sedative: false },
      transfer: ''
    }
  }
}

// ===================== 全屏功能相关 =====================
/**
 * 切换全屏/退出全屏
 */
const toggleFullscreen = () => {
  if (!document.fullscreenElement) {
    userRequestedExit = false
    document.documentElement.requestFullscreen().catch(err => {
      console.log('Error attempting to enable full-screen mode:', err)
      isFullscreen.value = false
    })
  } else {
    userRequestedExit = true
    document.exitFullscreen().catch(err => {
      console.log('Error attempting to exit full-screen mode:', err)
      isFullscreen.value = false
    })
  }
}

/**
 * 监听全屏状态变化
 */
const handleFullscreenChange = () => {
  const currentFullscreen = !!document.fullscreenElement
  isFullscreen.value = currentFullscreen

  // 非用户主动退出全屏时，自动重新进入（防止弹窗导致的全屏丢失）
  if (!currentFullscreen && previousFullscreen && !userRequestedExit) {
    setTimeout(() => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
          console.log('Failed to re-enter fullscreen after modal or other event:', err)
        })
      }
    }, 100)
  }
  if (currentFullscreen) userRequestedExit = false
  previousFullscreen = currentFullscreen
}

/**
 * 全屏切换失败回调
 * @param {Error} err 错误信息
 */
const handleFullscreenError = (err) => {
  console.log('Fullscreen error:', err)
  isFullscreen.value = false
  previousFullscreen = false
  userRequestedExit = false
}

// ===================== 弹窗相关方法 =====================
const showCameraModal = ref(false)  // 拍摄弹窗显示状态
const openCameraModal = () => { showCameraModal.value = true }  // 打开拍摄弹窗
const closeCameraModal = () => { showCameraModal.value = false } // 关闭拍摄弹窗

// ===================== 计算属性 - 实时评分+严重度 =====================
// GCS总分
const glasgowTotal = computed(() => calculateGlasgowTotal())
// PHI总分
const phiTotal = computed(() => calculatePHITotal())
// CRAMS总分
const cramsTotal = computed(() => calculateCramsTotal())
// GCS评分严重度 - 轻度(13+)、中度(9-12)、重度(<9)
const gcsSeverity = computed(() => {
  const t = glasgowTotal.value
  if (t >= 13) return { label: '轻度', color: 'green' }
  if (t >= 9) return { label: '中度', color: 'yellow' }
  return { label: '重度', color: 'red' }
})
// PHI评分严重度 - 轻度(≤3)、中度(4-8)、重度(≥9)
const phiSeverity = computed(() => {
  const t = phiTotal.value
  if (t <= 3) return { label: '轻度', color: 'green' }
  if (t <= 8) return { label: '中度', color: 'yellow' }
  return { label: '重度', color: 'red' }
})
// CRAMS评分严重度 - 轻伤(12)、中度伤(10-11)、重伤(6-9)、危重伤(<6)
const cramsSeverity = computed(() => {
  const t = cramsTotal.value
  if (t === 12) return { label: '轻伤', color: 'green' }
  if (t >= 10 && t <= 11) return { label: '中度伤', color: 'yellow' }
  if (t >= 6) return { label: '重伤', color: 'red' }
  return { label: '危重伤', color: 'red' }
})
// START分诊标签转换
const startBadge = computed(() => {
  const map = {
    red: { label: '红色 - 紧急', color: 'red' },
    yellow: { label: '黄色 - 紧迫', color: 'yellow' },
    green: { label: '绿色 - 延缓', color: 'green' },
    black: { label: '黑色 - 生命体征消失', color: 'black' }
  }
  return map[startScore.value] || { label: '未评估', color: 'gray' }
})

// ===================== 语音播报核心方法 =====================
/**
 * 播放处置建议语音播报
 */
const playAdviceVoice = () => {
  if (isVoicePlaying.value) { stopAdviceVoice(); return }
  if (!advicePanel.value.lines || advicePanel.value.lines.length === 0) {
    alert('暂无处置建议可播报'); return
  }
  // 拼接播报文本
  const voiceText = `当前${advicePanel.value.part}${advicePanel.value.injury}的处置建议：${advicePanel.value.lines.join('；')}`
  // 浏览器语音合成兼容判断
  if ('speechSynthesis' in window) {
    speechSynthesisInstance = window.speechSynthesis
    speechSynthesisInstance.cancel()
    // 创建语音实例并配置
    const utterance = new SpeechSynthesisUtterance(voiceText)
    utterance.lang = 'zh-CN' // 中文播报
    utterance.volume = 1     // 音量
    utterance.rate = 1       // 语速
    utterance.pitch = 1      // 音调
    // 播报结束回调
    utterance.onend = () => {
      isVoicePlaying.value = false
      speechSynthesisInstance = null
    }
    // 播报错误回调
    utterance.onerror = (e) => {
      console.error('语音播报错误:', e)
      isVoicePlaying.value = false
      speechSynthesisInstance = null
    }
    // 开始播报
    speechSynthesisInstance.speak(utterance)
    isVoicePlaying.value = true
  } else {
    alert('您的浏览器不支持语音合成功能')
  }
}

/**
 * 停止语音播报
 */
const stopAdviceVoice = () => {
  if (speechSynthesisInstance && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
  isVoicePlaying.value = false
  speechSynthesisInstance = null
}

// ===================== 生命周期钩子 =====================
onMounted(() => {
  // 页面加载时从本地缓存恢复患者ID
  const lastPatientId = localStorage.getItem('lastPatientId');
  if (lastPatientId) patientData.value.id = lastPatientId;
  // 绑定全屏事件监听
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  document.addEventListener('fullscreenerror', handleFullscreenError)
})

onUnmounted(() => {
  // 组件销毁时清理资源
  stopAdviceVoice() // 停止语音播报
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  document.removeEventListener('fullscreenerror', handleFullscreenError)
})
</script>

<style scoped>
.injury-assessment-system {
  height: 100vh;
  background:
    radial-gradient(circle at 20% 50%, rgba(79, 195, 247, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(41, 182, 246, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 40% 80%, rgba(30, 60, 114, 0.2) 0%, transparent 50%),
    linear-gradient(135deg, #0d1b2a 0%, #1e3c72 35%, #2a5298 100%);
  color: white;
  font-family: 'Microsoft YaHei', Arial, sans-serif;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.injury-assessment-system::before {
  content: '';
  position: absolute;
	top: -50%;
	left: -50%;
	width: 200%;
	height: 200%;
  background:
    radial-gradient(circle at 25% 25%, rgba(79, 195, 247, 0.03) 0%, transparent 25%),
    radial-gradient(circle at 75% 75%, rgba(41, 182, 246, 0.03) 0%, transparent 25%);
  animation: backgroundMove 20s ease-in-out infinite alternate;
  z-index: 0;
}

@keyframes backgroundMove {
  0% { transform: rotate(0deg) scale(1); }
  100% { transform: rotate(1deg) scale(1.02); }
}

/* 顶部标题栏 */
.header {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.95) 0%, rgba(30, 60, 114, 0.9) 100%);
  backdrop-filter: blur(20px);
  padding: 1.5rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid rgba(79, 195, 247, 0.2);
	box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  position: relative;
  z-index: 10;
}

.header-title h1 {
  font-size: 1.8rem;
  font-weight: 700;
  background: linear-gradient(135deg, #4fc3f7 0%, #81d4fa 50%, #b3e5fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: 0 0 30px rgba(79, 195, 247, 0.3);
  letter-spacing: 1px;
}

.header-controls { display: flex; gap: 1rem; }

.control-btn {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.1) 0%, rgba(41, 182, 246, 0.2) 100%);
  border: 1px solid rgba(79, 195, 247, 0.4);
  color: #4fc3f7;
  padding: 0.8rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(10px);
	box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.control-btn::before {
  content: '';
  position: absolute;
	top: 0;
	left: -100%;
	width: 100%;
	height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.6s;
}

.control-btn:hover {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.4) 100%);
  transform: translateY(-2px);
	box-shadow: 0 8px 25px rgba(79, 195, 247, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
}

.control-btn:hover::before { left: 100%; }

/* 主要内容区域 */
.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.0rem;
  padding: 1.0rem;
  position: relative;
  z-index: 5;
  min-height: 0;
  overflow: hidden;
}

/* 顶部头部不占用弹性空间，避免挤压中部 */
.patient-info-header { flex: 0 0 auto; }

/* 左侧患者信息区域 */
.patient-info-section { flex: 2; display: flex; flex-direction: column; gap: 1rem; }

.patient-form {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.8) 0%, rgba(30, 60, 114, 0.6) 100%);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 16px;
  padding: 1.5rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 0 0 1px rgba(79, 195, 247, 0.1);
  position: relative;
  overflow: hidden;
}

.patient-form::before {
  content: '';
  position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 2px;
  background: linear-gradient(90deg, transparent, #4fc3f7, transparent);
  opacity: 0.8;
}

.form-row {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr auto auto 1fr auto;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.form-row.single-row {
  grid-template-columns: auto minmax(120px, 1fr) auto minmax(120px, 1fr) auto minmax(80px, auto) auto minmax(120px, auto) auto;
  align-items: center;
  gap: 1rem;
}

.form-row.blood-type-row {
  grid-template-columns: auto 2fr auto;
  align-items: center;
  gap: 1.5rem;
}

.form-row label { color: #b3e5fc; font-size: 0.9rem; white-space: nowrap; }

.input-field {
  width: 150px;
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.05) 0%, rgba(41, 182, 246, 0.1) 100%);
  border: 1px solid rgba(79, 195, 247, 0.3);
  color: white;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  font-size: 0.9rem;
  backdrop-filter: blur(10px);
	box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2), 0 1px 0 rgba(255, 255, 255, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.input-field:focus {
  border-color: #4fc3f7;
	box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2), 0 0 0 3px rgba(79, 195, 247, 0.2), 0 4px 12px rgba(79, 195, 247, 0.15);
}

.input-field.small { width: 80px; }
.input-field.expanded { min-width: 220px; }

.radio-group { display: flex; gap: 1rem; }
.radio-group.inline { display: flex; gap: 0.8rem; white-space: nowrap; }
.radio-group label { display: flex; align-items: center; gap: 0.3rem; cursor: pointer; }

.blood-type-group { display: flex; gap: 0.8rem; flex-wrap: wrap; }
.blood-type-group.inline { display: flex; gap: 0.6rem; white-space: nowrap; flex-wrap: nowrap; }
.blood-type-group.expanded { display: flex; gap: 1rem; justify-content: space-evenly; flex-wrap: nowrap; }
.blood-type-group label { display: flex; align-items: center; gap: 0.3rem; cursor: pointer; font-size: 0.8rem; }

/* 新增单行患者信息样式 */
.patient-form-single-line {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.8) 0%, rgba(30, 60, 114, 0.6) 100%);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 12px;
  padding: 1rem 1.5rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 0 0 1px rgba(79, 195, 247, 0.1);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
}

.patient-form-single-line::before {
  content: '';
  position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 2px;
  background: linear-gradient(90deg, transparent, #4fc3f7, transparent);
  opacity: 0.8;
}

.patient-basic-info {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex: 1;
  flex-wrap: wrap;
}

.info-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
  flex: 1;
  min-width: 120px;
}

.info-group label { color: #b3e5fc; font-size: 0.85rem; font-weight: 500; min-width: max-content; }

.input-field.compact {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.05) 0%, rgba(41, 182, 246, 0.1) 100%);
  border: 1px solid rgba(79, 195, 247, 0.3);
  color: white;
  padding: 0.5rem 0.8rem;
  border-radius: 6px;
  font-size: 0.85rem;
  backdrop-filter: blur(10px);
	box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2), 0 1px 0 rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  width: 120px;
  min-width: 80px;
}

.input-field.compact:focus {
  border-color: #4fc3f7;
	box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2), 0 0 0 2px rgba(79, 195, 247, 0.3), 0 2px 8px rgba(79, 195, 247, 0.15);
}

.input-field.compact::placeholder { color: rgba(255, 255, 255, 0.5); font-size: 0.8rem; }

.radio-group.compact { display: flex; gap: 0.8rem; }

.radio-label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.8rem;
  transition: color 0.3s ease;
}

.radio-label:hover { color: #4fc3f7; }
.radio-label input[type="radio"] { accent-color: #4fc3f7; transform: scale(0.9); }

.blood-type-group.compact { display: flex; gap: 0.6rem; }

.blood-type-label {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
	color: rgba(255, 255, 255, 0.9);
  font-size: 0.75rem;
  transition: color 0.3s ease;
}

.blood-type-label:hover { color: #4fc3f7; }
.blood-type-label input[type="radio"] { accent-color: #4fc3f7; transform: scale(0.85); }

.action-buttons-group { display: flex; gap: 0.8rem; align-items: center; }

.btn-primary, .btn-secondary, .btn-tertiary, .btn-cancel {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.btn-primary {
  background: linear-gradient(135deg, #66bb6a 0%, #4caf50 50%, #388e3c 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.btn-primary:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(76, 175, 80, 0.5);
  background: linear-gradient(135deg, #7cc77f 0%, #5cbf60 50%, #43a047 100%);
}

.btn-secondary {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 50%, #0288d1 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(79, 195, 247, 0.4);
}

.btn-secondary:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(79, 195, 247, 0.5);
  background: linear-gradient(135deg, #6bcef5 0%, #42c3f9 50%, #1976d2 100%);
}

.btn-tertiary {
  background: linear-gradient(135deg, #ff8a65 0%, #ff7043 50%, #f4511e 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(255, 138, 101, 0.4);
}

.btn-tertiary:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(255, 138, 101, 0.5);
  background: linear-gradient(135deg, #ffab91 0%, #ff8a65 50%, #ff5722 100%);
}

.btn-cancel {
  background: linear-gradient(135deg, #e57373 0%, #f44336 50%, #d32f2f 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(244, 67, 54, 0.4);
}

.btn-cancel:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(244, 67, 54, 0.5);
  background: linear-gradient(135deg, #ef5350 0%, #e53935 50%, #c62828 100%);
}

.btn-manage {
  background: linear-gradient(135deg, #9c27b0 0%, #7b1fa2 50%, #6a1b9a 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(156, 39, 176, 0.4);
}

.btn-manage:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(156, 39, 176, 0.5);
  background: linear-gradient(135deg, #ba68c8 0%, #9c27b0 50%, #8e24aa 100%);
}

.btn-statistics {
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 50%, #e65100 100%);
  color: white;
	box-shadow: 0 4px 12px rgba(255, 152, 0, 0.4);
}

.btn-statistics:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 16px rgba(255, 152, 0, 0.5);
  background: linear-gradient(135deg, #ffb74d 0%, #ff9800 50%, #f57c00 100%);
}

.btn-add, .btn-take {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 50%, #0288d1 100%);
  border: none;
  color: white;
  padding: 0.7rem 1.5rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
	font-size: 0.9rem;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
	box-shadow: 0 4px 15px rgba(79, 195, 247, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;
}

.btn-add::before, .btn-take::before {
  content: '';
  position: absolute;
	top: 0;
	left: -100%;
	width: 100%;
	height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  transition: left 0.6s;
}

.btn-add:hover, .btn-take:hover {
  transform: translateY(-3px) scale(1.02);
	box-shadow: 0 8px 25px rgba(79, 195, 247, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  background: linear-gradient(135deg, #5ac6f7 0%, #39c6f6 50%, #1e88e5 100%);
}

.btn-add:hover::before, .btn-take:hover::before { left: 100%; }
.btn-add:active, .btn-take:active { transform: translateY(-1px) scale(1); }

/* 人体图形 */
.body-diagram {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.8) 0%, rgba(30, 60, 114, 0.6) 100%);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  gap: 2rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 0 0 1px rgba(79, 195, 247, 0.1);
  position: relative;
  overflow: hidden;
}

.body-diagram::before {
  content: '';
  position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 2px;
  background: linear-gradient(90deg, transparent, #4fc3f7, transparent);
  opacity: 0.8;
}

.body-silhouette {
  flex: 1;
  display: flex;
  justify-content: center;
  background: radial-gradient(circle at center, rgba(79, 195, 247, 0.05) 0%, transparent 60%);
  border-radius: 12px;
  padding: 1rem;
	box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2);
}

.body-svg { width: 150px; height: 300px; }

.body-svg rect, .body-svg path {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
	filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}

.body-svg rect:hover {
  fill: #64b5f6;
	filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3)) drop-shadow(0 0 8px rgba(100, 181, 246, 0.6));
  transform: scale(1.05);
}

.body-svg rect.injured {
  fill: #f44336 !important;
	filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3)) drop-shadow(0 0 12px rgba(244, 67, 54, 0.8)) drop-shadow(0 0 24px rgba(244, 67, 54, 0.4));
  animation: injuryPulse 2s ease-in-out infinite;
}

@keyframes injuryPulse {
  0%, 100% { filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3)) drop-shadow(0 0 12px rgba(244, 67, 54, 0.8)) drop-shadow(0 0 24px rgba(244, 67, 54, 0.4)); }
  50% { filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3)) drop-shadow(0 0 16px rgba(244, 67, 54, 1)) drop-shadow(0 0 32px rgba(244, 67, 54, 0.6)); }
}

.injury-checkboxes { flex: 2; display: flex; flex-direction: column; gap: 1rem; }

.injury-section h4 {
  color: #4fc3f7;
  margin-bottom: 0.8rem;
	font-size: 1rem;
	font-weight: 600;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  position: relative;
}

.injury-section h4::after {
  content: '';
  position: absolute;
	bottom: -4px;
	left: 0;
	width: 30px;
	height: 2px;
  background: linear-gradient(90deg, #4fc3f7, transparent);
  border-radius: 1px;
}

.injury-section label { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; cursor: pointer; }

/* 三栏布局 规律、良好的习惯*/
.left-column, .center-column, .right-column {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  min-height: 0;
  overflow-y: auto;
  max-height: 100%;
  -webkit-overflow-scrolling: touch;
}

/* 防止列的直系子卡片继续把列撑开 */
.left-column>*, .center-column>*, .right-column>* { min-height: 0; }

.left-column::-webkit-scrollbar, .center-column::-webkit-scrollbar, .right-column::-webkit-scrollbar { width: 6px; }
.left-column::-webkit-scrollbar-track, .center-column::-webkit-scrollbar-track, .right-column::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.1); border-radius: 3px; }
.left-column::-webkit-scrollbar-thumb, .center-column::-webkit-scrollbar-thumb, .right-column::-webkit-scrollbar-thumb { background: rgba(79, 195, 247, 0.3); border-radius: 3px; }
.left-column::-webkit-scrollbar-thumb:hover, .center-column::-webkit-scrollbar-thumb:hover, .right-column::-webkit-scrollbar-thumb:hover { background: rgba(79, 195, 247, 0.5); }

/* 收容转归开关样式 */
.admission-outcome-switch {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  border-left: 3px solid #4fc3f7;
}

.switch-label {
  display: block;
	font-size: 0.9rem;
	font-weight: 600;
  margin-bottom: 0.8rem;
  color: #81d4fa;
}

.switch-container { display: flex; gap: 0.5rem; }
.switch-container input[type="radio"] { display: none; }

.switch-option {
  flex: 1;
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
	font-size: 0.9rem;
}

.switch-container input[type="radio"]:checked+.switch-option {
  background: #4fc3f7;
  color: #000;
  border-color: #4fc3f7;
}

.switch-option:hover { background: rgba(79, 195, 247, 0.2); }

/* 照片区域 */
.photo-area { min-height: 200px; display: flex; align-items: center; justify-content: center; }
.camera-placeholder { text-align: center; color: #81d4fa; }
.camera-icon { font-size: 2rem; margin-bottom: 0.5rem; }

.capture-btn, .retake-btn {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: none;
  padding: 0.8rem 1.5rem;
  border-radius: 8px;
  color: white;
	font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.capture-btn:hover, .retake-btn:hover {
  transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(79, 195, 247, 0.3);
}

.photo-preview { text-align: center; }
.photo-preview img { max-width: 100%; border-radius: 8px; margin-bottom: 1rem; }

/* 操作按钮 */
.action-buttons { display: flex; flex-direction: column; gap: 0.8rem; }

.btn {
  padding: 0.8rem 1rem;
  border: none;
  border-radius: 8px;
	font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
	font-size: 0.9rem;
}

.save-btn { background: linear-gradient(135deg, #2196f3 0%, #42a5f5 100%); color: white; }
.print-btn { background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%); color: white; }
.reset-btn { background: linear-gradient(135deg, #f44336 0%, #ef5350 100%); color: white; }
.btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3); }

.assessment-card {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.85) 0%, rgba(30, 60, 114, 0.7) 100%);
  backdrop-filter: blur(25px);
  border: 1px solid rgba(79, 195, 247, 0.4);
  border-radius: 16px;
  padding: 1.5rem;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 0 0 1px rgba(79, 195, 247, 0.2);
  position: relative;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.assessment-card::before {
  content: '';
  position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
  background: linear-gradient(90deg, #4fc3f7 0%, #29b6f6 50%, #0288d1 100%);
  opacity: 0.9;
}

.assessment-card:hover {
  transform: translateY(-2px);
	box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 0 0 1px rgba(79, 195, 247, 0.3), 0 0 20px rgba(79, 195, 247, 0.1);
}

.assessment-card h3 {
  color: #4fc3f7;
  margin-bottom: 1.2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
	font-size: 1.1rem;
	font-weight: 600;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
  position: relative;
  padding-bottom: 8px;
}

.assessment-card h3::after {
  content: '';
  position: absolute;
	bottom: 0;
	left: 0;
	width: 50px;
	height: 2px;
  background: linear-gradient(90deg, #4fc3f7, #29b6f6, transparent);
  border-radius: 1px;
}

.info-icon {
  background: #4fc3f7;
  color: white;
  border-radius: 50%;
  width: 20px;
	height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
	font-size: 0.8rem;
}

.score-input { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem; }

.score-field {
  background: rgba(79, 195, 247, 0.1);
  border: 1px solid #4fc3f7;
  color: #4fc3f7;
  padding: 0.5rem;
  border-radius: 4px;
  text-align: center;
	font-size: 1.2rem;
	font-weight: 600;
  width: 60px;
}

.score-field.large { width: 80px; font-size: 1.5rem; }

.calc-btn {
  background: #4fc3f7;
  border: none;
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
	font-weight: 600;
}

.glasgow-details { display: grid; grid-template-columns: 1fr auto; gap: 0.5rem; align-items: center; }

.glasgow-section label {
  display: flex;
  align-items: center;
  gap: 0.3rem;
	font-size: 0.8rem;
  margin-bottom: 0.2rem;
  cursor: pointer;
}

.score-badge {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 50%, #0288d1 100%);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 12px;
	font-weight: 700;
  text-align: center;
  margin-left: 0.5rem;
	box-shadow: 0 4px 15px rgba(79, 195, 247, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
  position: relative;
  overflow: hidden;
}

.score-badge::before {
  content: '';
  position: absolute;
	top: 50%;
	left: 50%;
	width: 0;
	height: 0;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, transparent 70%);
  transition: all 0.6s ease;
  transform: translate(-50%, -50%);
  border-radius: 50%;
}

.score-badge:hover::before { width: 200px; height: 200px; }
.score-badge.large { font-size: 1.5rem; padding: 0.5rem 1rem; }

.diagnosis-options label { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; cursor: pointer; font-size: 0.9rem; }
.chest-assessment { display: flex; align-items: center; gap: 1rem; }
.chest-assessment label { display: flex; align-items: center; gap: 0.3rem; cursor: pointer; }
.treatment-options label { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; cursor: pointer; }

.total-score {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.3) 100%);
  border: 2px solid #4fc3f7;
	box-shadow: 0 0 30px rgba(79, 195, 247, 0.3), inset 0 0 20px rgba(79, 195, 247, 0.1);
  animation: totalScoreGlow 3s ease-in-out infinite alternate;
}

@keyframes totalScoreGlow {
  0% { box-shadow: 0 0 30px rgba(79, 195, 247, 0.3), inset 0 0 20px rgba(79, 195, 247, 0.1); }
  100% { box-shadow: 0 0 40px rgba(79, 195, 247, 0.5), inset 0 0 30px rgba(79, 195, 247, 0.2); }
}

.save-btn {
  background: linear-gradient(135deg, #42a5f5 0%, #2196f3 50%, #1976d2 100%);
  border: none;
  color: white;
  border-radius: 16px;
  cursor: pointer;
	font-size: 1.2rem;
	font-weight: 700;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
	box-shadow: 0 8px 25px rgba(33, 150, 243, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
}

.save-btn::before {
  content: '';
  position: absolute;
	top: 0;
	left: -100%;
	width: 100%;
	height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
  transition: left 0.8s;
}

.save-btn:hover {
  transform: translateY(-3px) scale(1.02);
	box-shadow: 0 12px 35px rgba(33, 150, 243, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.4);
  background: linear-gradient(135deg, #64b5f6 0%, #42a5f5 50%, #1e88e5 100%);
}

.save-btn:hover::before { left: 100%; }
.save-btn:active { transform: translateY(-1px) scale(1); }

/* 脉冲效果 */
.pulse-effect { position: relative; }

.pulse-effect::after {
  content: '';
  position: absolute;
	top: 50%;
	left: 50%;
	width: 100%;
	height: 100%;
  border: 2px solid rgba(79, 195, 247, 0.6);
  border-radius: inherit;
  transform: translate(-50%, -50%);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  100% { transform: translate(-50%, -50%) scale(1.1); opacity: 0; }
}

/* 响应式设计 */
@media (max-width: 1400px) {
  .main-content { grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
  .form-row.single-row { grid-template-columns: auto 1fr auto 1fr auto auto auto auto; gap: 0.8rem; }
  .form-row.blood-type-row { grid-template-columns: auto 2fr auto; gap: 1rem; }
  .blood-type-group.inline { gap: 0.4rem; }
  .blood-type-group.expanded { gap: 0.8rem; }
  .blood-type-group.inline label, .blood-type-group.expanded label { font-size: 0.7rem; }
}

@media (max-width: 1200px) {
  .main-content { grid-template-columns: 1fr 1fr; gap: 1rem; }
  .right-column { grid-column: 1 / -1; }
  .injury-content { flex-direction: column; }
  .vital-grid { grid-template-columns: repeat(2, 1fr); }
  .form-row.single-row { grid-template-columns: 1fr; gap: 0.8rem; }
  .form-row.single-row>* { justify-self: start; }
}

@media (max-width: 768px) {
  .main-content { grid-template-columns: 1fr; gap: 1rem; }
  .left-column, .center-column, .right-column { grid-column: 1; }
  .tab-headers { flex-wrap: wrap; }
  .tab-button { min-width: 80px; font-size: 0.75rem; }
  .vital-grid { grid-template-columns: 1fr; }
  .form-row { grid-template-columns: 1fr; gap: 0.5rem; }
  .form-row.single-row { grid-template-columns: 1fr; gap: 0.5rem; }
  
  .patient-form-single-line { flex-direction: column; gap: 1rem; padding: 1rem; }
  .patient-basic-info { flex-direction: column; gap: 1rem; width: 100%; }
  .info-group { flex-direction: column; align-items: flex-start; gap: 0.3rem; width: 100%; }
  .info-group label { font-size: 0.8rem; }
  .input-field.compact { width: 100%; min-width: unset; }
  .input-field.compact.small { width: 100%; }
  .radio-group.compact, .blood-type-group.compact { flex-wrap: wrap; width: 100%; }
  .action-buttons-group { width: 100%; justify-content: space-between; }
  .btn-primary, .btn-secondary, .btn-tertiary, .btn-cancel { flex: 1; padding: 0.8rem 0.5rem; font-size: 0.8rem; }
  .radio-group.inline, .blood-type-group.inline { flex-wrap: wrap; }
  .action-buttons { flex-direction: row; gap: 0.5rem; }
  .btn { font-size: 0.8rem; padding: 0.6rem 0.8rem; }
}

/* 自定义患者信息字段间距 */
.patient-basic-info .info-group:nth-child(1) { margin-right: 2rem; }
.patient-basic-info .info-group:nth-child(3) { margin-right: 0.5rem; }

/* 新加代码 */
.vital-signs-scroll-container {
  height: 300px;
  overflow-y: auto;
  overflow-x: hidden;
  border-radius: 16px;
  border: 1px solid rgba(79, 195, 247, 0.3);
  background: rgba(13, 27, 42, 0.6);
  backdrop-filter: blur(10px);
  margin: 0 auto;
}

/* 可选：美化滚动条（仅 WebKit 浏览器） */
.vital-signs-scroll-container::-webkit-scrollbar { width: 6px; }
.vital-signs-scroll-container::-webkit-scrollbar-thumb { background: rgba(79, 195, 247, 0.5); border-radius: 6px; }
.vital-signs-scroll-container::-webkit-scrollbar-thumb:hover { background: rgba(79, 195, 247, 0.8); }

/* —— 患者记录卡片（取代常驻摄像头）—— */
.patient-records-card {
  background: rgba(13,27,42,.55);
  border: 1px solid rgba(79,195,247,.28);
  border-radius: 12px;
  padding: .75rem .9rem;
}
.records-header { display: flex; align-items: center; justify-content: space-between; gap: .75rem; }
.records-header h4 { margin: 0; color: #4fc3f7; font-size: 1rem; font-weight: 600; }
.btn-record {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: none; color: #fff; font-weight: 700;
  padding: .5rem .9rem; border-radius: 10px; cursor: pointer;
  transition: transform .2s ease, box-shadow .2s ease;
}
.btn-record:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79,195,247,.35); }
.records-hint { margin: .45rem 0 0; color: #b3e5fc; opacity: .85; font-size: .82rem; }

/* —— 评分汇总 v2（两列徽章式，超紧凑）—— */
.score-summary-card.compact.v2 {
  margin-top: .6rem;
  padding: .65rem .7rem;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(13,27,42,.85) 0%, rgba(30,60,114,.7) 100%);
  border: 1px solid rgba(79,195,247,.4);
}
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .45rem; }
@media (max-width: 1280px) { .summary-grid { grid-template-columns: 1fr; } }
.chip {
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-auto-rows: minmax(24px, auto);
  align-items: center;
  gap: .35rem .45rem;
  background: rgba(0,0,0,.16);
  border-left: 3px solid #4fc3f7;
  border-radius: 10px;
  padding: .42rem .5rem;
}
.chip .k { color: #b3e5fc; font-weight: 600; font-size: .86rem; }
.chip .v { color: #fff; font-weight: 800; letter-spacing: .2px; }
.chip .u { color: #b3e5fc; opacity: .85; font-size: .78rem; }
.chip .b {
  justify-self: end;
  padding: .18rem .5rem; border-radius: 999px; font-weight: 700; font-size: .72rem;
  border: 1px solid rgba(255,255,255,.18);
}
.chip .b.green  { background: linear-gradient(135deg, #66bb6a, #4caf50); color:#fff; }
.chip .b.yellow { background: linear-gradient(135deg, #ffeb3b, #fbc02d); color:#1a1a1a; }
.chip .b.red    { background: linear-gradient(135deg, #ef5350, #e53935); color:#fff; }
.chip .b.black  { background: linear-gradient(135deg, #90a4ae, #607d8b); color:#e3f2fd; }
.chip .b.gray   { background: linear-gradient(135deg, #90caf9, #64b5f6); color:#0f172a; }

/* —— 拍摄/录像 弹窗 —— */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.modal-content.camera-modal {
  width: min(920px, 92vw);
  max-height: 88vh; display: flex; flex-direction: column;
  background: linear-gradient(135deg, rgba(13,27,42,.95) 0%, rgba(30,60,114,.92) 100%);
  border: 1px solid rgba(79,195,247,.5);
  border-radius: 14px; overflow: hidden;
  box-shadow: 0 10px 40px rgba(0,0,0,.45);
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: .8rem 1rem; border-bottom: 1px solid rgba(79,195,247,.28);
}
.modal-title { color: #4fc3f7; font-size: 1.05rem; font-weight: 700; margin: 0; }
.modal-close {
  background: none; border: none; color: #b3e5fc; font-size: 1.5rem; cursor: pointer;
  width: 32px; height: 32px; border-radius: 50%;
}
.modal-close:hover { background: rgba(79,195,247,.18); color: #4fc3f7; }
.modal-body { padding: .8rem 1rem; overflow: auto; }
.camera-host {
  /* 让 CameraModule 在弹窗中更宽敞，内部高度由子组件自适应 */
  min-height: 300px;
}
.modal-footer {
  padding: .75rem 1rem; border-top: 1px solid rgba(79,195,247,.28);
  display: flex; justify-content: flex-end; gap: .5rem;
}
.modal-confirm {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: 1px solid rgba(79,195,247,.6);
  color: #fff; padding: .5rem 1rem; border-radius: 8px; font-weight: 700; cursor: pointer;
}

/* 如需限制子组件内部视频高度，可使用以下选择器（通常弹窗不必限制） */
/*
:deep(video), :deep(canvas) { max-height: 360px; }
*/
/* —— 处置建议面板 —— */
.advice-panel-card{
  margin-top: .6rem;
  padding: .7rem .85rem;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(13,27,42,.85) 0%, rgba(30,60,114,.72) 100%);
  border: 1px solid rgba(79,195,247,.38);
}
.advice-panel-header{
  display:flex; align-items:center; justify-content:space-between; gap:.75rem; margin-bottom:.4rem;
}
.advice-panel-header h4{
  margin:0; color:#4fc3f7; font-size:1rem; font-weight:600;
}
.advice-tags{ display:flex; gap:.4rem; flex-wrap:wrap; }
.advice-tags .tag{
  background: rgba(79,195,247,.18);
  color:#b3e5fc; border:1px solid rgba(79,195,247,.35);
  padding:.15rem .5rem; border-radius:999px; font-size:.78rem; white-space:nowrap;
}
.advice-list-compact{
  margin:.2rem 0 0 1.2rem; padding:0; color:#eaf6ff;
}
.advice-list-compact li{
  margin:.18rem 0; line-height:1.35; font-size:.9rem;
}
/* ========== 处置建议面板新增样式（语音按钮） ========== */
.advice-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.4rem;
}

.advice-actions {
  display: flex;
  gap: 0.5rem;
}

.voice-btn {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: none;
  color: white;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.voice-btn:hover {
  background: linear-gradient(135deg, #64b5f6 0%, #42a5f5 100%);
  transform: translateY(-1px);
}

.voice-btn.playing {
  background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
}

/* 处置建议面板样式 */
.advice-panel-card{
  margin-top: .6rem;
  padding: .7rem .85rem;
  border-radius: 10px;
  background: linear-gradient(135deg, rgba(13,27,42,.85) 0%, rgba(30,60,114,.72) 100%);
  border: 1px solid rgba(79,195,247,.38);
}

.advice-tags{ display:flex; gap:.4rem; flex-wrap:wrap; margin-bottom: 0.3rem; }
.advice-tags .tag{
  background: rgba(79,195,247,.18);
  color:#b3e5fc; border:1px solid rgba(79,195,247,.35);
  padding:.15rem .5rem; border-radius:999px; font-size:.78rem; white-space:nowrap;
}

.advice-list-compact{
  margin:.2rem 0 0 1.2rem; padding:0; color:#eaf6ff;
}

.advice-list-compact li{
  margin:.18rem 0; line-height:1.35; font-size:.9rem;
}

</style>