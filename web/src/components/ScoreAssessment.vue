<template>
  <!-- 急救检伤评分总容器 -->
  <div class="score-assessment">
    <!-- 评分标签页切换区 -->
    <div class="scoring-tabs">
      <div class="tab-headers">
        <button 
          v-for="tab in scoringTabs" 
          :key="tab.id" 
          :class="['tab-button', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 标签页内容区 -->
      <div class="tab-content">
        <!-- 格拉斯哥昏迷量表(GCS) -->
        <div v-if="activeTab === 'glasgow'" class="scoring-content">
          <h4>Glasgow 昏迷量表 (GCS)</h4>
          <div class="glasgow-scoring">
            <!-- 睁眼反应评分项 -->
            <div class="score-section">
              <div class="section-header">
                <h5>睁眼反应 (E)</h5>
                <button class="info-btn" @click="openModal('eye')">
                  <span class="icon">ⓘ</span>
                </button>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="glasgowScore.eyeOpening" value="4" />自主睁眼</label>
                <label><input type="radio" v-model="glasgowScore.eyeOpening" value="3" />呼唤睁眼</label>
                <label><input type="radio" v-model="glasgowScore.eyeOpening" value="2" />疼痛睁眼</label>
                <label><input type="radio" v-model="glasgowScore.eyeOpening" value="1" />不能睁眼</label>
              </div>
            </div>

            <!-- 语言反应评分项 -->
            <div class="score-section">
              <div class="section-header">
                <h5>语言反应 (V)</h5>
                <button class="info-btn" @click="openModal('verbal')">
                  <span class="icon">ⓘ</span>
                </button>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="glasgowScore.verbalResponse" value="5" />对答切题</label>
                <label><input type="radio" v-model="glasgowScore.verbalResponse" value="4" />对答错乱</label>
                <label><input type="radio" v-model="glasgowScore.verbalResponse" value="3" />单词应答</label>
                <label><input type="radio" v-model="glasgowScore.verbalResponse" value="2" />呻吟声</label>
                <label><input type="radio" v-model="glasgowScore.verbalResponse" value="1" />无语言反应</label>
              </div>
            </div>

            <!-- 运动反应评分项 -->
            <div class="score-section">
              <div class="section-header">
                <h5>运动反应 (M)</h5>
                <button class="info-btn" @click="openModal('motor')">
                  <span class="icon">ⓘ</span>
                </button>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="6" />听从指令</label>
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="5" />定位疼痛</label>
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="4" />屈曲回避</label>
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="3" />异常屈曲</label>
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="2" />异常伸展</label>
                <label><input type="radio" v-model="glasgowScore.motorResponse" value="1" />无运动反应</label>
              </div>
            </div>

            <!-- GCS总分展示 -->
            <div class="total-score">
              总分：{{ calculateGlasgowTotal() }} / 15
            </div>
            <!-- GCS评分结果判定 -->
            <div v-if="finalResult_gla" class="result-detail" style="margin-top: 2rem;">
              <div :class="['result-badge', finalResult_gla.color]">
                <h4 :class="['severity-text', finalResult_gla.color]" style="color: antiquewhite;">
                  {{ finalResult_gla.severity }}
                </h4>
                <div class="priority-level" style="color: aliceblue">
                  优先级: {{ finalResult_gla.priority }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- PHI生理评分系统 -->
        <div v-if="activeTab === 'phi'" class="scoring-content">
          <h4>PHI 生理评分系统</h4>
          <div class="phi-scoring">
            <div class="phi-item">
              <label>收缩压 (mmHg)</label>
              <select v-model="phiScore.systolicPressure">
                <option value="0">&gt; 100</option>
                <option value="1">86 ~ 100</option>
                <option value="2">75 ~ 85</option>
                <option value="3">0 ~ 74</option>
              </select>
            </div>

            <div class="phi-item">
              <label>脉搏 (次/分)</label>
              <select v-model="phiScore.pulse">
                <option value="0">51 ~ 119</option>
                <option value="3">&ge; 120</option>
                <option value="5">&le; 50</option>
              </select>
            </div>

            <div class="phi-item">
              <div class="section-header">
                <label>呼吸状态</label>
                <button class="info-btn" @click="openModal2('PHIBreath')">
                  <span class="icon">ⓘ</span>
                </button>
              </div>
              <select v-model="phiScore.breathing">
                <option value="0">正常</option>
                <option value="3">费力或浅</option>
                <option value="5">&lt; 10次/分或需插管</option>
              </select>
            </div>

            <div class="phi-item">
              <div class="section-header">
                <label>意识状态</label>
                <button class="info-btn" @click="openModal2('PHIConscious')">
                  <span class="icon">ⓘ</span>
                </button>
              </div>
              <select v-model="phiScore.consciousness">
                <option value="0">正常</option>
                <option value="3">模糊或烦躁</option>
                <option value="5">言语不能理解</option>
              </select>
            </div>

            <!-- PHI总分及分项展示 -->
            <div class="total-score">
              <div class="score-breakdown">
                <div class="score-item">收缩压: {{ phiScore.systolicPressure }}分</div>
                <div class="score-item">脉搏: {{ phiScore.pulse }}分</div>
                <div class="score-item">呼吸: {{ phiScore.breathing }}分</div>
                <div class="score-item">意识: {{ phiScore.consciousness }}分</div>
              </div>
              <div class="total-line">总分：{{ calculatePHITotal() }} 分</div>
              <div class="severity-interpretation">
                <span v-if="calculatePHITotal() <= 3" class="severity mild">轻度</span>
                <span v-else-if="calculatePHITotal() <= 8" class="severity moderate">中度</span>
                <span v-else class="severity severe">重度</span>
              </div>
            </div>
          </div>
        </div>

        <!-- START检伤分级系统 -->
        <div v-if="activeTab === 'start'" class="scoring-content start-scoring">
          <div class="section-header">
            <h4>START 分级系统 - 交互式评估</h4>
            <button class="info-btn" @click="openModal2('Start')">
              <span class="icon">ⓘ</span>
            </button>
          </div>
          <!-- 流程重置按钮 -->
          <div class="flow-controls">
            <button class="reset-flow-btn" @click="resetStartFlow">重新开始评估</button>
          </div>

          <!-- START评估流程问题区 -->
          <div class="start-flow">
            <div v-if="startFlow.currentStep === 'canWalk'" class="flow-question active">
              <h5>伤员能否行走？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('canWalk', 'yes')">能</button>
                <button class="flow-btn no" @click="handleStartChoice('canWalk', 'no')">否</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'hasBreathing'" class="flow-question active">
              <h5>呼吸有无？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('hasBreathing', 'yes')">是</button>
                <button class="flow-btn no" @click="handleStartChoice('hasBreathing', 'no')">否</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'respiratoryRate'" class="flow-question active">
              <h5>呼吸速率>30次？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('respiratoryRate', 'yes')">是</button>
                <button class="flow-btn no" @click="handleStartChoice('respiratoryRate', 'no')">否</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'breathingAfterAirway'" class="flow-question active">
              <h5>重新打开呼吸道后，呼吸有无？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('breathingAfterAirway', 'yes')">有</button>
                <button class="flow-btn no" @click="handleStartChoice('breathingAfterAirway', 'no')">无</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'radialPulse'" class="flow-question active">
              <h5>桡动脉是否有搏动？或 毛细血管充盈时间是否&lt;2秒？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('radialPulse', 'yes')">是</button>
                <button class="flow-btn no" @click="handleStartChoice('radialPulse', 'no')">否</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'controlBleeding'" class="flow-question active">
              <h5>控制出血后情况如何？</h5>
              <div class="flow-options">
                <button class="flow-btn" @click="handleStartChoice('controlBleeding', 'controlled')">已控制</button>
              </div>
            </div>

            <div v-if="startFlow.currentStep === 'consciousness'" class="flow-question active">
              <h5>意识清楚是否能沟通？</h5>
              <div class="flow-options">
                <button class="flow-btn yes" @click="handleStartChoice('consciousness', 'yes')">是</button>
                <button class="flow-btn no" @click="handleStartChoice('consciousness', 'no')">否</button>
              </div>
            </div>

            <!-- 评估路径记录 -->
            <div v-if="startFlow.path.length > 0" class="assessment-path">
              <h5>评估路径：</h5>
              <div class="path-steps">
                <span v-for="(step, index) in startFlow.path" :key="index" class="path-step">
                  {{ step.question }}: <strong>{{ step.answer }}</strong>
                  <span v-if="index < startFlow.path.length - 1" class="arrow">→</span>
                </span>
              </div>
            </div>

            <!-- START评估最终结果 -->
            <div v-if="startFlow.finalResult" class="final-result">
              <div :class="['result-badge', startFlow.finalResult.color]">
                <h4>{{ startFlow.finalResult.label }}</h4>
                <p>{{ startFlow.finalResult.description }}</p>
                <div class="priority-level">
                  优先级: {{ startFlow.finalResult.priority }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- CRAMS简易创伤计分法 -->
        <div v-if="activeTab === 'crams'" class="scoring-content">
          <h4>简易创伤计分法</h4>
          <div class="crams-scoring">         
            <div class="score-section">
              <div class="section-header">
                <h5>呼吸计分</h5>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="cramsScore.breath" value="4" />  10~29</label>
                <label><input type="radio" v-model="cramsScore.breath" value="3" />  ＞29</label>
                <label><input type="radio" v-model="cramsScore.breath" value="2" />  6~9</label>
                <label><input type="radio" v-model="cramsScore.breath" value="1" />  1~5</label>
                <label><input type="radio" v-model="cramsScore.breath" value="0" />  0</label>
              </div>
            </div>

            <div class="score-section">
              <div class="section-header">
                <h5>收缩压</h5>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="cramsScore.chest" value="4"/> ＞89</label>
                <label><input type="radio" v-model="cramsScore.chest" value="3"/> 76~89</label>
                <label><input type="radio" v-model="cramsScore.chest" value="2"/> 50~75</label>
                <label><input type="radio" v-model="cramsScore.chest" value="1"/> 1~49</label>
                <label><input type="radio" v-model="cramsScore.chest" value="0"/> ＜1  </label>
              </div>
            </div>

            <div class="score-section">
              <div class="section-header">
                <h5>Glasgow评分</h5>
              </div>
              <div class="options-grid">
                <label><input type="radio" v-model="cramsScore.sport" value="4"/> 13~15</label>
                <label><input type="radio" v-model="cramsScore.sport" value="3"/> 9~12</label>
                <label><input type="radio" v-model="cramsScore.sport" value="2"/> 6~8</label>
                <label><input type="radio" v-model="cramsScore.sport" value="1"/> 4~5</label>
                <label><input type="radio" v-model="cramsScore.sport" value="0"/> 3</label>
              </div>
            </div>
            
            <!-- CRAMS总分展示 -->
            <div class="total-score">
              创伤评分：{{ calculateCramsTotal() }} / 12
            </div>
            <!-- CRAMS评分结果判定 -->
            <div v-if="finalResult" class="result-detail" style="margin-top: 2rem;">
              <div :class="['result-badge', finalResult.color]" style="color: antiquewhite;">
                <h4 :class="['severity-text', finalResult.color]" style="color: aliceblue">
                  {{ finalResult.severity }}
                </h4>
                <div class="priority-level">
                  优先级: {{ finalResult.priority }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RF智能检伤APACHE II分类 -->
        <div v-if="activeTab === 'rf'" class="scoring-content">
          <div class="total-score" style="margin-top:.75rem;" @click="fetchData">
            智能检伤APACHE II 分类： {{ 
              prediction === 0 ? '低危' : 
              prediction === 1 ? '中度危重' : 
              prediction === 2 ? '重度危重' : 
              '未评估' 
            }}
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- GCS专用信息弹窗 -->
  <div v-if="showModal" class="modal-overlay" @click="closeModal">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3 class="modal-title">{{ modalData.title }}</h3>
        <button class="modal-close" @click="closeModal">×</button>
      </div>
      <div class="modal-body">
        <p class="modal-desc">{{ modalData.description }}</p>
        <!-- 评估提问提示区 -->
        <div class="modal-questions">
          <h4>💬 评估提问提示（点击喇叭播报）</h4>
          <div class="question-list">
            <div class="question-item" v-for="(question, idx) in modalData.questions" :key="idx">
              <button class="single-voice-btn" @click="playSingleVoice(question)">
                <span class="voice-icon">🔊</span>
              </button>
              <span class="question-text">{{ question }}</span>
            </div>
          </div>
        </div>
        <!-- 评分标准区 -->
        <div class="modal-details">
          <h4>📝 评分标准（根据伤员反应打分）</h4>
          <ul class="score-list">
            <li v-for="(item, key) in modalData.details" :key="key">
              <span class="score-value">{{ key }}分：</span>
              <span class="score-desc">{{ item }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="modal-footer">
        <button class="modal-confirm" @click="closeModal">我知道了</button>
      </div>
    </div>
  </div>

  <!-- PHI/START专用信息弹窗 -->
  <div v-if="showModal2" class="modal-overlay" @click="closeModal2">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3 class="modal-title">{{ modalData.title }}</h3>
        <button class="modal-close" @click="closeModal2">×</button>
      </div>
      <div class="modal-body">
        <p class="modal-desc">{{ modalData.description }}</p>
        <div class="modal-details">
          <h4>📝 评分标准（根据伤员反应打分）</h4>
          <ul class="score-list">
            <li v-for="(item, key) in modalData.details" :key="key">
              <span class="score-value">{{ key }}分：</span>
              <span class="score-desc">{{ item }}</span>
            </li>
          </ul>
        </div>
      </div>
      <div class="modal-footer">
        <button class="modal-confirm" @click="closeModal2">我知道了</button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 引入vue核心API、axios请求库
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

// 向父组件派发评分变化事件
const emit = defineEmits(['score-change'])

/************************** 基础配置 - 标签页相关 **************************/
// 当前激活的标签页
const activeTab = ref('start')
// 所有评分标签页配置
const scoringTabs = ref([
  { id: 'glasgow', label: 'Glasgow' },
  { id: 'phi', label: 'PHI' },
  { id: 'start', label: 'START' },
  { id: 'crams', label: 'CRAMS'},
  { id: 'rf', label: 'RF'}
])

/************************** 核心评分数据模型 **************************/
// Glasgow昏迷量表评分数据 - 初始默认满分
const glasgowScore = ref({
  eyeOpening: '4',        // 睁眼反应
  verbalResponse: '5',    // 语言反应
  motorResponse: '6'      // 运动反应
})

// PHI生理评分数据 - 初始默认满分
const phiScore = ref({
  systolicPressure: '0',  // 收缩压
  pulse: '0',             // 脉搏
  breathing: '0',         // 呼吸状态
  consciousness: '0'      // 意识状态
})

// CRAMS简易创伤评分数据
const cramsScore = ref({
  breath: '2',  // 呼吸计分
  chest: '2',   // 收缩压计分
  sport: '2'    // GCS段位计分
})

/************************** 弹窗相关功能 **************************/
// 弹窗显示状态
const showModal = ref(false)
const showModal2 = ref(false)
// 弹窗展示数据
const modalData = ref({
  title: '',
  description: '',
  details: {},
  questions: [],
  videos: [{ title: '开放气道', src: '/videos/qidao.mp4', type: 'video/mp4' }] 
})

// 打开GCS专用弹窗
const openModal = (type) => {
  switch (type) {
    case 'eye':
      modalData.value = { title: '睁眼反应 (Eye Opening, E)', description: '评估患者对刺激的睁眼反应，反映大脑皮质和脑干网状激活系统的功能状态。', questions: ["你能自己睁开眼睛吗？","听到我的声音请睁开眼睛！","（轻按眼眶）有感觉的话请睁眼！"], details: { 4: '自主睁眼：无需任何刺激自行睁眼', 3: '呼唤睁眼：仅大声呼唤后睁眼', 2: '疼痛睁眼：仅按压眼眶等疼痛刺激后睁眼', 1: '不能睁眼：任何刺激均无睁眼反应' } }
      break
    case 'verbal':
      modalData.value = { title: '语言反应 (Verbal Response, V)', description: '评估患者的语言表达能力，需排除气管插管、失语等非意识因素影响。', questions: ["你叫什么名字？","现在在哪里？","今天是几号？","能说一句话吗？"], details: { 5: '对答切题：准确回答姓名/位置等问题', 4: '对答错乱：能说话但答非所问 ', 3: '单词应答：仅能说单个词（如“痛”）', 2: '呻吟声：仅发出无意义呻吟', 1: '无语言反应：无任何声音输出' } }
      break
    case 'motor':
      modalData.value = { title: '运动反应 (Motor Response, M)', description: '评估患者对刺激的肢体运动反应，需分别评估左右肢体。', questions: ["请抬一下你的左手！","请抬一下你的右手！","请握紧我的手！","（轻掐手臂）有感觉的话动一下手脚！"], details: { 6: '听从指令：按要求完成抬手/握拳等动作', 5: '定位疼痛：能触摸/拍打疼痛部位', 4: '屈曲回避：疼痛时肢体屈曲回避', 3: '异常屈曲：上肢屈曲、下肢伸直（去皮层强直）', 2: '异常伸展：四肢伸直、肌张力增高（去大脑强直）', 1: '无运动反应：无任何肢体动作' } }
      break
  }
  showModal.value = true
}

// 打开PHI/START专用弹窗
const openModal2 = (type) => {
  switch (type) {
    case 'PHIBreath':
      modalData.value = { title: '呼吸', description: '', details: { 0: '正常：患者自主呼吸，频率16-20次/分，节律规整，胸廓起伏对称，无辅助呼吸肌参与。', 3: '费力或浅：患者呼吸时可见鼻翼扇动、三凹征，或呼吸浅快（>25次/分），幅度不足正常一半。', 5: '<10次/分或需插管：患者出现呼吸暂停，或因血氧饱和度持续低于90%已进行气管插管辅助通气。' } }
      break
    case 'PHIConscious':
      modalData.value = { title: '意识', description: '', details: { 0: '正常：患者能清晰说出自己的姓名、所在地和当前年份。', 3: '模糊或烦躁：患者仅能对简单指令做出反应，时间地点人物定向力下降，或表现出躁动不安、试图拔除输液管。', 5: '言语不能理解：患者能发出声音但词句杂乱无章，或仅能发出无意义的单音，无法进行有效沟通。' } }
      break
    case 'Start':
      modalData.value = { title: 'START 检伤分级标准', description: '以下是具体操作方法：', details: { 1: '能否行走：大声呼喊让所有还能自行走动的伤员站到一边。', 2: '检查呼吸：无呼吸 → 立即清理气道 → 若仍无呼吸 → 标记黑色；清理气道后恢复呼吸 → 标记红色；有呼吸但频率 >30 次/分钟 → 标记红色。', 3: '检查循环：触摸桡动脉有搏动/毛细血管充盈时间<2秒，提示循环良好。', 4: '检查意识状态：给予简单指令判断意识水平，严重者标记红色。', 5: '控制出血：大出血伤员需立即止血，确保生命体征稳定。', 6: '最终确定伤员优先级并进行标记（红/黄/绿/黑）。' }, videos: [{ title: '开放气道：', src: '/videos/qidao.mp4', type: 'video/mp4' }] }
      break
  }
  showModal2.value = true
}

// 语音播报单个评估问题
const playSingleVoice = (text) => {
  if (window.speechSynthesis.speaking) window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'zh-CN'; // 中文播报
  utterance.volume = 1;     // 音量
  utterance.rate = 0.9;     // 语速放缓更清晰
  utterance.pitch = 1;      // 音调
  window.speechSynthesis.speak(utterance);
};

// 关闭弹窗并停止语音播报
const closeModal = () => {
  showModal.value = false;
  window.speechSynthesis.speaking && window.speechSynthesis.cancel();
};
const closeModal2 = () => {
  showModal2.value = false;
  window.speechSynthesis.speaking && window.speechSynthesis.cancel();
};

/************************** START检伤流程专用配置 **************************/
// START检伤分级结果
const triageLevel = ref('')
// START评估流程数据
const startFlow = ref({
  currentStep: 'canWalk',  // 当前评估步骤
  path: [],                // 评估路径记录
  finalResult: null,       // 最终评估结果
  answers: {}              // 步骤答案存储
})

/************************** 评分计算核心方法 **************************/
// 计算GCS格拉斯哥总分 + 联动更新CRAMS的GCS段位分 + 存储GCS到本地缓存
const calculateGlasgowTotal = () => {
  const eye = parseInt(glasgowScore.value.eyeOpening) || 0
  const verbal = parseInt(glasgowScore.value.verbalResponse) || 0
  const motor = parseInt(glasgowScore.value.motorResponse) || 0
  const total = eye + verbal + motor
  
  // 存储GCS总分到本地缓存
  localStorage.setItem('GCS', JSON.stringify(total));
  localStorage.setItem('heartRate', JSON.stringify(12));

  // GCS总分联动更新CRAMS的sport字段
  if (total >=13) cramsScore.value.sport = '4';
  else if (total >=9) cramsScore.value.sport = '3';
  else if (total >=6) cramsScore.value.sport = '2';
  else if (total >=4) cramsScore.value.sport = '1';
  else cramsScore.value.sport = '0';
  
  return total
}

// GCS评分结果自动判定
const finalResult_gla = computed(() => {
  const total = calculateGlasgowTotal()
  if (total >=13 && total <=15) return { severity: '轻度', priority: '低', color: 'green' }
  else if (total >=9 && total <=12) return { severity: '中度', priority: '中', color: 'yellow' }
  else return { severity: '重度', priority: '高', color: 'red' }
})

// 计算PHI生理评分总分
const calculatePHITotal = () => {
  const systolic = parseInt(phiScore.value.systolicPressure) || 0
  const pulse = parseInt(phiScore.value.pulse) || 0
  const breathing = parseInt(phiScore.value.breathing) || 0
  const consciousness = parseInt(phiScore.value.consciousness) || 0
  return systolic + pulse + breathing + consciousness
}

// 计算CRAMS创伤评分总分
const calculateCramsTotal = () => {
  const breath = parseInt(cramsScore.value.breath) || 0
  const chest = parseInt(cramsScore.value.chest) || 0
  const sport = parseInt(cramsScore.value.sport) || 0
  return breath + chest + sport 
}

// CRAMS评分结果自动判定
const finalResult = computed(() => {
  const total = calculateCramsTotal()
  if (total === 12) return { severity: '轻伤', priority: '低', color: 'green' }
  else if (total >=10 && total <=11) return { severity: '中度伤', priority: '高', color: 'yellow' }
  else if (total >=6 && total <=9) return { severity: '重伤', priority: '紧急', color: 'red' }
  else return { severity: '危重伤', priority: '紧急', color: 'red' }
})

/************************** START评估流程控制方法 **************************/
// 重置START评估流程
const resetStartFlow = () => {
  startFlow.value = { currentStep: 'canWalk', path: [], finalResult: null, answers: {} }
}

// 处理START评估步骤选择
const handleStartChoice = (step, answer) => {
  startFlow.value.answers[step] = answer
  // 映射问题文本和答案文本，用于路径展示
  const questionTexts = { canWalk: '伤员能否行走', hasBreathing: '呼吸有无', respiratoryRate: '呼吸速率>30次', breathingAfterAirway: '重新打开呼吸道后呼吸有无', radialPulse: '桡动脉搏动及微血管充填时间', controlBleeding: '控制出血', consciousness: '意识清楚能否沟通' }
  const answerTexts = { yes: '是', no: '否', controlled: '已控制' }
  startFlow.value.path.push({ question: questionTexts[step], answer: answerTexts[answer] || answer })

  let nextStep = null, result = null
  // 流程分支逻辑
  switch (step) {
    case 'canWalk': answer === 'yes' ? result = { color: 'green', label: '绿色 - 延缓', description: '轻伤，可以等待治疗', priority: '第四优先' } : nextStep = 'hasBreathing'; break
    case 'hasBreathing': answer === 'no' ? nextStep = 'breathingAfterAirway' : nextStep = 'respiratoryRate'; break
    case 'respiratoryRate': answer === 'yes' ? result = { color: 'red', label: '红色 - 紧急', description: '生命危险，需要立即治疗', priority: '第一优先' } : nextStep = 'radialPulse'; break
    case 'breathingAfterAirway': answer === 'no' ? result = { color: 'black', label: '黑色 - 死亡', description: '已死亡或濒死', priority: '最低优先' } : result = { color: 'red', label: '红色 - 紧急', description: '生命危险，需要立即治疗', priority: '第一优先' }; break
    case 'radialPulse': answer === 'yes' ? nextStep = 'consciousness' : nextStep = 'controlBleeding'; break
    case 'controlBleeding': result = { color: 'red', label: '红色 - 紧急', description: '生命危险，需要立即治疗', priority: '第一优先' }; break
    case 'consciousness': answer === 'no' ? result = { color: 'red', label: '红色 - 紧急', description: '生命危险，需要立即治疗', priority: '第一优先' } : result = { color: 'yellow', label: '黄色 - 紧迫', description: '伤势严重但暂无生命危险', priority: '第二优先' }; break
  }

  // 更新结果或下一步骤
  if (result) { startFlow.value.finalResult = result; startFlow.value.currentStep = null; triageLevel.value = result.color }
  else if (nextStep) startFlow.value.currentStep = nextStep
}

/************************** 数据监听 - 评分变化派发事件 **************************/
// 监听GCS评分变化，向父组件派发事件
watch(glasgowScore, (newVal) => emit('score-change', { type: 'glasgow', data: newVal }), { deep: true })
// 监听PHI评分变化，向父组件派发事件
watch(phiScore, (newVal) => emit('score-change', { type: 'phi', data: newVal }), { deep: true })
// 监听CRAMS评分变化，向父组件派发事件
watch(cramsScore, (newVal) => emit('score-change', { type: 'crams', data: newVal }), { deep: true })
// 监听START分级变化，向父组件派发事件
watch(triageLevel, (newVal) => emit('score-change', { type: 'start', data: newVal }))

/************************** 智能检伤(RF)相关功能 **************************/
const vitalSigns = ref(null);    // 生命体征数据
const GCSGCS = ref('');          // GCS缓存数据
const ageage = ref('');          // 年龄缓存数据
const prediction = ref('0');     // 智能检伤结果 0-低危 1-中度危重 2-重度危重
const isLoading = ref('');       // 加载状态

// 读取本地缓存生命体征数据，执行智能检伤
const fetchData = () => {
  try {
    const storedData = localStorage.getItem('sharedData');
    const gcsgcs = localStorage.getItem('GCS');
    const ag = localStorage.getItem('age');
    if (storedData) {
      vitalSigns.value = JSON.parse(storedData);
      GCSGCS.value = JSON.parse(gcsgcs);
      ageage.value = JSON.parse(ag);
      handleSubmit(vitalSigns.value);
    }
  } catch (error) { console.error('获取数据失败：', error); }
  applySharedVitalsToScores(); // 同步生命体征到各评分项
};

// 智能检伤接口请求（原代码注释，保留方法体）
const handleSubmit = async () => {
  try {
    isLoading.value = true;
    const apacheApiBase = import.meta.env.VITE_APACHE_API_BASE || '/apache-api';
    const response = await axios.post(`${apacheApiBase}/predict`, { 'GCSGCS':GCSGCS.value, 'vitalSigns':vitalSigns.value, 'age': ageage.value }, { headers: { 'Content-Type': 'application/json' } });
    prediction.value = response.data.prediction
  } catch (err) { console.error('检伤接口请求失败：', err); } finally { isLoading.value = false; }
}

/************************** 生命体征自动同步到评分项核心逻辑 **************************/
// 读取并标准化本地缓存的生命体征数据
const readSharedVitals = () => {
  try {
    const raw = localStorage.getItem('sharedData');
    if (!raw) return null;
    const d = JSON.parse(raw);
    const toNum = (v) => {
      if (v === null || v === undefined) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    return {
      heartRate: toNum(d.heartRate),
      respiratoryRate: toNum(d.respiratoryRate),
      systolicPressure: toNum(d.systolicPressure),
      diastolicPressure: toNum(d.diastolicPressure),
      temperature: toNum(d.temperature),
      oxygenSaturation: toNum(d.oxygenSaturation)
    };
  } catch (e) { console.warn('生命体征数据解析失败：', e); return null; }
};

// 生命体征映射到PHI评分项
const applyToPHI = (v) => {
  if (!v) return;
  // 收缩压映射
  if (v.systolicPressure != null) {
    const sbp = v.systolicPressure;
    phiScore.value.systolicPressure = sbp>100?'0':sbp>=86?'1':sbp>=75?'2':'3';
  }
  // 脉搏映射
  if (v.heartRate != null) {
    const hr = v.heartRate;
    phiScore.value.pulse = hr>=120?'3':hr<=50?'5':'0';
  }
  // 呼吸状态映射
  if (v.respiratoryRate != null) {
    const rr = v.respiratoryRate;
    phiScore.value.breathing = rr<10?'5':rr>=25?'3':'0';
  }
};

// 生命体征映射到CRAMS评分项
const applyToCRAMS = (v) => {
  if (!v) return;
  // 呼吸计分映射
  if (v.respiratoryRate != null) {
    const rr = v.respiratoryRate;
    if (rr ===0) cramsScore.value.breath='0';
    else if (rr>=1&&rr<=5) cramsScore.value.breath='1';
    else if (rr>=6&&rr<=9) cramsScore.value.breath='2';
    else if (rr>=10&&rr<=29) cramsScore.value.breath='4';
    else cramsScore.value.breath='3';
  }
  // 收缩压映射
  if (v.systolicPressure != null) {
    const sbp = v.systolicPressure;
    cramsScore.value.chest = sbp<1?'0':sbp<=49?'1':sbp<=75?'2':sbp<=89?'3':'4';
  }
};

// GCS总分同步更新CRAMS的sport字段
const updateCramsSportFromGCS = () => {
  const g = calculateGlasgowTotal();
  cramsScore.value.sport = g>=13?'4':g>=9?'3':g>=6?'2':g>=4?'1':'0';
};

// 总入口：同步生命体征到所有评分项
const applySharedVitalsToScores = () => {
  const v = readSharedVitals();
  if (!v) return;
  applyToPHI(v);
  applyToCRAMS(v);
  updateCramsSportFromGCS();
};

/************************** 定时同步生命体征数据 **************************/
const heartRatee = ref(null);        // 呼吸率响应式变量
const systolicPressure = ref(null);  // 收缩压响应式变量
let syncTimer = null;                // 定时器ID，防止内存泄漏

// 从本地缓存同步生命体征到响应式变量
const syncFromStorage = () => {
  try {
    const stored = localStorage.getItem('sharedData');
    if (stored !== null) {
      const data = JSON.parse(stored);
      if (heartRatee.value !== data.respiratoryRate) heartRatee.value = data.respiratoryRate;
      if (systolicPressure.value !== data.systolicPressure) systolicPressure.value = data.systolicPressure;
    } else {
      heartRatee.value = null;
      systolicPressure.value = null;
    }
  } catch (e) { console.error('同步数据失败:', e); }
};

// 更新呼吸率到本地缓存
const setHeartRate = (value) => {
  try {
    const storedData = JSON.parse(localStorage.getItem('sharedData') || '{}');
    storedData.respiratoryRate = value;
    localStorage.setItem('sharedData', JSON.stringify(storedData));
    heartRatee.value = value;
  } catch (e) { console.error('设置呼吸率失败:', e); }
};

// 更新收缩压到本地缓存
const setSystolicPressure = (value) => {
  try {
    const storedData = JSON.parse(localStorage.getItem('sharedData') || '{}');
    storedData.systolicPressure = value;
    localStorage.setItem('sharedData', JSON.stringify(storedData));
    systolicPressure.value = value;
  } catch (e) { console.error('设置收缩压失败:', e); }
};

// 监听呼吸率变化，自动更新CRAMS评分
watch(heartRatee, (newVal) => {
  if (newVal === null) return;
  const rr = newVal;
  cramsScore.value.breath = rr===0?'0':rr>=1&&rr<=5?'1':rr>=6&&rr<=9?'2':rr>=10&&rr<=29?'4':'3';
}, { immediate: true })

// 监听收缩压变化，自动更新PHI/CRAMS评分
watch(systolicPressure, (newVal) => {
  if (newVal === null) return;
  const sp = newVal;
  // 更新CRAMS
  cramsScore.value.chest = sp>89?'4':sp>=76&&sp<=89?'3':sp>=50&&sp<=75?'2':sp>=1&&sp<=49?'1':'0';
  // 更新PHI
  phiScore.value.systolicPressure = sp>100?'0':sp>=86&&sp<=100?'1':sp>=75&&sp<=85?'2':'3';
}, { immediate: true })

/************************** 组件生命周期钩子 **************************/
// 组件挂载时初始化
onMounted(() => {
  applySharedVitalsToScores();          // 初始化同步生命体征
  syncFromStorage();                    // 初始化同步响应式变量
  syncTimer = setInterval(syncFromStorage, 1000); // 每秒同步一次数据
  window.addEventListener('storage', () => applySharedVitalsToScores()); // 监听缓存变化
});

// 组件卸载时销毁资源，防止内存泄漏
onBeforeUnmount(() => {
  if (syncTimer) clearInterval(syncTimer);
  window.removeEventListener('storage', () => applySharedVitalsToScores());
});

/************************** 暴露数据给父组件调用 **************************/
defineExpose({
  activeTab, glasgowScore, phiScore, startFlow, triageLevel, cramsScore,
  calculateGlasgowTotal, calculatePHITotal, resetStartFlow, handleStartChoice
})
</script>

<style scoped>
.score-assessment { height: 100%; }
/* 评分系统整体样式 */
.scoring-tabs {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.85) 0%, rgba(30, 60, 114, 0.7) 100%);
  backdrop-filter: blur(25px);
  border: 1px solid rgba(79, 195, 247, 0.4);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 0 0 1px rgba(79, 195, 247, 0.2);
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
/* 标签页头部样式 */
.tab-headers { display: flex; background: rgba(0, 0, 0, 0.2); border-bottom: 1px solid rgba(79, 195, 247, 0.3); position: sticky; top: 0; z-index: 5; }
.tab-button {
  flex: 1; padding: 0.8rem 1rem; background: transparent; border: none; color: #b3e5fc; font-size: 0.85rem; font-weight: 500; cursor: pointer; transition: all 0.3s ease; border-right: 1px solid rgba(79, 195, 247, 0.2);
}
.tab-button:last-child { border-right: none; }
.tab-button.active { background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.15) 100%); color: #4fc3f7; border-bottom: 2px solid #4fc3f7; }
.tab-button:hover:not(.active) { background: rgba(79, 195, 247, 0.1); color: #81d4fa; }
/* 标签页内容区样式 */
.tab-content { flex: 1; padding: 1.25rem; overflow: auto; }
.scoring-content h4 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: #4fc3f7; }
/* 评分项头部样式 - 标题+信息按钮 */
.section-header { display: flex; justify-content: flex-start; align-items: center; gap: 8px; }
.start-scoring .section-header h4 { margin: 0; line-height: 1.2; }
/* 信息按钮样式 */
.info-btn {
  width: 24px; height: 24px; border-radius: 50%; background: linear-gradient(135deg, rgba(79, 195, 247, 0.3) 0%, rgba(41, 182, 246, 0.2) 100%);
  border: 1px solid rgba(79, 195, 247, 0.5); color: #4fc3f7; font-size: 0.8rem; font-weight: bold; cursor: pointer;
  display: flex; align-items: center; justify-content: center; transition: all 0.3s ease;
}
.info-btn:hover { background: linear-gradient(135deg, rgba(79, 195, 247, 0.5) 0%, rgba(41, 182, 246, 0.4) 100%); border-color: #4fc3f7; transform: scale(1.1); }
/* 评分项区块样式 */
.score-section { margin-bottom: 1.5rem; padding: 1rem 0 1rem 1rem; background: rgba(0, 0, 0, 0.2); border-radius: 8px; border-left: 3px solid #4fc3f7; }
.score-section h5 { font-size: 0.9rem; font-weight: 600; color: #81d4fa; margin: 0; }
.score-section label { display: block; margin-bottom: 0.5rem; font-size: 0.85rem; cursor: pointer; transition: color 0.3s ease; }
.score-section label:hover { color: #4fc3f7; }
/* 选项网格样式 */
.options-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; margin-top: 0.5rem; }
.crams-scoring .options-grid { display: flex; flex-direction: column; gap: 0.5rem; }
/* 总分展示样式 */
.total-score {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.15) 100%);
  padding: 1rem; border-radius: 8px; text-align: center; font-size: 1.1rem; font-weight: 600; color: #4fc3f7;
  border: 1px solid rgba(79, 195, 247, 0.3);
}
/* PHI评分专项样式 */
.phi-scoring { display: flex; flex-direction: column; gap: 1rem; }
.phi-item { display: inline; flex-direction: column; gap: 0.5rem; padding: 1rem; background: rgba(0, 0, 0, 0.2); border-radius: 8px; border-left: 3px solid #4fc3f7; }
.phi-item label { font-size: 0.9rem; font-weight: 600; color: #81d4fa; }
.phi-item input, .phi-item select {
  padding: 0.4rem; background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(79, 195, 247, 0.3); border-radius: 6px;
  color: white; font-size: 0.9rem; transition: all 0.3s ease;
}
.phi-item select { float: right; min-width: 180px; }
.phi-item input:focus, .phi-item select:focus { border-color: #4fc3f7; box-shadow: 0 0 0 2px rgba(79, 195, 247, 0.2); outline: none; }
/* PHI分数拆解样式 */
.score-breakdown { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; margin-bottom: 1rem; }
.score-item { background: rgba(0, 0, 0, 0.3); padding: 0.5rem; border-radius: 4px; font-size: 0.8rem; text-align: center; border: 1px solid rgba(79, 195, 247, 0.2); }
.total-line { font-size: 1.2rem; font-weight: 700; text-align: center; margin-bottom: 0.8rem; color: #4fc3f7; }
/* 严重程度标签样式 */
.severity-interpretation { text-align: center; }
.severity { padding: 0.5rem 1rem; border-radius: 20px; font-weight: 600; font-size: 0.9rem; }
.severity.mild { background: linear-gradient(135deg, #4caf50 0%, #66bb6a 100%); color: white; }
.severity.moderate { background: linear-gradient(135deg, #ff9800 0%, #ffb74d 100%); color: white; }
.severity.severe { background: linear-gradient(135deg, #f44336 0%, #ef5350 100%); color: white; }
/* START流程专项样式 */
.flow-controls { margin-top: 1.5rem; margin-bottom: 1.5rem; text-align: center; }
.reset-flow-btn {
  background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); border: none; color: white; padding: 0.6rem 1.2rem;
  border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.3s ease;
}
.reset-flow-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(255, 152, 0, 0.3); }
.start-flow { display: flex; flex-direction: column; gap: 1.5rem; }
.flow-question {
  background: rgba(0, 0, 0, 0.2); border: 1px solid rgba(79, 195, 247, 0.3); border-radius: 10px;
  padding: 1.5rem; transition: all 0.3s ease;
}
.flow-question.active { border-color: #4fc3f7; box-shadow: 0 0 20px rgba(79, 195, 247, 0.2); animation: questionPulse 2s ease-in-out infinite; }
@keyframes questionPulse { 0%,100% { box-shadow: 0 0 20px rgba(79, 195, 247, 0.2); } 50% { box-shadow: 0 0 30px rgba(79, 195, 247, 0.4); } }
.flow-question h5 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: #4fc3f7; text-align: center; }
.flow-options { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
.flow-btn {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.2) 0%, rgba(41, 182, 246, 0.3) 100%);
  border: 2px solid rgba(79, 195, 247, 0.5); color: white; padding: 0.8rem 1.5rem; border-radius: 8px;
  font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: all 0.3s ease; min-width: 80px;
}
.flow-btn:hover { background: linear-gradient(135deg, rgba(79, 195, 247, 0.4) 0%, rgba(41, 182, 246, 0.5) 100%); border-color: #4fc3f7; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(79, 195, 247, 0.3); }
.flow-btn.yes { background: linear-gradient(135deg, rgba(76, 175, 80, 0.2) 0%, rgba(102, 187, 106, 0.3) 100%); border-color: rgba(76, 175, 80, 0.5); }
.flow-btn.yes:hover { background: linear-gradient(135deg, rgba(76, 175, 80, 0.4) 0%, rgba(102, 187, 106, 0.5) 100%); border-color: #4caf50; box-shadow: 0 6px 20px rgba(76, 175, 80, 0.3); }
.flow-btn.no { background: linear-gradient(135deg, rgba(244, 67, 54, 0.2) 0%, rgba(239, 83, 80, 0.3) 100%); border-color: rgba(244, 67, 54, 0.5); }
.flow-btn.no:hover { background: linear-gradient(135deg, rgba(244, 67, 54, 0.4) 0%, rgba(239, 83, 80, 0.5) 100%); border-color: #f44336; box-shadow: 0 6px 20px rgba(244, 67, 54, 0.3); }
/* 评估路径样式 */
.assessment-path { background: rgba(0, 0, 0, 0.3); border-radius: 8px; padding: 1rem; border-left: 3px solid #4fc3f7; }
.assessment-path h5 { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.8rem; color: #81d4fa; }
.path-steps { display: flex; flex-direction: column; gap: 0.5rem; }
.path-step { font-size: 0.85rem; padding: 0.3rem 0; display: flex; align-items: center; gap: 0.5rem; }
.path-step strong { color: #4fc3f7; }
.arrow { color: #81d4fa; font-weight: bold; }
/* 最终结果样式 */
.final-result { margin-top: 1.5rem; }
.result-badge { padding: 1.5rem; border-radius: 12px; text-align: center; border: 2px solid; animation: resultAppear 0.5s ease-out; }
@keyframes resultAppear { from { opacity: 0; transform: scale(0.8); } to { opacity: 1; transform: scale(1); } }
.result-badge.red { background: linear-gradient(135deg, rgba(244, 67, 54, 0.3) 0%, rgba(229, 57, 53, 0.2) 100%); border-color: #f44336; color: #ffcdd2; }
.result-badge.yellow { background: linear-gradient(135deg, rgba(255, 235, 59, 0.3) 0%, rgba(251, 192, 45, 0.2) 100%); border-color: #ffeb3b; color: #1a1a1a; }
.result-badge.green { background: linear-gradient(135deg, rgba(76, 175, 80, 0.3) 0%, rgba(102, 187, 106, 0.2) 100%); border-color: #4caf50; color: #c8e6c9; }
.result-badge.black { background: linear-gradient(135deg, rgba(96, 125,139, 0.3) 0%, rgba(120, 144, 156, 0.2) 100%); border-color: #607d8b; color: #cfd8dc; }
.result-badge h4 { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; }
.result-badge p { font-size: 0.95rem; margin-bottom: 0.8rem; opacity: 0.9; }
.priority-level { font-size: 0.85rem; font-weight: 600; opacity: 0.8; }
/* 弹窗样式 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(5px); display: flex; align-items: center; justify-content: center; z-index: 1000; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.modal-content {
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.95) 0%, rgba(30, 60, 114, 0.9) 100%);
  border: 1px solid rgba(79, 195, 247, 0.6); border-radius: 12px; width: 90%; max-width: 500px; max-height: 80vh;
  overflow-y: auto; box-shadow: 0 10px 50px rgba(0, 0, 0, 0.5); animation: slideIn 0.3s ease;
}
@media (min-width: 1024px) { .modal-content { max-width: 720px; } }
@keyframes slideIn { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid rgba(79, 195, 247, 0.3); }
.modal-title { font-size: 1.1rem; font-weight: 600; color: #4fc3f7; margin: 0; }
.modal-close { background: none; border: none; color: #b3e5fc; font-size: 1.5rem; cursor: pointer; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: 50%; transition: all 0.2s ease; }
.modal-close:hover { background: rgba(79, 195, 247, 0.2); color: #4fc3f7; }
.modal-body { padding: 1.25rem; }
.modal-desc { color: #e0f7fa; margin-bottom: 1.25rem; line-height: 1.5; font-size: 0.95rem; }
.modal-details h4 { font-size: 1rem; color: #81d4fa; margin-bottom: 0.75rem; font-weight: 600; }
.score-list { list-style-type: none; padding: 0; margin: 0; }
.score-list li { padding: 0.75rem 0; border-bottom: 1px solid rgba(79, 195, 247, 0.15); display: flex; flex-direction: column; gap: 0.25rem; }
.score-list li:last-child { border-bottom: none; }
.score-value { font-weight: 600; color: #4fc3f7; }
.score-desc { color: #e0f7fa; font-size: 0.9rem; line-height: 1.4; }
.modal-footer { padding: 1rem 1.25rem; border-top: 1px solid rgba(79, 195, 247, 0.3); text-align: right; }
.modal-confirm {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.3) 0%, rgba(41, 182, 246, 0.4) 100%);
  border: 1px solid rgba(79, 195, 247, 0.6); color: white; padding: 0.5rem 1.25rem; border-radius: 6px;
  font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: all 0.3s ease;
}
.modal-confirm:hover { background: linear-gradient(135deg, rgba(79, 195, 247, 0.5) 0%, rgba(41, 182, 246, 0.6) 100%); border-color: #4fc3f7; box-shadow: 0 4px 15px rgba(79, 195, 247, 0.3); }
/* 提问提示区样式 */
.modal-questions { margin: 1rem 0; padding: 1rem; background: rgba(0, 0, 0, 0.2); border-radius: 8px; border-left: 3px solid #4fc3f7; }
.modal-questions h4 { font-size: 1rem; color: #81d4fa; margin: 0 0 0.8rem 0; font-weight: 600; }
.question-list { display: flex; flex-direction: column; gap: 0.6rem; }
.question-item { display: flex; align-items: center; gap: 0.8rem; padding: 0.5rem; border-radius: 4px; transition: background 0.2s ease; }
.question-item:hover { background: rgba(79, 195, 247, 0.1); }
.single-voice-btn {
  background: linear-gradient(135deg, rgba(79, 195, 247, 0.3) 0%, rgba(41, 182, 246, 0.2) 100%);
  border: 1px solid #4fc3f7; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  color: white; cursor: pointer; flex-shrink: 0;
}
.single-voice-btn:hover { background: linear-gradient(135deg, rgba(79, 195, 247, 0.5) 0%, rgba(41, 182, 246, 0.4) 100%); }
.question-text { color: #e0f7fa; font-size: 0.9rem; line-height: 1.4; }
/* 通用样式优化 */
.form-grid { display: grid; grid-template-columns: 1fr; gap: .75rem 1rem; }
@media (min-width: 768px) { .form-grid { grid-template-columns: 1fr 1fr; } }
.field { display: grid; grid-template-columns: 200px 1fr; gap: .5rem; align-items: center; background: rgba(0,0,0,.2); border: 1px solid rgba(79,195,247,.25); border-left: 3px solid #4fc3f7; border-radius: 8px; padding: .6rem .75rem; }
.field > label { color: #81d4fa; font-weight: 600; font-size: .9rem; }
.controls { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.controls input[type="number"], .controls select { min-height: 34px; padding: .35rem .5rem; background: rgba(0,0,0,.3); border: 1px solid rgba(79,195,247,.3); border-radius: 6px; color: #fff; width: 140px; }
.controls input:focus, .controls select:focus { border-color: #4fc3f7; outline: none; }
.score-display { margin: 0; padding: .35rem .6rem; }
.phi-item { display: grid; grid-template-columns: 200px 1fr; align-items: center; }
.phi-item select { float: none; justify-self: start; min-width: 180px; }
</style>