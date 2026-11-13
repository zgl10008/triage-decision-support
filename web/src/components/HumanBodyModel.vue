<template>
  <div class="injury-assessment">
    <div class="injury-content">
      <!-- 左侧：受伤部位勾选区 -->
      <div class="injury-options">
        <h4>受伤部位</h4>
        <div class="injury-parts-section">
          <h5>受伤部位:</h5>
          <div class="parts-checkboxes">
            <label v-for="(name, key) in bodyParts" :key="key">
              <input
                type="checkbox"
                :value="key"
                v-model="injuredParts"
                @change="onPartCheckboxChange(key, $event)"
              />
              {{ name }}
            </label>
          </div>
        </div>
      </div>

      <!-- 右侧-人体SVG模型区域 -->
      <div class="body-model">
        <div class="model-wrapper">
          <svg viewBox="0 0 200 400" class="body-svg">
            <!-- 头部 -->
            <ellipse cx="100" cy="50" rx="25" ry="30" :class="getPartClass('head')" @click="onSvgPartClick('head')" />
            <!-- 颈部 -->
            <rect x="90" y="80" width="20" height="15" rx="5" :class="getPartClass('neck')" @click="onSvgPartClick('neck')" />
            <!-- 胸部 -->
            <rect x="75" y="95" width="50" height="60" rx="10" :class="getPartClass('chest')" @click="onSvgPartClick('chest')" />
            <!-- 腹部 -->
            <rect x="80" y="155" width="40" height="50" rx="8" :class="getPartClass('abdomen')" @click="onSvgPartClick('abdomen')" />
            
            <!-- 左臂：左上臂、左前臂、左手 -->
            <g class="arm-group">
              <rect x="55" y="105" width="15" height="45" rx="7" :class="getPartClass('leftUpperArm')" @click="onSvgPartClick('leftUpperArm')" />
              <rect x="50" y="150" width="12" height="40" rx="6" :class="getPartClass('leftForearm')" @click="onSvgPartClick('leftForearm')" />
              <ellipse cx="56" cy="200" rx="8" ry="12" :class="getPartClass('leftHand')" @click="onSvgPartClick('leftHand')" />
            </g>
            
            <!-- 右臂：右上臂、右前臂、右手 -->
            <g class="arm-group">
              <rect x="130" y="105" width="15" height="45" rx="7" :class="getPartClass('rightUpperArm')" @click="onSvgPartClick('rightUpperArm')" />
              <rect x="138" y="150" width="12" height="40" rx="6" :class="getPartClass('rightForearm')" @click="onSvgPartClick('rightForearm')" />
              <ellipse cx="144" cy="200" rx="8" ry="12" :class="getPartClass('rightHand')" @click="onSvgPartClick('rightHand')" />
            </g>
            
            <!-- 左腿：左大腿、左小腿、左脚 -->
            <g class="leg-group">
              <rect x="78" y="205" width="15" height="60" rx="7" :class="getPartClass('leftThigh')" @click="onSvgPartClick('leftThigh')" />
              <rect x="77" y="265" width="13" height="55" rx="6" :class="getPartClass('leftCalf')" @click="onSvgPartClick('leftCalf')" />
              <ellipse cx="82" cy="330" rx="12" ry="8" :class="getPartClass('leftFoot')" @click="onSvgPartClick('leftFoot')" />
            </g>
            
            <!-- 右腿：右大腿、右小腿、右脚 -->
            <g class="leg-group">
              <rect x="107" y="205" width="15" height="60" rx="7" :class="getPartClass('rightThigh')" @click="onSvgPartClick('rightThigh')" />
              <rect x="109" y="265" width="13" height="55" rx="6" :class="getPartClass('rightCalf')" @click="onSvgPartClick('rightCalf')" />
              <ellipse cx="115" cy="330" rx="12" ry="8" :class="getPartClass('rightFoot')" @click="onSvgPartClick('rightFoot')" />
            </g>
          </svg>
        </div>
      </div>
    </div>

    <!-- 功能按钮区：伤情输入 + 语音录入 -->
    <div style="display: flex; gap: 10px; margin: 10px 0; justify-content: center;">
      <div class="asr-open-row">
        <button class="asr-open-btn" @click="InjuryInput">伤情输入</button>
      </div>
      <div class="asr-open-row">
        <button class="asr-open-btn" @click="openAsrModal">语音录入（识别）</button>
      </div>
    </div>

    <!-- 语音录入识别弹窗 - 挂载到body避免样式裁切 -->
    <Teleport to="body">
      <div v-if="showAsrModal" class="modal-overlay" @click.self="closeAsrModal">
        <div class="modal-content asr-modal">
          <div class="modal-header">
            <h3 class="modal-title">语音录入识别</h3>
            <button class="modal-close" @click="closeAsrModal">×</button>
          </div>
          <div class="modal-body">
            <div class="asr-toolbar">
              <label class="asr-label">语言：</label>
              <select v-model="asrLang" class="asr-select" title="语言">
                <option value="zh-CN">中文 (zh-CN)</option>
                <option value="en-US">English (en-US)</option>
              </select>
              <button class="asr-btn primary" :disabled="isRecording" @click="startRecording">开始录音</button>
              <button class="asr-btn" :disabled="!isRecording" @click="stopRecording">停止</button>
              <button class="asr-btn" :disabled="!audioBlob" @click="playPreview">试听</button>
              <button class="asr-btn danger" :disabled="!audioBlob || isRecording" @click="clearAudio">清空</button>
              <button class="asr-btn success" :disabled="!audioBlob || isRecording || isSubmitting" @click="submitASR">
                {{ isSubmitting ? '提交中...' : '提交识别' }}
              </button>
            </div>
            <!-- 录音文件信息 -->
            <div class="asr-info" v-if="audioBlob">
              <span>时长：{{ prettyDuration }}</span>
              <span>大小：{{ prettySize }}</span>
              <span>格式：{{ audioMime }}</span>
            </div>
            <!-- 语音识别结果 -->
            <div class="asr-result" v-if="asrText">
              <label>识别结果：</label>
              <textarea :value="asrText" readonly></textarea>
            </div>
            <!-- 识别结果查询建议按钮 -->
            <button class="query-btn" @click="searchInjury_input(asrText.trim())" :disabled="!asrText.trim()">
              查询处理建议
            </button>
            <div class="result-section" v-if="showResult">
              <label class="result-label">处理建议：</label>
              <div class="result-content">
                <div v-if="isLoading" class="loading">加载中...</div>
                <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
                <ul v-if="resultData && !errorMsg">
                  <li v-for="(item, index) in resultData" :key="index">{{ item }}</li>
                </ul>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="modal-confirm" @click="closeAsrModal">完成</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 手动伤情输入弹窗 - 挂载到body避免样式裁切 -->
    <Teleport to="body">
      <div v-if="showInjuryModal" class="modal-overlay" @click.self="closeInjuryModal">
        <div class="modal-content injury-modal">
          <div class="modal-header">
            <h3 class="modal-title">伤情信息处理</h3>
            <button class="modal-close" @click="closeInjuryModal">×</button>
          </div>
          <div class="modal-body">
            <!-- 手动输入区域 -->
            <div class="input-section">
              <label class="input-label">请输入伤情部位：</label>
              <input 
                type="text" 
                class="injury-input" 
                v-model="injuryPart"
                placeholder="例如：头部、左前臂、胸部..."
              >
              <button class="query-btn" @click="searchInjury_input(injuryPart.trim())" :disabled="!injuryPart.trim()">
                查询处理建议
              </button>
            </div>
            <div class="result-section" v-if="showResult">
              <label class="result-label">处理建议：</label>
              <div class="result-content">
                <div v-if="isLoading" class="loading">加载中...</div>
                <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
                <ul v-if="resultData && !errorMsg">
                  <li v-for="(item, index) in resultData" :key="index">{{ item }}</li>
                </ul>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="modal-btn cancel" @click="closeInjuryModal">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 受伤详情弹窗 - 分页展示 伤情细分+处置建议 无滚动条 -->
    <div v-if="showDetail" class="injury-detail-popup" @click.self="closeDetail">
      <div class="popup-content" role="dialog" aria-modal="true">
        <div class="popup-header">
          <h5>{{ selectedPartName }} - {{ step === 1 ? '选择细分伤情' : '紧急处置建议' }}</h5>
          <button class="icon-close" aria-label="关闭" @click="closeDetail">×</button>
        </div>
        <div class="popup-body no-scroll">
          <!-- 步骤1：选择细分伤情类型（分页） -->
          <template v-if="step === 1">
            <div v-if="hasDetailsForSelected" class="injury-detail-grid">
              <label class="detail-option" v-for="key in currentDetailPageKeys" :key="key">
                <input type="radio" :value="key" v-model="selectedInjury" @change="handleSelectInjury" />
                <div class="detail-title">{{ injuryDetails[selectedPart][key].name }}</div>
                <div class="detail-desc" v-if="injuryDetails[selectedPart][key].desc">
                  {{ injuryDetails[selectedPart][key].desc }}
                </div>
              </label>
            </div>
            <div v-else class="empty-detail">
              暂无该部位的细分选项，可在 <code>injuryDetails</code> 中添加。
            </div>
            <div class="pager" v-if="detailTotalPages > 1">
              <button :disabled="detailPage===1" @click="detailPage--">上一页</button>
              <span>{{ detailPage }} / {{ detailTotalPages }}</span>
              <button :disabled="detailPage===detailTotalPages" @click="detailPage++">下一页</button>
            </div>
            <div class="footer-ops">
              <button class="primary" :disabled="!selectedInjury" @click="goStep(2)">查看处置建议</button>
              <button class="ghost" @click="closeDetail">取消</button>
            </div>
          </template>

          <template v-else>
            <div class="advice-block">
              <h6>紧急处置建议</h6>
              <div v-if="injuryQueryLoading" class="loading">加载中...</div>
              <div v-else-if="injuryQueryError" class="error">{{ injuryQueryError }}</div>
              <ul v-else class="advice-list">
                <li v-for="(line, i) in currentAdvicePageLines" :key="i">{{ line }}</li>
              </ul>
            </div>
            <div class="pager" v-if="!injuryQueryLoading && !injuryQueryError && adviceTotalPages > 1">
              <button :disabled="advicePage===1" @click="advicePage--">上一页</button>
              <span>{{ advicePage }} / {{ adviceTotalPages }}</span>
              <button :disabled="advicePage===adviceTotalPages" @click="advicePage++">下一页</button>
            </div>
            <div class="footer-ops">
              <button class="ghost" @click="toggleSpeakAdvice" :aria-pressed="isSpeaking">
                {{ isSpeaking ? '停止播放' : '播放' }}
              </button>
              <button class="primary" @click="applyAndClose">确认并关闭</button>
              <button class="ghost" @click="goStep(1)">返回修改</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// 判断是否为移动端设备
const isMobile = () => (typeof window !== 'undefined' ? window.innerWidth <= 768 : false);
// 引入 axios 请求库
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';
const MATCH_API_BASE = import.meta.env.VITE_MATCH_API_BASE || '/match-api';

export default {
  name: 'HumanBodyModel',
  data() {
    return {
      injuryType: '',          // 受伤类型
      injuredParts: [],        // 已选中的受伤部位集合
      severity: '',            // 伤情严重程度
      injuryQueryLoading: false,
      injuryQueryError: '',    // 细分伤情查询错误信息
      injuryQueryResult: null, // 细分伤情查询结果
      showDetail: false,       // 受伤详情弹窗显隐
      selectedPart: '',        // 当前选中的部位标识
      selectedPartName: '',    // 当前选中的部位中文名称
      selectedInjury: '',      // 当前选中的细分伤情标识
      llmdata: null,           // 大模型返回的处置建议数据
      
      // 手动伤情输入弹窗相关
      showInjuryModal: false,  // 手动输入弹窗显隐
      injuryPart: '',          // 手动输入的伤情部位内容
      showResult: false,       // 是否展示查询结果区域
      isLoading: false,
      errorMsg: '',            // 手动查询错误信息
      resultData: null,
      agenticMeta: null,

      // 语音录入弹窗相关
      showAsrModal: false,     // 语音录入弹窗显隐
      allowedAsrMimeTypes: ['audio/webm', 'audio/ogg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'video/mp4'],
      maxAsrFileSize: 10 * 1024 * 1024,
      asrLang: 'zh-CN',        // 语音识别语言类型
      isRecording: false,      // 是否正在录音
      isSubmitting: false,     // 是否正在提交语音识别
      mediaStream: null,       // 录音媒体流
      mediaRecorder: null,     // 录音实例
      audioChunks: [],         // 录音数据片段
      audioBlob: null,         // 录音生成的blob文件
      audioUrl: '',            // 录音文件预览地址
      audioMime: '',           // 录音文件格式
      audioDurationSec: 0,     // 录音时长（秒）
      asrText: '',             // 语音识别结果文本

      // 分步+分页配置
      step: 1,
      detailPage: 1,           // 伤情分页当前页码
      advicePage: 1,           // 建议分页当前页码
      DETAIL_PAGE_SIZE_DESKTOP: 8, // 桌面端伤情每页条数
      DETAIL_PAGE_SIZE_MOBILE: 6,  // 移动端伤情每页条数
      ADVICE_PAGE_SIZE_DESKTOP: 6,
      ADVICE_PAGE_SIZE_MOBILE: 5,

      // 语音播放相关
      isSpeaking: false,       // 是否正在播放语音建议
      _speechVoice: null,      // 语音播报的语音包
      _speechUtter: null,      // 语音播报实例

      // 人体部位字典：key=标识，value=中文名称
      bodyParts: {
        head: '头部', neck: '颈部', chest: '胸部', abdomen: '腹部',
        leftUpperArm: '左上臂', leftForearm: '左前臂', leftHand: '左手',
        rightUpperArm: '右上臂', rightForearm: '右前臂', rightHand: '右手',
        leftThigh: '左大腿', leftCalf: '左小腿', leftFoot: '左脚',
        rightThigh: '右大腿', rightCalf: '右小腿', rightFoot: '右脚'
      },

      // 各部位对应的细分伤情字典（名称与知识库保持一致）
      injuryDetails: {
        head: {
          scalpLaceration: { name: '头皮裂伤' },
          comminutedSkullFracture: { name: '粉碎性颅骨骨折' },
          mildBrainInjury: { name: '轻型脑损伤' },
          cerebralContusion: { name: '脑挫裂伤' }
        },
        neck: {
          neckInjury: { name: '颈部损伤' },
          maxillofacialInjury: { name: '颌面部伤' }
        },
        chest: {
          chestImpactInjury: { name: '胸部撞击伤' },
          flailChest: { name: '胸部压伤(连枷胸)' },
          thoracoabdominalInjury: { name: '胸腹联合伤' }
        },
        abdomen: {
          abdominalWallInjury: { name: '腹壁损伤' },
          stomachPenetrationInjury: { name: '胃穿透伤' },
          kidneyBluntInjury: { name: '肾钝性伤' }
        },
        leftUpperArm: {
          upperArmExplosionInjury: { name: '上臂爆炸伤' },
          axillaryArteryInjury: { name: '腋动脉损伤' }
        },
        rightUpperArm: {
          upperArmExplosionInjury: { name: '上臂爆炸伤' },
          axillaryArteryInjury: { name: '腋动脉损伤' }
        },
        leftForearm: {
          forearmFractureWithCompartmentSyndrome: { name: '前臂撞击伤(尺桡骨骨折)并发骨筋膜室综合征' },
          radialArteryInjury: { name: '桡动脉损伤' }
        },
        rightForearm: {
          forearmFractureWithCompartmentSyndrome: { name: '前臂撞击伤(尺桡骨骨折)并发骨筋膜室综合征' },
          radialArteryInjury: { name: '桡动脉损伤' }
        },
        leftHand: { thumbAmputation: { name: '锐器伤致拇指离断' }, handExplosionInjury: { name: '手部炸伤' } },
        rightHand: { thumbAmputation: { name: '锐器伤致拇指离断' }, handExplosionInjury: { name: '手部炸伤' } },
        leftThigh: {
          femoralArteryInjury: { name: '股动脉损伤' },
          thighBlindTunnelInjury: { name: '大腿盲管伤' }
        },
        rightThigh: {
          femoralArteryInjury: { name: '股动脉损伤' },
          thighBlindTunnelInjury: { name: '大腿盲管伤' }
        },
        leftCalf: {
          crushSyndrome: { name: '挤压伤综合征(下肢挤压伤)' },
          lowerLimbSkinAvulsion: { name: '下肢皮肤撕脱伤' },
          poplitealArteryInjury: { name: '腘动脉损伤' }
        },
        rightCalf: {
          crushSyndrome: { name: '挤压伤综合征(下肢挤压伤)' },
          lowerLimbSkinAvulsion: { name: '下肢皮肤撕脱伤' },
          poplitealArteryInjury: { name: '腘动脉损伤' }
        },
        leftFoot: { lowerLimbSkinAvulsion: { name: '下肢皮肤撕脱伤' } },
        rightFoot: { lowerLimbSkinAvulsion: { name: '下肢皮肤撕脱伤' } }
      }
    };
  },
  computed: {
    // 获取当前选中部位的所有伤情key
    detailKeys() {
      return Object.keys(this.injuryDetails[this.selectedPart] || {});
    },
    // 根据设备类型返回伤情每页条数
    detailPageSize() {
      return isMobile() ? this.DETAIL_PAGE_SIZE_MOBILE : this.DETAIL_PAGE_SIZE_DESKTOP;
    },
    detailTotalPages() {
      return Math.max(1, Math.ceil(this.detailKeys.length / this.detailPageSize));
    },
    // 当前页展示的伤情key集合
    currentDetailPageKeys() {
      const start = (this.detailPage - 1) * this.detailPageSize;
      return this.detailKeys.slice(start, start + this.detailPageSize);
    },

    currentAdviceLinesAll() {
      if (!this.selectedPart || !this.selectedInjury) return [];
      const act = this.injuryDetails[this.selectedPart][this.selectedInjury]?.emergencyAction || [];
      return Array.isArray(act) ? act : [act];
    },
    // 根据设备类型返回建议每页条数
    advicePageSize() {
      return isMobile() ? this.ADVICE_PAGE_SIZE_MOBILE : this.ADVICE_PAGE_SIZE_DESKTOP;
    },
    adviceTotalPages() {
      return Math.max(1, Math.ceil(this.currentAdviceLinesAll.length / this.advicePageSize));
    },
    // 当前页展示的建议集合
    currentAdvicePageLines() {
      const start = (this.advicePage - 1) * this.advicePageSize;
      return this.currentAdviceLinesAll.slice(start, start + this.advicePageSize);
    },

    hasDetailsForSelected() {
      return this.selectedPart && this.injuryDetails[this.selectedPart];
    },

    // 拼接当前页建议为语音播报文本
    currentAdviceText() {
      const lines = this.currentAdvicePageLines || [];
      return lines.join('；') + (lines.length ? '。' : '');
    },

    prettyDuration() {
      const s = Math.round(this.audioDurationSec || 0);
      const m = Math.floor(s / 60).toString().padStart(2, '0');
      const r = (s % 60).toString().padStart(2, '0');
      return `${m}:${r}`;
    },
    prettySize() {
      if (!this.audioBlob) return '0B';
      const b = this.audioBlob.size;
      if (b < 1024) return `${b}B`;
      if (b < 1024 * 1024) return `${(b/1024).toFixed(1)}KB`;
      return `${(b/1024/1024).toFixed(1)}MB`;
    }
  },
  watch: {
    injuryType() { this.$emit('injury-type-change', this.injuryType); },
    severity() { this.$emit('severity-change', this.severity); },
    // 详情弹窗显隐时，控制页面是否滚动
    showDetail(val) {
      if (typeof window !== 'undefined') document.body.style.overflow = val ? 'hidden' : '';
    },
    // 建议分页切换时，停止语音播放
    advicePage() { this.stopSpeech(); },
    // 步骤切换时，停止语音播放+向父组件同步数据
    step(n) {
      if (n !== 2) this.stopSpeech();
      this.emitChange();
    }
  },
  mounted() {
    // 初始化语音播报包
    this.initVoices();
    if (typeof window !== 'undefined') {
      window.speechSynthesis?.addEventListener?.('voiceschanged', this.initVoices);
    }
  },
  beforeDestroy() {
    this.stopSpeech();
    if (typeof window !== 'undefined') {
      window.speechSynthesis?.removeEventListener?.('voiceschanged', this.initVoices);
      document.body.style.overflow = '';
    }
  },
  methods: {
    // ===== 基础交互方法 =====
    // 左侧勾选框变更事件
    onPartCheckboxChange(part, e) {
      const checked = e.target.checked;
      if (checked) {
        this.openDetailFor(part); // 勾选则打开详情弹窗
      } else {
        this.handleDeselectEffects(part);
      }
      this.$nextTick(this.emitChange);
    },
    // 右侧SVG人体部位点击事件
    onSvgPartClick(part) {
      if (this.injuredParts.includes(part)) {
        this.injuredParts = this.injuredParts.filter(p => p !== part);
        this.handleDeselectEffects(part);
      } else {
        this.injuredParts.push(part);
        this.openDetailFor(part);
      }
      this.$nextTick(this.emitChange);
    },
    // 打开伤情详情弹窗并初始化数据
    openDetailFor(part) {
      this.selectedPart = part;
      this.selectedPartName = this.bodyParts[part] || '';
      this.selectedInjury = '';
      this.step = 1;
      this.detailPage = 1;
      this.advicePage = 1;
      this.showDetail = true;
    },
    // 选中细分伤情时，向父组件同步数据
    handleSelectInjury() {
      this.emitChange();
    },
    // 切换详情弹窗步骤
    goStep(step) {
      console.log('进入goStep方法，目标步骤：', step);
      this.step = step;
      if (step === 2) {
        this.advicePage = 1;
        console.log('开始调用queryInjuryBySelected');
        this.queryInjuryBySelected(); // 切换到建议页时，查询处置建议
      }
      this.$nextTick(() => this.emitChange());
    },
    // 确认建议并关闭弹窗
    applyAndClose() {
      if (!this.injuryQueryLoading) {
        this.emitChange();
        this.closeDetail();
      } else {
        this.$emit('toast', { type: 'warning', message: '正在查询处置建议，请稍候' });
      }
    },
    clearSelectedInjury() {
      this.selectedInjury = '';
      this.emitChange();
    },
    // 关闭伤情详情弹窗
    closeDetail() {
      this.showDetail = false;
    },
    getPartClass(part) {
      return { 'body-part': true, 'injured': this.injuredParts.includes(part) };
    },
    handleDeselectEffects(part) {
      if (this.selectedPart === part) {
        this.selectedInjury = '';
        this.showDetail = false;
      }
    },
    emitChange() {
      this.$emit('injured-parts-change', {
        parts: this.injuredParts.slice(),
        type: this.injuryType,
        severity: this.severity,
        selectedPart: this.selectedPart,
        selectedInjury: this.selectedInjury,
        advice: this.currentAdviceLinesAll,
        selectedPartName: this.selectedPartName,
        selectedInjuryName: (this.injuryDetails[this.selectedPart]?.[this.selectedInjury]?.name) || ''
      });
    },

    // ===== 语音播报相关方法 =====
    // 初始化语音播报包
    initVoices() {
      if (typeof window === 'undefined' || !window.speechSynthesis) return;
      const voices = window.speechSynthesis.getVoices?.() || [];
      this._speechVoice = voices.find(v => /zh-CN/i.test(v.lang)) || voices.find(v => /zh/i.test(v.lang)) || voices[0] || null;
    },
    // 切换播放/暂停语音建议
    toggleSpeakAdvice() {
      this.isSpeaking ? this.stopSpeech() : this.speakCurrentAdvice();
    },
    // 播放当前页的处置建议语音
    speakCurrentAdvice() {
      if (typeof window === 'undefined' || !window.speechSynthesis) {
        this.$emit('toast', { type: 'warning', message: '当前环境不支持语音播放' });
        return;
      }
      const text = (this.currentAdviceText || '').trim();
      if (!text) {
        this.$emit('toast', { type: 'info', message: '本页暂无可读建议' });
        return;
      }
      this.stopSpeech();
      const utter = new SpeechSynthesisUtterance(text);
      if (this._speechVoice) utter.voice = this._speechVoice;
      utter.lang = this._speechVoice?.lang || 'zh-CN';
      utter.rate = 1.0; utter.pitch = 1.0; utter.volume = 1.0;
      utter.onstart = () => { this.isSpeaking = true; };
      utter.onend = () => { this.isSpeaking = false; this._speechUtter = null; };
      utter.onerror = () => { this.isSpeaking = false; this._speechUtter = null; };
      this._speechUtter = utter;
      window.speechSynthesis.speak(utter);
    },
    // 停止语音播放
    stopSpeech() {
      if (typeof window === 'undefined' || !window.speechSynthesis) return;
      try {
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
          window.speechSynthesis.cancel();
        }
      } finally {
        this.isSpeaking = false;
        this._speechUtter = null;
      }
    },

    // ===== 语音录入弹窗相关方法 =====
    // 打开语音录入弹窗
    openAsrModal() {
      this.showAsrModal = true;
      if (typeof window !== 'undefined') document.body.style.overflow = 'hidden';
    },
    // 关闭语音录入弹窗
    closeAsrModal() {
      this.stopRecording();
      this.cleanupStream();
      this.showAsrModal = false;
      if (typeof window !== 'undefined') document.body.style.overflow = '';
    },
    async startRecording() {
      try {
        this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeCandidates = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/webm','audio/mp4','audio/wav'];
        const mimeType = mimeCandidates.find(t => MediaRecorder.isTypeSupported?.(t)) || '';
        this.audioMime = mimeType || 'audio/webm';
        this.mediaRecorder = new MediaRecorder(this.mediaStream, mimeType ? { mimeType } : undefined);
        this.audioChunks = [];
        this.audioBlob = null;
        this.audioUrl = '';
        this.asrText = '';
        this.isRecording = true;
        let startTs = Date.now();
        this.mediaRecorder.ondataavailable = e => { if (e.data?.size) this.audioChunks.push(e.data); };
        this.mediaRecorder.onstop = () => {
          this.audioBlob = new Blob(this.audioChunks, { type: this.audioMime });
          this.audioUrl = URL.createObjectURL(this.audioBlob);
          this.audioDurationSec = Math.max(1, Math.round((Date.now() - startTs)/1000));
          this.cleanupStream();
          this.isRecording = false;
        };
        this.mediaRecorder.start(250);
      } catch (err) {
        console.error('麦克风不可用', err);
        this.$emit('toast', { type: 'error', message: '无法访问麦克风，请检查权限设置' });
      }
    },
    // 停止录音
    stopRecording() {
      try {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
          this.mediaRecorder.stop();
        }
      } catch (e) {}
    },
    // 试听录音文件
    playPreview() {
      if (!this.audioUrl) return;
      const a = new Audio(this.audioUrl);
      a.play();
    },
    // 清空录音相关数据
    clearAudio() {
      this.stopRecording();
      this.cleanupStream();
      if (this.audioUrl) URL.revokeObjectURL(this.audioUrl);
      this.audioChunks = [];
      this.audioBlob = null;
      this.audioUrl = '';
      this.audioDurationSec = 0;
      this.asrText = '';
    },
    // 清理录音媒体流
    cleanupStream() {
      try { this.mediaStream?.getTracks?.().forEach(t => t.stop()); } catch {}
      this.mediaStream = null;
    },
    // 提交语音文件进行识别
    async submitASR() {
      if (!this.audioBlob) return;
      if (!this.allowedAsrMimeTypes.includes(this.audioMime)) {
        this.$emit('toast', { type: 'error', message: '仅支持 wav、webm、ogg、mp4、m4a 音频格式' });
        return;
      }
      if (this.audioBlob.size > this.maxAsrFileSize) {
        this.$emit('toast', { type: 'error', message: '音频文件不能超过 10MB' });
        return;
      }
      this.isSubmitting = true;
      try {
        const formData = new FormData();
        const ext = this.audioMime.includes('ogg') ? 'ogg' : this.audioMime.includes('mp4') ? 'm4a' : this.audioMime.includes('wav') ? 'wav' : 'webm';
        formData.append('audio', this.audioBlob, `record.${ext}`);
        formData.append('lang', this.asrLang);
        const token = localStorage.getItem('authToken');
        const resp = await fetch(`${API_BASE}/asr`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData
        });
        if (!resp.ok) throw new Error(`ASR HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.code !== 0) throw new Error(data.message || '识别失败');
        this.asrText = data.text || '';
        this.$emit('asr-result', { text: this.asrText, lang: this.asrLang });
      } catch (e) {
        console.error(e);
        this.$emit('toast', { type: 'error', message: '识别失败，请稍后再试' });
      } finally {
        this.isSubmitting = false;
      }
    },

    // ===== 手动伤情输入弹窗相关方法 =====
    // 打开手动输入弹窗
    InjuryInput() {
      this.showInjuryModal = true;
      this.injuryPart = '';
      this.showResult = false;
      this.resultData = null;
      this.errorMsg = '';
      document.body.style.overflow = 'hidden';
    },
    // 关闭手动输入弹窗
    closeInjuryModal() {
      this.showInjuryModal = false;
      this.resultData = null;
      this.showResult = false;
      document.body.style.overflow = '';
    },

    // ===== 核心请求方法 =====
    async queryInjuryBySelected() {
      console.log('查询的伤情名称：', this.injuryDetails[this.selectedPart]?.[this.selectedInjury]?.name);
      if (!this.selectedPart || !this.selectedInjury) {
        return;
      }
      const injuryName = this.injuryDetails[this.selectedPart][this.selectedInjury].name;
      this.injuryQueryLoading = true;
      this.injuryQueryError = '';
      this.injuryQueryResult = null;
      try {
        const response = await axios.post(`${API_BASE}/treatment`, { injury: injuryName }, { headers: { 'Content-Type': 'application/json' } });
        const resData = response.data;
        if (resData.code === 0) {
          const treatmentData = resData.data || {};
          this.llmdata = await this.searchInjury(injuryName);
          const rescueAdvice = this.llmdata.rescue_advice;
          this.injuryQueryResult = rescueAdvice;
          this.injuryDetails[this.selectedPart][this.selectedInjury].emergencyAction = this.injuryQueryResult;
          if (this.injuryQueryResult.length === 0) {
            this.injuryQueryError = '未查询到该伤情的现场急救处置建议';
          }
        } else {
          this.injuryQueryError = resData.msg || '查询失败';
        }
      } catch (error) {
        console.error('细分伤情查询失败', error);
        console.error('错误详情', { message: error.message, response: error.response?.data, status: error.response?.status });
        this.injuryQueryError = '网络错误，请稍后重试';
      } finally {
        this.injuryQueryLoading = false;
      }
    },
    // 调用大模型接口，获取格式化的处置建议
    async searchInjury(queryText) {
      if (!queryText.trim()) {
        this.error = '请输入伤情描述';
        return;
      }
      this.loading = true;
      this.error = null;
      this.result = null;
      try {
        const response = await axios.post(`${MATCH_API_BASE}/agentic`, {
          text: queryText,
          mode: 'llm'
        });
        this.result = this.normalizeAgenticResult(response.data);
        this.error = null;
        return this.result;
      } catch (err) {
        this.error = err.response?.data?.error || '请求失败，请检查后端是否运行';
        console.error('API请求错误:', err);
      } finally {
        this.loading = false;
      }
    },
    // Adapt the structured /agentic response to the legacy view model.
    normalizeAgenticResult(data) {
      const rescueAdvice = Array.isArray(data?.steps)
        ? data.steps
          .map((step) => typeof step === 'string' ? step : step?.action)
          .filter(Boolean)
        : [];
      return { ...data, rescue_advice: rescueAdvice };
    },
    formatAgenticError(data) {
      const missing = Array.isArray(data?.missing_information)
        ? data.missing_information.filter(Boolean)
        : [];
      if (missing.length) {
        return `信息不足，请补充：${missing.join('、')}`;
      }
      if (data?.final_decision === 'needs_review') {
        return '候选伤情存在冲突，请由专业人员复核。';
      }
      return data?.error || '未能生成可靠的处置建议，请补充伤情信息后重试。';
    },
    // 手动输入/语音识别结果 统一查询处置建议
    async searchInjury_input(queryText) {
      if (!queryText.trim()) {
        this.error = '请输入伤情描述';
        return;
      }
      this.isLoading = true;
      this.error = null;
      this.result = null;
      this.errorMsg = '';
      this.resultData = null;
      this.showResult = true;
      try {
        const response = await axios.post(`${MATCH_API_BASE}/agentic`, {
          text: queryText,
          mode: 'llm'
        });
        this.isLoading = false;
        this.resultData = this.normalizeAgenticResult(response.data).rescue_advice;
        this.agenticMeta = this.normalizeAgenticResult(response.data);
        console.log("键盘输入的大模型结果（已修正）：", this.resultData);
      } catch (err) {
        this.errorMsg = this.formatAgenticError(err.response?.data);
        this.error = this.errorMsg;
        console.error('API请求错误:', err);
      } finally {
        this.loading = false;
      }
    },
    // 查看建议（备用方法）
    viewAdvice() {
      if (!this.currentInjury) {
        this.$message.warning('请先选择具体伤情');
        return;
      }
    }
  }
};
</script>

<style scoped>
/* 组件外层容器样式 */
.injury-assessment {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 12px;
  padding: 1rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
}
.injury-assessment h4 {
  color: #4fc3f7; margin-bottom: 1.5rem; font-size: 1.15rem; font-weight: 600;
  text-shadow: 0 0 10px rgba(79,195,247,.5); position: relative;
}
.injury-assessment h4::after {
  content: ''; position: absolute; bottom: -6px; left: 0; width: 40px; height: 2px;
  background: linear-gradient(90deg, #4fc3f7, #29b6f6); border-radius: 1px;
}
.injury-content { display: grid; grid-template-columns: 1fr 190px; gap: 1rem; align-items: start; }
.injury-options { display: flex; flex-direction: column; gap: 2rem; }
.injury-parts-section { background: rgba(255,255,255,.03); border-radius: 8px; padding: 1rem; }
.injury-options h5 { color: #4fc3f7; margin-bottom: .7rem; font-size: 1rem; font-weight: 500; }
.parts-checkboxes { display: grid; grid-template-columns: 1fr 1fr; row-gap: .2rem; column-gap: 1.5rem; }
.injury-options label { display: flex; align-items: center; gap: 1rem; color: rgba(255,255,255,.9); cursor: pointer; font-size: .68rem; transition: color .3s ease; }
.injury-options label:hover { color: #4fc3f7; }
.injury-options input[type="checkbox"] { width: 16px; height: 16px; accent-color: #4fc3f7; cursor: pointer; }

/* 右侧人体模型样式 */
.body-model { display: block; flex-direction: column; align-items: center; gap: 1rem; }
.model-wrapper { background: rgba(255,255,255,.08); border: 1px solid rgba(79,195,247,.3); border-radius: 12px; padding: 0 1.5rem; height: 245px; box-shadow: 0 4px 20px rgba(0,0,0,.2); }
.body-svg { width: 100%; height: auto; max-width: 200px; display: block; }
.body-part { fill: rgba(79, 195, 247, 0.6); stroke: rgba(79, 195, 247, 0.8); stroke-width: 1.5; cursor: pointer; transition: all .3s ease; }
.body-part:hover { fill: rgba(79,195,247,.8); stroke: #4fc3f7; stroke-width: 2; filter: drop-shadow(0 0 8px rgba(79,195,247,.6)); }
.body-part.injured { fill: #ff6b6b; stroke: #ff4757; stroke-width: 2.5; animation: injuredPulse 1.5s infinite; filter: drop-shadow(0 0 10px rgba(255,107,107,.8)); }
@keyframes injuredPulse { 0%,100%{opacity:1;} 50%{opacity:.7;} }

/* 伤情详情弹窗样式 */
.injury-detail-popup {
  position: fixed; inset: 0; background: rgba(5, 14, 22, 0.65);
  display: flex; justify-content: center; align-items: center; z-index: 2000;
}
.popup-content {
  background: rgba(12, 22, 32, 0.96); color: #eaf6ff;
  border: 1px solid rgba(79,195,247,.35);
  border-radius: 12px;
  width: 92%; max-width: 640px;
  max-height: 90vh; overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,.45);
}
.popup-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: .75rem 1rem .6rem; background: rgba(12, 22, 32, .98);
  border-bottom: 1px solid rgba(79,195,247,.25);
}
.popup-header h5 { margin: 0; color: #4fc3f7; font-size: 1rem; }
.icon-close { background: transparent; color: #9fdcff; border: none; font-size: 1.5rem; line-height: 1; cursor: pointer; }
.icon-close:hover { color: #c7ecff; }
.popup-body.no-scroll { padding: .9rem 1rem 1.1rem; overflow: hidden; }
.injury-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .6rem; margin-bottom: .8rem; }
.detail-option {
  background: rgba(255,255,255,.04); border: 1px solid rgba(79,195,247,.25);
  border-radius: 10px; padding: .6rem .7rem;
  display: grid; grid-template-columns: 16px 1fr; column-gap: .6rem; align-items: start;
}
.detail-option input[type="radio"] { margin-top: .2rem; accent-color: #4fc3f7; }
.detail-title { font-size: .9rem; color: #e6f7ff; margin-bottom: .15rem; }
.detail-desc { grid-column: 2 / -1; font-size: .76rem; color: #bfe8ff; opacity: .9; }
.advice-block h6 { margin: 0 0 .5rem 0; color: #9fe0ff; font-weight: 600; font-size: .92rem; }
.advice-list { margin: 0 0 .6rem 1rem; padding: 0; }
.advice-list li { margin: .2rem 0; line-height: 1.35; font-size: .88rem; }
.pager { display: flex; justify-content: center; align-items: center; gap: .6rem; margin: .2rem 0 .8rem; }
.pager button {
  background: transparent; color: #c7ecff; border: 1px solid rgba(159,220,255,.5);
  padding: .35rem .7rem; border-radius: 8px; cursor: pointer;
}
.pager button:disabled { opacity: .45; cursor: not-allowed; }
.pager span { min-width: 64px; text-align: center; font-size: .9rem; color: #bfe8ff; }
.footer-ops { display: flex; justify-content: center; gap: .6rem; }
button.primary {
  background-color: #4fc3f7; color: #0b1a26; border: none; padding: .45rem .8rem;
  cursor: pointer; border-radius: 8px; font-weight: 600;
}
button.primary:hover { background-color: #5fd0ff; }
button.ghost {
  background: transparent; color: #c7ecff; border: 1px solid rgba(159,220,255,.5);
  padding: .42rem .8rem; border-radius: 8px; cursor: pointer;
}
button.ghost:hover { background: rgba(159,220,255,.08); }

/* 功能按钮样式 */
.asr-open-row{ margin-top:.6rem; display:flex; justify-content:flex-end; }
.asr-open-btn{
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: none; color: #0b1a26; font-weight: 800;
  padding: .5rem .9rem; border-radius: 10px; cursor: pointer;
  transition: transform .2s ease, box-shadow .2s ease;
}
.asr-open-btn:hover{ transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79,195,247,.35); }

/* 通用弹窗遮罩样式 */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; z-index: 3000;
}

/* 语音录入弹窗样式 */
.modal-content.asr-modal {
  width: min(820px, 92vw);
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
.modal-body { padding: .9rem 1rem; overflow: auto; }
.modal-footer {
  padding: .75rem 1rem; border-top: 1px solid rgba(79,195,247,.28);
  display: flex; justify-content: flex-end; gap: .5rem;
}
.modal-confirm {
  background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
  border: 1px solid rgba(79,195,247,.6);
  color: #0b1a26; padding: .5rem 1rem; border-radius: 8px; font-weight: 800; cursor: pointer;
}
.asr-toolbar{ display:flex; flex-wrap:wrap; align-items:center; gap:.6rem; }
.asr-label{ color:#b3e5fc; }
.asr-select{
  background: rgba(255,255,255,.06);
  color:#eaf6ff;
  border:1px solid rgba(79,195,247,.35);
  padding:.38rem .55rem; border-radius:8px;
}
.asr-btn{
  background: transparent; color:#c7ecff;
  border:1px solid rgba(159,220,255,.5);
  padding:.42rem .8rem; border-radius:8px; cursor:pointer;
}
.asr-btn.primary{ background:#4fc3f7; color:#0b1a26; border:none; font-weight:800; }
.asr-btn.success{ border-color:#66bb6a; color:#d1ffd6; }
.asr-btn.danger{ border-color:#ef5350; color:#ffd7d4; }
.asr-btn:disabled{ opacity:.45; cursor:not-allowed; }
.asr-info{ display:flex; gap:1rem; margin-top:.6rem; color:#bfe8ff; font-size:.88rem; }
.asr-result{ margin-top:.8rem; display:flex; flex-direction:column; gap:.4rem; }
.asr-result textarea{
  width:100%; min-height:90px; resize:vertical;
  background: rgba(255,255,255,.05);
  color:#eaf6ff; border:1px solid rgba(79,195,247,.28);
  border-radius:8px; padding:.6rem .7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono","Courier New", monospace;
}

/* 手动输入弹窗样式 */
.injury-modal {
  width: 90%;
  max-width: 600px;
  background: linear-gradient(135deg, rgba(13, 27, 42, 0.95) 0%, rgba(30, 60, 114, 0.92) 100%);
  border: 1px solid rgba(79, 195, 247, 0.5);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  overflow: hidden;
}
.input-section { display: flex; flex-direction: column; gap: 0.8rem; }
.input-label { color: #bfe8ff; font-size: 0.95rem; font-weight: 500; }
.injury-input {
  padding: 0.7rem 0.9rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 8px;
  color: #eaf6ff;
  font-size: 0.95rem;
}
.injury-input:focus { outline: none; border-color: #4fc3f7; box-shadow: 0 0 0 2px rgba(79, 195, 247, 0.2); }
.query-btn {
  align-self: flex-start;
  padding: 0.6rem 1.2rem;
  background: #4fc3f7;
  color: #0b1a26;
	border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.query-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.query-btn:hover:not(:disabled) { background: #5fd0ff; }
.result-section {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  padding-top: 0.8rem;
  border-top: 1px dashed rgba(79, 195, 247, 0.2);
}
.result-label { color: #4fc3f7; font-size: 0.95rem; font-weight: 500; }
.result-content {
  padding: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(79, 195, 247, 0.2);
  border-radius: 8px;
  min-height: 100px;
}
.result-content ul { margin: 0; padding-left: 1.5rem; color: #eaf6ff; }
.result-content li { margin-bottom: 0.5rem; line-height: 1.4; }
.loading { color: #bfe8ff; text-align: center; padding: 1rem 0; }
.error { color: #ff6b6b; text-align: center; padding: 1rem 0; }
.modal-btn.cancel {
  padding: 0.5rem 1.2rem;
  background: transparent;
  color: #bfe8ff;
  border: 1px solid rgba(79, 195, 247, 0.3);
	border-radius: 6px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}
.modal-btn.cancel:hover { background: rgba(79, 195, 247, 0.1); }

/* 加载/错误提示样式 */
.advice-block .loading { color: #4fc3f7; text-align: center; padding: 1rem 0; font-size: 0.9rem; }
.advice-block .error { color: #ff6b6b; text-align: center; padding: 1rem 0; font-size: 0.9rem; }

/* 响应式适配 */
@media (max-width: 768px) {
  .injury-detail-grid { grid-template-columns: 1fr; }
}
</style>


