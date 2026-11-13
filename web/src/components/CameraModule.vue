<template>
  <!-- 患者记录-摄像头拍摄/录制组件 主容器 -->
  <div class="camera-module">
    <h4>患者记录</h4>

    <!-- 【模块1】摄像头权限申请区 - 无权限时展示 -->
    <div v-if="!cameraPermission" class="permission-request">
      <div class="permission-icon">🎥</div>
      <p>请允许访问摄像头以拍摄患者照片或录制视频</p>
      <button class="permission-btn" @click="requestCameraAccess">启用摄像头</button>
    </div>

    <!-- 【模块2】摄像头拍摄/录制主界面 - 有权限+无预览时展示 -->
    <div v-else-if="cameraPermission && !showPreview" class="camera-interface">
      <!-- 摄像头实时预览区域 -->
      <div class="camera-preview">
        <video 
          ref="videoElement" 
          autoplay 
          playsinline 
          muted
          class="camera-video"
        ></video>
        <!-- 当前使用的摄像头类型标识 -->
        <div class="camera-type-indicator">
          <div class="camera-icon">📱</div>
          <span>{{ getCurrentCameraType() }}</span>
        </div>
        <!-- 视频录制中状态标识 -->
        <div v-if="isRecording" class="recording-indicator">
          <div class="recording-dot"></div>
          <span>录制中 {{ recordingTime }}s</span>
        </div>
      </div>

      <!-- 摄像头功能控制按钮组 -->
      <div class="camera-controls">
        <button 
          class="control-btn capture-photo-btn"
          @click="capturePhoto"
          :disabled="isRecording"
        >
          <div class="btn-icon">📷</div>
          <span>拍照</span>
        </button>
        <button 
          class="control-btn record-btn"
          @click="toggleRecording"
          :class="{ recording: isRecording }"
        >
          <div class="btn-icon">{{ isRecording ? '⏹️' : '🎬' }}</div>
          <span>{{ isRecording ? '停止录制' : '录制视频' }}</span>
        </button>
        <button class="control-btn settings-btn" @click="toggleSettings">
          <div class="btn-icon">⚙️</div>
          <span>设置</span>
        </button>
      </div>

      <!-- 摄像头配置面板 - 点击设置后展开 -->
      <div v-if="showSettings" class="settings-panel">
        <div class="setting-item">
          <label>摄像头:</label>
          <select v-model="selectedCamera" @change="switchCamera">
            <option v-for="camera in availableCameras" :key="camera.deviceId" :value="camera.deviceId">
              {{ camera.label || `摄像头 ${camera.deviceId.substr(0, 8)}` }}
            </option>
          </select>
        </div>
        <div class="setting-item">
          <label>分辨率:</label>
          <select v-model="selectedResolution" @change="changeResolution">
            <option value="1920x1080">1920x1080 (Full HD)</option>
            <option value="1280x720">1280x720 (HD)</option>
            <option value="640x480">640x480 (SD)</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 【模块3】拍摄/录制后预览界面 - 有拍摄内容时展示 -->
    <div v-else-if="showPreview" class="preview-interface">
      <!-- 照片预览区域 -->
      <div v-if="capturedImage" class="photo-preview">
        <img :src="capturedImage" alt="拍摄的患者照片" class="preview-image" />
        <div class="preview-info">
          <span class="file-type">照片</span>
          <span class="timestamp">{{ captureTimestamp }}</span>
        </div>
      </div>

      <!-- 视频预览区域 -->
      <div v-if="recordedVideo" class="video-preview">
        <video :src="recordedVideo" controls class="preview-video"></video>
        <div class="preview-info">
          <span class="file-type">视频</span>
          <span class="duration">时长: {{ videoDuration }}s</span>
          <span class="timestamp">{{ recordTimestamp }}</span>
        </div>
      </div>

      <!-- 预览操作按钮组 -->
      <div class="preview-controls">
        <button class="control-btn save-btn" @click="saveMedia">
          <div class="btn-icon">💾</div>
          <span>保存</span>
        </button>
        <button class="control-btn delete-btn" @click="deleteMedia">
          <div class="btn-icon">🗑️</div>
          <span>删除</span>
        </button>
        <button class="control-btn retake-btn" @click="retakeMedia">
          <div class="btn-icon">🔄</div>
          <span>重新拍摄</span>
        </button>
      </div>
    </div>

    <!-- 【模块4】已保存的患者媒体记录列表 - 有保存内容时展示 -->
    <div v-if="savedMediaList.length > 0" class="saved-media">
      <h5>已保存的记录 ({{ savedMediaList.length }})</h5>
      
      <!-- 媒体记录下拉选择器 -->
      <div class="media-selector">
        <label>选择记录:</label>
        <div class="custom-dropdown" @click="toggleDropdown">
          <div class="dropdown-selected">
            {{ savedMediaList[selectedMediaIndex].name }} - {{ savedMediaList[selectedMediaIndex].timestamp }}
          </div>
          <div class="dropdown-arrow">▼</div>
          <div v-if="showDropdown" class="dropdown-options">
            <div 
              v-for="(media, index) in savedMediaList" 
              :key="index"
              class="dropdown-option"
              @click.stop="selectMedia(index)"
              :class="{ selected: index === selectedMediaIndex }"
            >
              {{ media.name }} - {{ media.timestamp }}
            </div>
          </div>
        </div>
      </div>
      
      <!-- 当前选中的媒体记录详情 -->
      <div class="current-media">
        <div class="media-item">
          <div class="media-thumbnail">
            <img v-if="savedMediaList[selectedMediaIndex].type === 'photo'" :src="savedMediaList[selectedMediaIndex].data" alt="照片缩略图" />
            <video v-else :src="savedMediaList[selectedMediaIndex].data" class="video-thumbnail"></video>
            <div class="media-type-badge">{{ savedMediaList[selectedMediaIndex].type === 'photo' ? '📷' : '🎬' }}</div>
          </div>
          <div class="media-info">
            <span class="media-name">{{ savedMediaList[selectedMediaIndex].name }}</span>
            <span class="media-time">{{ savedMediaList[selectedMediaIndex].timestamp }}</span>
            <span v-if="savedMediaList[selectedMediaIndex].type === 'video'" class="media-duration">时长: {{ savedMediaList[selectedMediaIndex].duration }}s</span>
          </div>
          <div class="media-actions">
            <button class="analyze-btn" @click="analyzeMedia">
              <div class="btn-icon">🤖</div>
              <span>AI分析</span>
            </button>
            <button class="delete-media-btn" @click="removeSavedMedia(selectedMediaIndex)">×</button>
          </div>
        </div>
      </div>

      <!-- AI分析结果弹窗 - 点击AI分析后弹出 -->
      <div v-if="showAnalysisModal" class="modal-overlay" @click.self="closeAnalysisModal">
        <div class="modal-content">
          <div class="modal-header">
            <h4>AI 分析结果</h4>
            <button class="modal-close" @click="closeAnalysisModal">×</button>
          </div>
          
          <div class="modal-body">
            <!-- 分析加载中状态 -->
            <div v-if="isAnalyzing" class="analyzing-indicator">
              <div class="spinner"></div>
              <p>AI 正在分析中，请稍候...</p>
            </div>
            
            <!-- 分析失败错误提示 -->
            <div v-if="analysisError" class="ai-error">
              <p>分析失败: {{ analysisError }}</p>
            </div>
            
            <!-- AI分析成功结果展示 -->
            <div v-if="analysisResult && !isAnalyzing" class="ai-result">
              <div class="result-header">
                <h5>救治场景分析报告</h5>
                <span class="analysis-time">{{ analysisTimestamp }}</span>
              </div>
              <div class="result-content">
                <div class="ai-advice" v-html="formatAnalysisResult(analysisResult)"></div>
              </div>
            </div>

            <!-- 视觉证据 → RAG 融合检索 -->
            <div v-if="visualEvidence && !isAnalyzing" class="fusion-section">
              <h6>视觉证据（可用于 RAG 融合检索）</h6>
              <div class="fusion-evidence">
                <span v-if="visualEvidence.location">部位：{{ visualEvidence.location }}</span>
                <span v-if="visualEvidence.severity">严重度：{{ visualEvidence.severity }}</span>
                <span v-if="visualEvidence.injury_candidates && visualEvidence.injury_candidates.length">
                  视觉候选：{{ visualEvidence.injury_candidates.map(c => `${c.name}(${Math.round(c.confidence * 100)}%)`).join('、') }}
                </span>
                <span v-else class="fusion-no-candidate">未识别出明确伤情候选</span>
              </div>
              <button
                class="btn-primary fusion-btn"
                :disabled="fusionLoading || !visualEvidence.injury_candidates || !visualEvidence.injury_candidates.length"
                @click="triggerFusion"
              >
                {{ fusionLoading ? '融合生成中...' : '生成融合处置建议' }}
              </button>
              <div v-if="fusionError" class="ai-error">
                <p>融合检索失败: {{ fusionError }}</p>
              </div>
              <div v-if="fusionResult" class="fusion-result">
                <div v-if="fusionResult.needsReview" class="review-warning">
                  ⚠️ 文本检索与视觉识别结论不一致，建议人工复核后再执行处置
                </div>
                <div class="fusion-meta" v-if="fusionResult.matchedInjury">
                  匹配伤情：{{ fusionResult.matchedInjury }}
                  <span v-if="fusionResult.source">（来源：{{ fusionResult.source }}）</span>
                </div>
                <div v-if="fusionResult.advice && fusionResult.advice.length" class="fusion-steps">
                  <div v-for="(step, idx) in fusionResult.advice" :key="idx" class="fusion-step">{{ step }}</div>
                </div>
              </div>
            </div>
            
            <!-- 原始媒体记录预览 -->
            <div v-if="analysisResult && !isAnalyzing" class="original-media-preview">
              <h6>原始记录</h6>
              <img v-if="savedMediaList[selectedMediaIndex].type === 'photo'" :src="savedMediaList[selectedMediaIndex].data" alt="原始照片" />
              <video v-else :src="savedMediaList[selectedMediaIndex].data" controls class="preview-video"></video>
            </div>
          </div>
          
          <!-- 弹窗底部按钮 -->
          <div class="modal-footer">
            <button class="btn-secondary" @click="closeAnalysisModal">关闭</button>
            <button v-if="analysisResult" class="btn-primary" @click="saveAnalysisResult">保存分析报告</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  // 组件名称
  name: 'CameraModule',
  // 组件数据中心
  data() {
    return {
      // ===== 摄像头基础状态 =====
      cameraPermission: false,  // 摄像头权限是否已获取
      stream: null,             // 媒体流对象
      mediaRecorder: null,      // 视频录制器对象

      // ===== 视频录制状态 =====
      isRecording: false,       // 是否正在录制视频
      recordingTime: 0,         // 录制时长(秒)
      recordingTimer: null,     // 录制计时定时器

      // ===== 设备与配置项 =====
      availableCameras: [],     // 设备上可用的摄像头列表
      selectedCamera: null,     // 当前选中的摄像头ID
      selectedResolution: '1280x720', // 默认分辨率HD
      showSettings: false,      // 是否展示摄像头设置面板

      // ===== 拍摄/录制媒体数据 =====
      capturedImage: null,      // 拍摄的照片base64数据
      recordedVideo: null,      // 录制的视频blob地址
      videoDuration: 0,         // 视频时长
      showPreview: false,       // 是否展示拍摄/录制预览页

      // ===== 时间戳相关 =====
      captureTimestamp: '',     // 照片拍摄时间
      recordTimestamp: '',      // 视频录制时间

      // ===== 已保存媒体列表 =====
      savedMediaList: [],       // 保存的所有照片/视频列表
      selectedMediaIndex: 0,    // 当前选中的媒体记录下标
      showDropdown: false,      // 是否展开媒体下拉列表

      // ===== AI分析相关 =====
      showAnalysisModal: false, // 是否展示AI分析弹窗
      isAnalyzing: false,       // 是否正在AI分析中
      analysisResult: null,     // AI分析结果
      analysisError: null,      // AI分析错误信息
      analysisTimestamp: '',    // AI分析时间戳
      visualEvidence: null,     // 结构化视觉证据（供 RAG 融合）
      fusionResult: null,       // 融合检索结果
      fusionLoading: false,     // 是否正在融合检索
      fusionError: '',          // 融合检索错误信息

      // ===== 接口配置 =====
      apiBaseUrl: import.meta.env.VITE_ANALYZER_API_BASE || '/analyzer-api',
      matchApiBase: import.meta.env.VITE_MATCH_API_BASE || '/match-api'
    }
  },
  // 生命周期：组件挂载完成后执行
  mounted() {
    // 页面加载时默认不自动请求权限，如需开启可取消下方注释
    // this.requestCameraAccess();
  },
  // 生命周期：组件销毁前执行 - 释放资源
  beforeUnmount() {
    this.stopCamera();
  },
  // 组件核心业务方法集
  methods: {
    /**
     * 请求摄像头+麦克风权限，优先启用后置摄像头
     */
    async requestCameraAccess() {
      try {
        // 优先请求后置摄像头+麦克风权限
        const constraints = {
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
          audio: true
        };
        this.stream = await navigator.mediaDevices.getUserMedia(constraints);
        this.cameraPermission = true;
        await this.getAvailableCameras();
        this.setupVideoStream();
      } catch (error) {
        // 后置摄像头不可用，降级请求前置摄像头
        try {
          const fallbackConstraints = {
            video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
            audio: true
          };
          this.stream = await navigator.mediaDevices.getUserMedia(fallbackConstraints);
          this.cameraPermission = true;
          await this.getAvailableCameras();
          this.setupVideoStream();
        } catch (fallbackError) {
          alert('无法访问摄像头，请检查权限设置');
        }
      }
    },

    /**
     * 获取设备上所有可用的摄像头设备列表
     */
    async getAvailableCameras() {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        this.availableCameras = devices.filter(device => device.kind === 'videoinput');
        // 优先选中后置摄像头，无则选第一个
        if (this.availableCameras.length > 0) {
          const backCamera = this.availableCameras.find(camera => 
            camera.label.toLowerCase().includes('back') || 
            camera.label.toLowerCase().includes('rear') ||
            camera.label.toLowerCase().includes('environment')
          );
          this.selectedCamera = backCamera ? backCamera.deviceId : this.availableCameras[0].deviceId;
        }
      } catch (error) {
        console.error('无法获取摄像头列表:', error);
      }
    },

    /**
     * 将媒体流绑定到页面的video标签，展示摄像头画面
     */
    setupVideoStream() {
      if (this.$refs.videoElement && this.stream) {
        this.$refs.videoElement.srcObject = this.stream;
      }
    },

    /**
     * 切换选中的摄像头设备
     */
    async switchCamera() {
      if (this.selectedCamera) {
        await this.stopCamera();
        const constraints = {
          video: { deviceId: this.selectedCamera, width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: true
        };
        try {
          this.stream = await navigator.mediaDevices.getUserMedia(constraints);
          this.setupVideoStream();
        } catch (error) {
          console.error('切换摄像头失败:', error);
        }
      }
    },

    /**
     * 修改摄像头拍摄分辨率
     */
    async changeResolution() {
      const [width, height] = this.selectedResolution.split('x').map(Number);
      await this.stopCamera();
      const constraints = {
        video: { width: { ideal: width }, height: { ideal: height }, deviceId: this.selectedCamera },
        audio: true
      };
      try {
        this.stream = await navigator.mediaDevices.getUserMedia(constraints);
        this.setupVideoStream();
      } catch (error) {
        console.error('改变分辨率失败:', error);
      }
    },

    /**
     * 获取当前使用的摄像头类型（前置/后置）
     * @returns {String} 摄像头类型文字
     */
    getCurrentCameraType() {
      const currentCamera = this.availableCameras.find(camera => camera.deviceId === this.selectedCamera);
      if (!currentCamera) return '摄像头';
      const label = currentCamera.label.toLowerCase();
      if (label.includes('back') || label.includes('rear') || label.includes('environment')) {
        return '后置摄像头';
      } else if (label.includes('front') || label.includes('user') || label.includes('facing')) {
        return '前置摄像头';
      }
      return currentCamera.label || '摄像头';
    },

    /**
     * 拍摄患者照片核心方法
     */
    capturePhoto() {
      if (this.$refs.videoElement) {
        const canvas = document.createElement('canvas');
        const video = this.$refs.videoElement;
        // 视频流未加载完成则延迟重试
        if (video.videoWidth === 0 || video.videoHeight === 0) {
          console.warn('视频未准备好，延迟拍照');
          setTimeout(() => this.capturePhoto(), 200);
          return;
        }
        // 绘制画布并转base64格式
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        this.capturedImage = canvas.toDataURL('image/jpeg', 0.8);
        this.captureTimestamp = new Date().toLocaleString();
        this.showPreview = true;
        // 向外派发照片拍摄完成事件
        this.$emit('photo-captured', { data: this.capturedImage, timestamp: this.captureTimestamp });
      }
    },

    /**
     * 切换视频录制状态：开始/停止录制
     */
    toggleRecording() {
      this.isRecording ? this.stopRecording() : this.startRecording();
    },

    /**
     * 开始录制视频
     */
    startRecording() {
      if (this.stream) {
        const options = { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 2500000 };
        try {
          this.mediaRecorder = new MediaRecorder(this.stream, options);
          const chunks = [];
          // 录制过程中收集视频流数据
          this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) chunks.push(event.data);
          };
          // 录制停止后处理视频数据
          this.mediaRecorder.onstop = () => {
            const blob = new Blob(chunks, { type: 'video/webm' });
            this.recordedVideo = URL.createObjectURL(blob);
            this.recordTimestamp = new Date().toLocaleString();
            this.showPreview = true;
            // 向外派发视频录制完成事件
            this.$emit('video-recorded', { data: this.recordedVideo, duration: this.videoDuration, timestamp: this.recordTimestamp });
          };
          // 启动录制+开启计时
          this.mediaRecorder.start();
          this.isRecording = true;
          this.recordingTime = 0;
          this.recordingTimer = setInterval(() => { this.recordingTime++; }, 1000);
        } catch (error) {
          console.error('开始录制失败:', error);
          alert('录制功能不支持，请尝试使用其他浏览器');
        }
      }
    },

    /**
     * 停止录制视频
     */
    stopRecording() {
      if (this.mediaRecorder && this.isRecording) {
        this.mediaRecorder.stop();
        this.isRecording = false;
        this.videoDuration = this.recordingTime;
        // 清除计时定时器
        if (this.recordingTimer) {
          clearInterval(this.recordingTimer);
          this.recordingTimer = null;
        }
      }
    },

    /**
     * 保存当前预览的照片/视频到本地列表
     */
    async saveMedia() {
      // 组装媒体数据对象
      const mediaData = {
        type: this.capturedImage ? 'photo' : 'video',
        data: this.capturedImage || this.recordedVideo,
        timestamp: this.capturedImage ? this.captureTimestamp : this.recordTimestamp,
        duration: this.videoDuration,
        name: `${this.capturedImage ? '照片' : '视频'}_${Date.now()}`,
        blob: null
      };
      // 照片：base64转blob格式，方便后续上传
      if (this.capturedImage) {
        const base64Data = this.capturedImage.split(',')[1];
        const byteCharacters = atob(base64Data);
        const byteArrays = [];
        for (let offset = 0; offset < byteCharacters.length; offset += 512) {
          const slice = byteCharacters.slice(offset, offset + 512);
          const byteNumbers = new Array(slice.length);
          for (let i = 0; i < slice.length; i++) byteNumbers[i] = slice.charCodeAt(i);
          byteArrays.push(new Uint8Array(byteNumbers));
        }
        mediaData.blob = new Blob(byteArrays, { type: 'image/jpeg' });
      }
      // 视频：blob地址转blob对象
      else if (this.recordedVideo) {
        try {
          const response = await fetch(this.recordedVideo);
          mediaData.blob = await response.blob();
        } catch (error) {
          console.error('视频转换Blob失败:', error);
        }
      }
      // 加入保存列表+重置预览状态+派发保存事件
      this.savedMediaList.push(mediaData);
      this.showPreview = false;
      this.capturedImage = null;
      this.recordedVideo = null;
      this.$emit('media-saved', mediaData);
      // 重置视频流
      this.$nextTick(() => this.setupVideoStream());
    },

    /**
     * 删除当前预览的未保存媒体文件
     */
    deleteMedia() {
      this.showPreview = false;
      this.capturedImage = null;
      this.recordedVideo = null;
      this.$nextTick(() => this.setupVideoStream());
    },

    /**
     * 重新拍摄：复用删除方法，返回摄像头页面
     */
    retakeMedia() {
      this.deleteMedia();
    },

    /**
     * 删除已保存的媒体记录
     * @param {Number} index 要删除的记录下标
     */
    removeSavedMedia(index) {
      this.savedMediaList.splice(index, 1);
      // 处理下标越界问题
      if (this.selectedMediaIndex >= this.savedMediaList.length) {
        this.selectedMediaIndex = Math.max(0, this.savedMediaList.length - 1);
      }
    },

    /**
     * 切换摄像头设置面板的显隐状态
     */
    toggleSettings() {
      this.showSettings = !this.showSettings;
    },

    /**
     * 停止摄像头，释放媒体流资源（防止内存泄漏）
     */
    stopCamera() {
      if (this.stream) {
        this.stream.getTracks().forEach(track => track.stop());
        this.stream = null;
      }
    },

    /**
     * 切换媒体列表下拉选择器的显隐状态
     */
    toggleDropdown() {
      this.showDropdown = !this.showDropdown;
    },

    /**
     * 选中指定下标对应的媒体记录
     * @param {Number} index 媒体记录下标
     */
    selectMedia(index) {
      this.selectedMediaIndex = index;
      this.showDropdown = false;
    },

    // ===================== AI分析相关方法 =====================
    /**
     * 调用后端接口，对选中的媒体文件进行AI分析
     */
    async analyzeMedia() {
      const media = this.savedMediaList[this.selectedMediaIndex];
      if (!media || !media.blob) {
        alert('无法分析该媒体文件');
        return;
      }
      // 重置分析状态
      this.showAnalysisModal = true;
      this.isAnalyzing = true;
      this.analysisResult = null;
      this.analysisError = null;
      this.analysisTimestamp = new Date().toLocaleString();

      try {
        // 组装表单数据，准备上传文件
        const formData = new FormData();
        const fileExtension = media.type === 'photo' ? 'jpg' : 'webm';
        const mimeType = media.type === 'photo' ? 'image/jpeg' : 'video/webm';
        const file = new File([media.blob], `media_${Date.now()}.${fileExtension}`, { type: mimeType });
        formData.append('file', file);
        
        // 请求后端AI分析接口
        const response = await fetch(`${this.apiBaseUrl}/analyze`, { method: 'POST', body: formData });
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        const data = await response.json();
        
        // 处理分析结果（后端同时返回 analysis / rescue_advice，兼容两种字段）
        if (data.success) {
          this.analysisResult = data.rescue_advice ?? data.analysis ?? '';
          this.visualEvidence = data.visual_evidence || null;
          this.fusionResult = null;
          this.fusionError = '';
        } else {
          this.analysisError = data.error || '分析失败';
        }
      } catch (error) {
        console.error('AI分析失败:', error);
        this.analysisError = error.message || '网络请求失败，请检查后端服务是否运行';
      } finally {
        this.isAnalyzing = false;
      }
    },

    /**
     * 格式化AI分析结果，美化展示样式
     * @param {String} text 原始分析文本
     * @returns {String} 格式化后的HTML文本
     */
    formatAnalysisResult(text) {
      if (!text) return '';
      return text.replace(/\n/g, '<br>')
                .replace(/(\d+[\.、，])/g, '<br><strong>$1</strong> ')
                .replace(/救治场景|伤员病情|急救建议/g, '<strong>$&</strong>');
    },

    /**
     * 关闭AI分析结果弹窗，重置分析状态
     */
    closeAnalysisModal() {
      this.showAnalysisModal = false;
      this.analysisResult = null;
      this.analysisError = null;
      this.visualEvidence = null;
      this.fusionResult = null;
      this.fusionError = '';
    },

    /**
     * 将视觉证据注入 RAG 检索：调用 /match（visual 字段），
     * 文本与视觉候选进行融合判定，返回融合后的处置建议。
     */
    async triggerFusion() {
      if (!this.visualEvidence || !this.visualEvidence.injury_candidates || !this.visualEvidence.injury_candidates.length) {
        this.fusionError = '视觉证据中没有可用伤情候选，无法融合检索';
        return;
      }
      this.fusionLoading = true;
      this.fusionError = '';
      this.fusionResult = null;
      try {
        const response = await fetch(`${this.matchApiBase}/agentic`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: '', visual: this.visualEvidence, mode: 'llm' })
        });
        const data = await response.json();
        if (response.ok && data.success) {
          const evidence = data.evidence || {};
          this.fusionResult = {
            advice: Array.isArray(data.steps)
              ? data.steps.map((step) => typeof step === 'string' ? step : step?.action).filter(Boolean)
              : [],
            matchedInjury: data.matched_injury || '',
            similarityScore: data.similarity_score,
            source: evidence.source || 'agentic',
            consistent: !evidence.needs_review,
            needsReview: !!evidence.needs_review,
            reason: data.final_decision || ''
          };
        } else {
          this.fusionError = data.error || '融合检索未匹配';
        }
      } catch (error) {
        this.fusionError = error.message || '融合检索请求失败，请检查后端服务';
      } finally {
        this.fusionLoading = false;
      }
    },

    /**
     * 下载保存AI分析报告为JSON文件
     */
    saveAnalysisResult() {
      if (!this.analysisResult) return;
      // 组装报告数据
      const report = {
        mediaName: this.savedMediaList[this.selectedMediaIndex].name,
        timestamp: this.analysisTimestamp,
        analysis: this.analysisResult,
        mediaType: this.savedMediaList[this.selectedMediaIndex].type,
        mediaData: this.savedMediaList[this.selectedMediaIndex].data
      };
      // 生成下载链接并触发下载
      const dataStr = JSON.stringify(report, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `救治分析报告_${new Date().getTime()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      alert('分析报告已保存');
    }
  }
}
</script>

<style scoped>
.camera-module {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(79, 195, 247, 0.3);
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
}

.camera-module h4 {
  color: #4fc3f7;
  margin-bottom: 1.5rem;
  font-size: 1.2rem;
  font-weight: 600;
  text-shadow: 0 0 10px rgba(79, 195, 247, 0.5);
}

/* 权限请求样式 */
.permission-request {
  text-align: center;
	padding: 2rem;
}
.permission-icon {
	font-size: 4rem;
	margin-bottom: 1rem;
}
.permission-request p {
	color: rgba(255, 255, 255, 0.8);
	margin-bottom: 1.5rem;
	line-height: 1.6;
}
.permission-btn {
	background: linear-gradient(135deg, #4fc3f7, #29b6f6);
	border: none;
	color: white;
	padding: 12px 24px;
	border-radius: 8px;
	font-size: 1rem;
	font-weight: 500;
	cursor: pointer;
	transition: all 0.3s ease;
	box-shadow: 0 4px 15px rgba(79, 195, 247, 0.3);
}
.permission-btn:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(79, 195, 247, 0.4);
}

/* 摄像头界面样式 */
.camera-interface {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}
.camera-preview {
	position: relative;
	border-radius: 8px;
	overflow: hidden;
	background: #000;
}
.camera-video {
	width: 100%;
	height: auto;
	display: block;
	border-radius: 8px;
}
.camera-type-indicator {
	position: absolute;
	top: 15px;
	right: 15px;
	background: rgba(79, 195, 247, 0.8);
	color: white;
	padding: 6px 10px;
	border-radius: 16px;
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 0.8rem;
	font-weight: 500;
	backdrop-filter: blur(5px);
}
.camera-icon { font-size: 0.9rem; }
.recording-indicator {
	position: absolute;
	top: 15px;
	left: 15px;
	background: rgba(255, 0, 0, 0.8);
	color: white;
	padding: 8px 12px;
	border-radius: 20px;
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 0.9rem;
	font-weight: 500;
}
.recording-dot {
	width: 8px;
	height: 8px;
	background: white;
	border-radius: 50%;
	animation: blink 1s infinite;
}
@keyframes blink {
	0%, 50% { opacity: 1; }
	51%, 100% { opacity: 0.3; }
}

/* 控制按钮通用样式 */
.camera-controls {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 0.8rem;
}
.control-btn {
	background: rgba(255, 255, 255, 0.1);
	border: 1px solid rgba(79, 195, 247, 0.3);
	color: white;
	padding: 12px 8px;
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.3s ease;
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 4px;
	font-size: 0.9rem;
}
.control-btn:hover {
	background: rgba(79, 195, 247, 0.2);
	border-color: #4fc3f7;
	transform: translateY(-2px);
}
.control-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
	transform: none;
}
.btn-icon { font-size: 1.5rem; }
.record-btn.recording {
	background: rgba(255, 0, 0, 0.2);
	border-color: #ff4757;
	color: #ff4757;
}

/* 设置面板样式 */
.settings-panel {
	background: rgba(255, 255, 255, 0.05);
	border: 1px solid rgba(79, 195, 247, 0.2);
	border-radius: 8px;
	padding: 1rem;
	margin-top: 1rem;
}
.setting-item {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 0.8rem;
}
.setting-item:last-child { margin-bottom: 0; }
.setting-item label {
	color: rgba(255, 255, 255, 0.9);
	font-size: 0.9rem;
}
.setting-item select {
	background: transparent;
	border: 1px solid rgba(79, 195, 247, 0.3);
	color: white;
	padding: 6px 8px;
	border-radius: 4px;
	font-size: 0.8rem;
	-webkit-appearance: none;
	-moz-appearance: none;
	appearance: none;
}
.setting-item select option {
	background: transparent;
	color: white;
}

/* 预览界面样式 */
.preview-interface {
	display: flex;
	flex-direction: column;
	gap: 1rem;
}
.photo-preview img, .preview-video {
	width: 100%;
	border-radius: 8px;
}
.preview-info {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 8px 0;
	font-size: 0.8rem;
	color: rgba(255, 255, 255, 0.7);
}
.file-type {
	background: rgba(79, 195, 247, 0.3);
	padding: 4px 8px;
	border-radius: 12px;
	color: #4fc3f7;
}
.preview-controls {
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	gap: 0.8rem;
}

/* 已保存媒体样式 */
.saved-media { margin-top: 1.5rem; }
.saved-media h5 {
	color: #4fc3f7;
	margin-bottom: 1rem;
	font-size: 1rem;
}
.media-selector {
	margin-bottom: 1rem;
	display: flex;
	align-items: center;
	gap: 8px;
}
.media-selector label {
	color: rgba(255, 255, 255, 0.9);
	font-size: 0.9rem;
}
.custom-dropdown {
	position: relative;
	width: 100%;
	cursor: pointer;
}
.dropdown-selected {
	background: #36287d;
	color: white;
	padding: 10px;
	border-radius: 4px;
	display: flex;
	justify-content: space-between;
	align-items: center;
}
.dropdown-arrow {
	font-size: 0.8rem;
	margin-left: 8px;
}
.dropdown-options {
	position: absolute;
	top: 100%;
	left: 0;
	right: 0;
	background: #36287d;
	border: 1px solid rgba(79, 195, 247, 0.2);
	border-radius: 4px;
	margin-top: 4px;
	z-index: 10;
	max-height: 200px;
	overflow-y: auto;
}
.dropdown-option {
	padding: 10px;
	color: white;
	cursor: pointer;
	transition: background 0.3s ease;
	background: #36287d;
}
.dropdown-option:hover { background: rgba(79, 195, 247, 0.3); }
.selected { background: rgba(79, 195, 247, 0.4); }

/* 当前选中媒体样式 */
.current-media {
	display: flex;
	align-items: center;
	gap: 12px;
	background: rgba(255, 255, 255, 0.05);
	padding: 10px;
	border-radius: 8px;
	position: relative;
}
.media-item {
	display: flex;
	align-items: center;
	gap: 12px;
	background: rgba(255, 255, 255, 0.05);
	padding: 10px;
	border-radius: 8px;
	cursor: pointer;
	transition: all 0.3s ease;
	position: relative;
}
.media-item:hover { background: rgba(79, 195, 247, 0.1); }
.media-thumbnail {
	position: relative;
	width: 60px;
	height: 45px;
	border-radius: 4px;
	overflow: hidden;
}
.media-thumbnail img, .video-thumbnail {
	width: 100%;
	height: 100%;
	object-fit: cover;
}
.media-type-badge {
	position: absolute;
	top: 2px;
	right: 2px;
	font-size: 0.8rem;
	background: rgba(0, 0, 0, 0.6);
	border-radius: 50%;
	width: 20px;
	height: 20px;
	display: flex;
	align-items: center;
	justify-content: center;
}
.media-info {
	flex: 1;
	display: flex;
	flex-direction: column;
	gap: 2px;
}
.media-name {
	color: white;
	font-size: 0.9rem;
	font-weight: 500;
}
.media-time {
	color: rgba(255, 255, 255, 0.6);
	font-size: 0.8rem;
}
.media-duration {
	color: rgba(255, 255, 255, 0.5);
	font-size: 0.7rem;
}
.media-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}
.analyze-btn {
	background: linear-gradient(135deg, #6a11cb, #2575fc);
	border: none;
	color: white;
	padding: 8px 12px;
	border-radius: 6px;
	cursor: pointer;
	transition: all 0.3s ease;
	display: flex;
	align-items: center;
	gap: 4px;
	font-size: 0.8rem;
}
.analyze-btn:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(37, 117, 252, 0.4);
}
.delete-media-btn {
	background: rgba(255, 0, 0, 0.2);
	border: none;
	color: #ff4757;
	width: 24px;
	height: 24px;
	border-radius: 50%;
	cursor: pointer;
	font-size: 1rem;
	display: flex;
	align-items: center;
	justify-content: center;
	transition: all 0.3s ease;
}
.delete-media-btn:hover { background: rgba(255, 0, 0, 0.3); }

/* AI分析弹窗样式 */
.modal-overlay {
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background: rgba(0, 0, 0, 0.8);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 1000;
	backdrop-filter: blur(5px);
}
.modal-content {
	background: linear-gradient(135deg, #1a1a2e, #16213e);
	border-radius: 12px;
	width: 90%;
	max-width: 800px;
	max-height: 90vh;
	overflow-y: auto;
	border: 1px solid rgba(79, 195, 247, 0.3);
	box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.modal-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 1.5rem;
	border-bottom: 1px solid rgba(79, 195, 247, 0.2);
}
.modal-header h4 {
	color: #4fc3f7;
	margin: 0;
	font-size: 1.3rem;
}
.modal-close {
	background: none;
	border: none;
	color: #ff4757;
	font-size: 1.5rem;
	cursor: pointer;
	padding: 0;
	width: 30px;
	height: 30px;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 50%;
	transition: all 0.3s ease;
}
.modal-close:hover { background: rgba(255, 71, 87, 0.1); }
.modal-body { padding: 1.5rem; }

/* 分析指示器样式 */
.analyzing-indicator {
	text-align: center;
	padding: 2rem;
	color: #4fc3f7;
}
.spinner {
	width: 50px;
	height: 50px;
	border: 3px solid rgba(79, 195, 247, 0.3);
	border-top-color: #4fc3f7;
	border-radius: 50%;
	animation: spin 1s linear infinite;
	margin: 0 auto 1rem;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* AI结果样式 */
.ai-result {
	background: rgba(0, 0, 0, 0.2);
	border-left: 4px solid #4fc3f7;
	padding: 1rem;
	border-radius: 8px;
	margin-bottom: 1.5rem;
}
.result-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 1rem;
}
.result-header h5 {
	color: #4fc3f7;
	margin: 0;
	font-size: 1.1rem;
}
.analysis-time {
	color: rgba(255, 255, 255, 0.6);
	font-size: 0.8rem;
}
.ai-advice {
	color: white;
	white-space: pre-wrap;
	font-family: inherit;
	line-height: 1.6;
}
.ai-error {
	color: #ff6b6b;
	padding: 1rem;
	background: rgba(255, 107, 107, 0.1);
	border-radius: 8px;
	border-left: 4px solid #ff6b6b;
	margin-bottom: 1rem;
}

/* 原始媒体预览样式 */
.original-media-preview {
	margin-top: 2rem;
	padding-top: 1.5rem;
	border-top: 1px solid rgba(79, 195, 247, 0.2);
}
.original-media-preview h6 {
	color: #4fc3f7;
	margin-bottom: 1rem;
	font-size: 1rem;
}
.original-media-preview img, .original-media-preview video {
	width: 100%;
	max-height: 200px;
	object-fit: contain;
	border-radius: 8px;
	background: #000;
}

/* 弹窗底部按钮样式 */
.modal-footer {
	display: flex;
	justify-content: flex-end;
	gap: 1rem;
	padding: 1.5rem;
	border-top: 1px solid rgba(79, 195, 247, 0.2);
}
.btn-primary, .btn-secondary {
	padding: 10px 20px;
	border-radius: 6px;
	border: none;
	cursor: pointer;
	font-size: 0.9rem;
	font-weight: 500;
	transition: all 0.3s ease;
}
.btn-primary {
	background: linear-gradient(135deg, #4fc3f7, #29b6f6);
	color: white;
}
.btn-secondary {
	background: rgba(255, 255, 255, 0.1);
	color: white;
	border: 1px solid rgba(255, 255, 255, 0.2);
}
.btn-primary:hover, .btn-secondary:hover {
	transform: translateY(-2px);
	box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

/* 视觉证据 → RAG 融合检索样式 */
.fusion-section {
	margin-top: 1.5rem;
	padding: 1rem;
	border: 1px solid rgba(79, 195, 247, 0.3);
	border-radius: 8px;
	background: rgba(79, 195, 247, 0.05);
}
.fusion-section h6 {
	color: #4fc3f7;
	margin-bottom: 0.6rem;
	font-size: 0.95rem;
}
.fusion-evidence {
	display: flex;
	flex-wrap: wrap;
	gap: 0.6rem 1.2rem;
	font-size: 0.85rem;
	color: rgba(255, 255, 255, 0.85);
	margin-bottom: 0.8rem;
}
.fusion-no-candidate {
	color: #ffb74d;
}
.fusion-btn {
	margin-bottom: 0.8rem;
}
.fusion-btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
	transform: none;
}
.review-warning {
	padding: 0.6rem 0.8rem;
	margin-bottom: 0.6rem;
	border: 1px solid #ffb74d;
	border-radius: 6px;
	background: rgba(255, 183, 77, 0.12);
	color: #ffb74d;
	font-size: 0.85rem;
}
.fusion-meta {
	font-size: 0.85rem;
	color: #4fc3f7;
	margin-bottom: 0.6rem;
}
.fusion-steps {
	display: flex;
	flex-direction: column;
	gap: 0.45rem;
}
.fusion-step {
	font-size: 0.9rem;
	line-height: 1.6;
	color: rgba(255, 255, 255, 0.92);
	padding-left: 0.8rem;
	border-left: 2px solid rgba(79, 195, 247, 0.4);
}

/* 响应式适配-移动端样式 */
@media (max-width: 768px) {
	.camera-controls, .preview-controls { grid-template-columns: 1fr; }
	.control-btn { padding: 16px; }
	.media-item { flex-direction: column; text-align: center; }
	.media-thumbnail { width: 80px; height: 60px; }
	.media-actions { margin-top: 10px; justify-content: center; }
	.modal-content { width: 95%; max-height: 95vh; }
}
</style>
