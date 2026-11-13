<template>
  <!-- 体征测量核心组件：蓝牙连接+体征数据展示+异常提醒+紧急建议 -->
  <div class="vital-signs">
    <!-- 头部区域：标题 + 蓝牙连接/血压测量控制区 -->
    <div class="vital-header">
      <h4>体征测量</h4>
      <div class="bluetooth-controls">
        <!-- 蓝牙连接状态指示灯：连接中(橙)、已连接(绿) -->
        <div class="bluetooth-status">
          <div 
            class="status-indicator"
            :class="{ connected: bluetoothStatus.includes('Connected'), connecting: isConnecting }"
          >
            <div class="status-dot"></div>
          </div>
        </div>
        <!-- 功能按钮区 -->
        <div class="control-buttons">
          <button class="btn-bluetooth" @click="connectDevice" :disabled="isConnecting">
            <i class="icon-bluetooth"></i>
            {{ isConnecting ? '连接中...' : '搜索设备' }}
          </button>
          <button class="btn-nibp" @click="startNIBP" :disabled="!bluetoothStatus.includes('Connected')">
            <i class="icon-blood-pressure"></i>
            血压测量
          </button>
        </div>
      </div>
    </div>

    <!-- 体征数据网格展示区：心率、血氧、呼吸率、血压、体温 -->
    <div class="vital-grid">
      <div class="vital-item">
        <label>心率 <span class="unit">bpm</span></label>
        <div class="vital-value" :class="{ abnormal: isAbnormal.hr(+vitalSigns.heartRate || null) }">
          {{ vitalSigns.heartRate }}
        </div>
      </div>
      <div class="vital-item">
        <label>血氧 <span class="unit">%</span></label>
        <div class="vital-value" :class="{ abnormal: isAbnormal.spo2(+vitalSigns.oxygenSaturation || null) }">
          {{ vitalSigns.oxygenSaturation }}
        </div>
      </div>
      <div class="vital-item">
        <label>呼吸率 <span class="unit">bpm</span></label>
        <div class="vital-value" :class="{ abnormal: isAbnormal.rr(+vitalSigns.respiratoryRate || null) }">
          {{ vitalSigns.respiratoryRate }}
        </div>
      </div>
      <div class="vital-item">
        <label>收缩压 <span class="unit">mmHg</span></label>
        <div class="vital-value" :class="{ abnormal: isAbnormal.sbp(+vitalSigns.systolicPressure || null) }">
          {{ vitalSigns.systolicPressure }}
        </div>
      </div>
      <div class="vital-item">
        <label>舒张压 <span class="unit">mmHg</span></label>
        <div class="vital-value">{{ vitalSigns.diastolicPressure }}</div>
      </div>
      <div class="vital-item">
        <label>体温 <span class="unit">°C</span></label>
        <div class="vital-value" :class="{ abnormal: isAbnormal.temp(+vitalSigns.temperature || null) }">
          {{ vitalSigns.temperature }}
        </div>
      </div>
    </div>

    <!-- 紧急处置建议模块：有异常时展示，无数据不显示 -->
    <div v-if="emergencyAdvice.length" class="emergency-advice">
      <h5>⚠️ 紧急处置建议</h5>
      <ul>
        <li v-for="(item, idx) in emergencyAdvice" :key="idx">{{ item }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
// 引入Vue3核心API
import { ref, watch,onMounted,onUnmounted} from 'vue'
// 引入蓝牙设备监测组合式函数（核心蓝牙通信逻辑）
import { useBluetoothMonitor } from '../composables/useBluetoothMonitor.js'
import axios from 'axios'
/**
 * 定义组件向外暴露的事件
 * 1. vital-data-change：体征数据发生变化时触发，传递格式化后的体征数据
 * 2. vital-emergency-advice：紧急建议更新时触发，传递建议列表
 */
const emit = defineEmits(['vital-data-change', 'vital-emergency-advice'])

/**
 * 解构蓝牙监测组合式函数的属性和方法
 * 蓝牙状态/连接状态/体征原始数据/连接设备/开始血压测量 核心方法
 */
const {
  bluetoothStatus,
  isConnecting,
  vitalParams,
  connectDevice,
  startNIBP
} = useBluetoothMonitor()

/**
 * 页面展示用的体征数据对象
 * 初始化默认值为 '--' 占位符，提升页面美观度
 */
const vitalSigns = ref({
  heartRate: '--',           // 心率
  oxygenSaturation: '--',    // 血氧饱和度
  respiratoryRate: '--',     // 呼吸率
  systolicPressure: '--',    // 收缩压
  diastolicPressure: '--',   // 舒张压
  temperature: '--'          // 体温
})
// 1s向后端获取数据，并更新
// 配置
const BACKEND_URL = '/api/get_vitals'
const POLL_INTERVAL_MS = 5000 // 5秒一次

let pollTimer = null

const sendPostRequest = async () => {
  try {
    console.log('[📡 POST 请求] 正在获取后端体征数据...')

    const response = await fetch(BACKEND_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({}) // 发送空对象，确保 Content-Length 存在
    })

    if (!response.ok) {
      throw new Error(`HTTP  $ {response.status}:  $ {response.statusText}`)
    }

    const data = await response.json()
    vitalSigns.value['heartRate'] = data.data.heartRate
    vitalSigns.value['oxygenSaturation'] = data.data.oxygenSaturation
    vitalSigns.value['respiratoryRate'] = data.data.respiratoryRate
    vitalSigns.value['systolicPressure'] = data.data.systolicPressure
    vitalSigns.value['diastolicPressure'] = data.data.diastolicPressure
    vitalSigns.value['temperature'] = data.data.temperature
    console.log('[✅ 后端返回体征数据]', data.data)
    localStorage.setItem('sharedData', JSON.stringify(vitalSigns.value));

    // 👉 如果未来想用此数据更新 UI，可在这里 emit 或赋值
    // 例如：emit('backend-vital-update', data)

  } catch (error) {
    console.error('[❌ POST 请求失败]', error.message || error)
  }
}

// 启动定时任务
onMounted(() => {
  sendPostRequest() // 立即执行一次
  pollTimer = setInterval(sendPostRequest, POLL_INTERVAL_MS)
})

// 清理定时器
onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
    console.log('[⏹️ 定时 POST 请求] 已停止')
  }
})




// 紧急处置建议列表，有异常时自动生成对应建议文本
const emergencyAdvice = ref([])

/**
 * 工具函数：安全转换数值
 * @param {any} v 待转换的值
 * @returns {Number|null} 有效数字返回数字，无效返回null
 */
const toNum = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : null
}

/**
 * 体征数据正常值阈值常量（成人通用标准，可根据业务需求微调）
 * 超出该范围判定为数据异常，会高亮展示+生成处置建议
 */
const THRESHOLDS = {
  HR: { low: 50, high: 120 },        // 心率阈值
  SpO2: { low: 90 },                 // 血氧阈值（仅下限）
  RR: { low: 10, high: 30 },         // 呼吸率阈值
  SBP: { low: 90, high: 180 },       // 收缩压阈值
  TEMP: { low: 35, high: 38.5, veryHigh: 40 } // 体温分级阈值
}

/**
 * 异常状态判定方法集合
 * 给每个体征字段提供独立的判定函数，返回布尔值控制页面高亮样式
 * @returns {Boolean} true=数据异常，false=数据正常/无数据
 */
const isAbnormal = {
  hr: (v) => v != null && (v < THRESHOLDS.HR.low || v > THRESHOLDS.HR.high),
  spo2: (v) => v != null && v < THRESHOLDS.SpO2.low,
  rr: (v) => v != null && (v < THRESHOLDS.RR.low || v > THRESHOLDS.RR.high),
  sbp: (v) => v != null && (v < THRESHOLDS.SBP.low || v > THRESHOLDS.SBP.high),
  temp: (v) => v != null && (v < THRESHOLDS.TEMP.low || v >= THRESHOLDS.TEMP.high)
}

/**
 * 核心方法：根据体征数据生成对应的紧急处置建议
 * 按照心率/血压/血氧/呼吸率/体温 依次判定，组合多维度风险提示
 * @param {Object} p 蓝牙返回的原始体征参数
 * @returns {Array} 处置建议文本数组
 */
const buildAdvice = (p) => {
  const list = []
  // 转换原始数据为有效数字，方便判定
  const hr = toNum(p.heartRate)
  const spo2 = toNum(p.spo2)
  const rr = toNum(p.respRate)
  const sbp = toNum((p.nibp || '').split('/')[0])
  const temp = toNum(p.temperature)

  // 心率异常建议
  if (hr != null && hr < THRESHOLDS.HR.low) list.push('心率过慢：立即心电监测，准备阿托品；评估高危可致房室传导阻滞病因。')
  if (hr != null && hr > THRESHOLDS.HR.high) list.push('心率过快：心电监护，评估心律类型；必要时抗心律失常药物或电复律。')

  // 血压异常建议
  if (sbp != null && sbp < THRESHOLDS.SBP.low) list.push('低血压：快速补液（晶体液），必要时去甲肾上腺素等升压支持。')
  if (sbp != null && sbp > THRESHOLDS.SBP.high) list.push('高血压：监测神经系统症状，静脉降压药物（缓降血压）。')

  // 血氧异常建议
  if (spo2 != null && spo2 < THRESHOLDS.SpO2.low) list.push('血氧不足：立即吸氧；评估气道，必要时气管插管/呼吸机支持。')

  // 呼吸率异常建议
  if (rr != null && rr < THRESHOLDS.RR.low) list.push('呼吸过慢：评估意识与通气，准备气道管理及通气支持。')
  if (rr != null && rr > THRESHOLDS.RR.high) list.push('呼吸过快：考虑低氧/代谢性酸中毒，尽快做动脉血气分析。')

  // 体温分级异常建议（低体温/高热/超高热）
  if (temp != null) {
    if (temp < THRESHOLDS.TEMP.low) {
      list.push('低体温（<35°C）：立即保暖，使用加温毯，输注加温液体，监测心律。')
    } else if (temp >= THRESHOLDS.TEMP.high && temp < THRESHOLDS.TEMP.veryHigh) {
      list.push('高热（≥38.5°C）：物理降温（冰袋、温水擦浴），可给予退热药（如对乙酰氨基酚），查找感染源。')
    } else if (temp >= THRESHOLDS.TEMP.veryHigh) {
      list.push('超高热（≥40°C）：紧急降温（冰盐水灌胃/灌肠、降温毯），防惊厥，排查中暑或中枢性高热。')
    }
  }

  // 组合风险判定：低血压+心动过速 → 疑似失血性休克
  if (sbp != null && hr != null && sbp < 90 && hr > 110) {
    list.push('可能失血性休克：建立两条静脉通路，快速补液/备血，搜寻出血来源。')
  }

  return list
}

/**
 * 深度监听蓝牙原始体征参数变化
 * 核心逻辑：原始数据变更 → 更新展示数据 → 生成紧急建议 → 向外派发格式化数据
 */
watch(vitalParams, (newParams) => {
  // 更新页面展示的体征数据
  vitalSigns.value.heartRate = newParams.pulseRate || '--'
  vitalSigns.value.oxygenSaturation = newParams.spo2 || '--'
  vitalSigns.value.respiratoryRate = newParams.respRate || '--'
  const nibpParts = (newParams.nibp || '--/--').split('/')
  vitalSigns.value.systolicPressure = nibpParts[0] || '--'
  vitalSigns.value.diastolicPressure = nibpParts[1] || '--'
  vitalSigns.value.temperature = newParams.temperature || '--'

  // 重新生成紧急处置建议
  emergencyAdvice.value = buildAdvice(newParams)

  // 向外派发格式化后的体征数据，供父组件使用
  emit('vital-data-change', {
    heart_rate: parseInt(newParams.heartRate) || 0,
    blood_pressure: {
      systolic: parseInt(nibpParts[0]) || 0,
      diastolic: parseInt(nibpParts[1]) || 0
    },
    respiratory_rate: parseInt(newParams.respRate) || 0,
    oxygen_saturation: parseInt(newParams.spo2) || 0,
    temperature: parseFloat(newParams.temperature) || 0.0,
    timestamp: new Date().toISOString()
  })
}, { deep: true })

/**
 * 组件初始化默认值处理
 * 页面加载完成后，主动派发一次初始空数据，生成初始空建议，保证数据一致性
 */
const initialParams = {
  heartRate: '--',
  spo2: '--',
  respRate: '--',
  nibp: '--/--',
  temperature: '--'
}
emit('vital-data-change', {
  heart_rate: 0,
  blood_pressure: { systolic: 0, diastolic: 0 },
  respiratory_rate: 0,
  oxygen_saturation: 0,
  temperature: 0.0,
  timestamp: new Date().toISOString()
})
emergencyAdvice.value = buildAdvice(initialParams)
</script>

<style scoped>
/* 组件外层容器：渐变背景+毛玻璃效果+边框美化 */
.vital-signs {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.8) 0%, rgba(30, 60, 114, 0.6) 100%);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 16px;
  padding: 1.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 0 0 1px rgba(79, 195, 247, 0.1);
  position: relative;
  overflow: hidden;
}

/* 顶部渐变装饰线 */
.vital-signs::before {
  content: '';
  position: absolute;
  top: 0;
	left: 0;
	right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #4fc3f7, transparent);
  opacity: 0.8;
}

/* 头部标题样式 */
.vital-signs h4 {
  color: #4fc3f7;
  margin-bottom: 1.2rem;
  font-size: 1.15rem;
  font-weight: 600;
  text-shadow: 0 0 10px rgba(79, 195, 247, 0.5);
  position: relative;
}

/* 标题下方下划线 */
.vital-signs h4::after {
  content: '';
  position: absolute;
  bottom: -6px;
	left: 0;
  width: 40px;
	height: 2px;
  background: linear-gradient(90deg, #4fc3f7, #29b6f6);
  border-radius: 1px;
}

/* 标题+蓝牙控制区 布局 */
.vital-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

/* 体征数据网格布局：3列均分 */
.vital-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

/* 单个体征项样式 */
.vital-item {
  text-align: center;
}
.vital-item label {
  font-size: 0.8rem;
  color: #b3e5fc;
  display: block;
}
/* 单位文本样式 */
.unit {
  color: #4fc3f7;
}

/* 体征数值展示框样式 */
.vital-value {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.15) 0%, rgba(41, 182, 246, 0.25) 100%);
  color: #4fc3f7;
  padding: 0.8rem;
  border-radius: 12px;
  font-size: 1.3rem;
  font-weight: 700;
  backdrop-filter: blur(10px);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2), 0 2px 4px rgba(79, 195, 247, 0.2), 0 0 0 1px rgba(79, 195, 247, 0.3);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(79, 195, 247, 0.3);
  transition: all 0.3s ease;
}
/* 数值框悬浮高亮 */
.vital-value:hover {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.3) 100%);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2), 0 4px 8px rgba(79, 195, 247, 0.3), 0 0 0 1px rgba(79, 195, 247, 0.4);
}

/* 异常数值高亮样式：红色边框+红色文字 */
.vital-value.abnormal {
  border-color: #f44336;
  color: #ff8a80;
  box-shadow: inset 0 2px 8px rgba(244, 67, 54, 0.25), 0 2px 6px rgba(244, 67, 54, 0.25), 0 0 0 1px rgba(244, 67, 54, 0.35);
}

/* 紧急处置建议模块样式 */
.emergency-advice {
  margin-top: 1rem;
  background: rgba(244, 67, 54, 0.08);
  border: 1px solid rgba(244, 67, 54, 0.6);
  border-radius: 12px;
  padding: 0.9rem 1rem;
  color: #ffcdd2;
}
.emergency-advice h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: #ff8a80;
}
.emergency-advice ul {
  margin: 0;
  padding-left: 1.1rem;
}
.emergency-advice li {
  margin: 0.25rem 0;
  line-height: 1.4;
}

/* 蓝牙控制区布局 */
.bluetooth-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0;
  border-top: none;
  margin-top: 0;
}
.bluetooth-status {
  display: flex;
  align-items: center;
  margin-bottom: 0;
}

/* 蓝牙状态指示灯：圆形指示灯 */
.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  position: relative;
}
/* 已连接-绿色 */
.status-indicator.connected {
  background-color: #4caf50;
}
/* 连接中-橙色 */
.status-indicator.connecting {
  background-color: #ff9800;
}
/* 指示灯呼吸动画 */
.status-dot {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  position: absolute;
  top: 50%;
	left: 50%;
  transform: translate(-50%, -50%);
  animation: pulse 2s infinite;
}
/* 呼吸动画关键帧 */
@keyframes pulse {
  0% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.2); }
  100% { transform: translate(-50%, -50%) scale(1); }
}

/* 功能按钮布局 */
.control-buttons {
  display: flex;
  gap: 0.5rem;
}

/* 蓝牙/血压测量按钮统一样式 */
.btn-bluetooth, .btn-nibp {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.15) 0%, rgba(41, 182, 246, 0.25) 100%);
  color: #4fc3f7;
  padding: 0.6rem 1.2rem;
  border-radius: 8px;
  font-size: 0.9rem;
	font-weight: 500;
  backdrop-filter: blur(10px);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2), 0 2px 4px rgba(79, 195, 247, 0.2), 0 0 0 1px rgba(79, 195, 247, 0.3);
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 按钮悬浮高亮 */
.btn-bluetooth:hover, .btn-nibp:hover {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.3) 100%);
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.2), 0 4px 8px rgba(79, 195, 247, 0.3), 0 0 0 1px rgba(79, 195, 247, 0.4);
}

/* 按钮内部图标样式 */
.icon-bluetooth, .icon-blood-pressure {
  font-size: 1.2rem;
  margin-right: 0.4rem;
}
</style>