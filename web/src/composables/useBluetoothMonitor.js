import { ref, reactive } from 'vue'

// 蓝牙数据解析器类
class BMDataParser {
  constructor() {
    this.PACKAGE_MIN_LENGTH = 4
    this.PACKAGE_HEADER = [0x55, 0xaa]
    this.PACKAGE_CALLBACKS = [
      //package_type     callback_name                   callback_func
      0x01, 'on_ecg_waveform_received', null,
      0x02, 'on_ecg_params_received', null,
      0x03, 'on_nibp_params_received', null,
      0x04, 'on_spo2_params_received', null,
      0x05, 'on_temp_params_received', null,
      0x30, 'on_ecg_peak_received', null,
      0x31, 'on_spo2_peak_received', null,
      0xfc, 'on_firmware_ver_received', null,
      0xfd, 'on_hardware_ver_received', null,
      0xfe, 'on_spo2_waveform_received', null,
      0xff, 'on_resp_waveform_received', null,
    ]
    this.rawBuffer = []
  }

  registerCallback(name, callback) {
    var callbackNameIndex = this.PACKAGE_CALLBACKS.indexOf(name)
    if (callbackNameIndex != -1) {
      this.PACKAGE_CALLBACKS[callbackNameIndex + 1] = callback
    }
  }

  addData(arr) {
    this.rawBuffer.push(...Array.prototype.slice.call(new Uint8Array(arr.buffer)))

    while (this.rawBuffer.length >= this.PACKAGE_MIN_LENGTH) {
      let packageStartIndex = -1
      for (let i = 0; i < (this.rawBuffer.length - 1); i++) {
        if ((this.rawBuffer[i] === this.PACKAGE_HEADER[0]) && (this.rawBuffer[i + 1] === this.PACKAGE_HEADER[1])) {
          packageStartIndex = i
          break
        }
      }

      if (packageStartIndex === -1) {
        this.rawBuffer.splice(0, this.rawBuffer.length - 1)
        continue
      }

      let packageEndIndex = packageStartIndex + this.rawBuffer[packageStartIndex + 2] + 2
      if (packageEndIndex > this.rawBuffer.length) {
        break
      }

      let packageData = this.rawBuffer.slice(packageStartIndex, packageEndIndex)
      this.rawBuffer.splice(0, packageEndIndex)

      if (this.checkSum(packageData)) {
        this.parsePackage(packageData)
      }
    }
  }

  checkSum(pkg) {
    var sum = 0
    for (let i = 2; i < pkg.length - 1; i++) {
      sum += pkg[i]
    }
    sum = (~sum) & 0xff
    return sum === pkg[pkg.length - 1]
  }

  parsePackage(pkg) {
    const packageType = pkg[3]
    let callback = null

    // 通过package_type查找对应的callback
    for (let i = 0; i < this.PACKAGE_CALLBACKS.length; i += 3) {
      if (this.PACKAGE_CALLBACKS[i] === packageType) {
        callback = this.PACKAGE_CALLBACKS[i + 2]
        break
      }
    }

    if (callback == null) return

    // console.log('Parsed package type:', packageType, 'data:', pkg)

    switch (packageType) {
      case 0x01: // ECG waveform
        callback(pkg[4])
        break

      case 0x02: // ECG params
        callback(/*states*/pkg[4], /*heart rate*/pkg[5], /*resp rate*/pkg[6])
        break

      case 0x03: // NIBP params
        callback(/*states*/pkg[4], /*cuff pressure*/pkg[5] * 2, /*SYS*/pkg[6], /*MEAN*/pkg[7], /*DIA*/pkg[8])
        break

      case 0x04: // SpO2 params
        callback(/*states*/pkg[4], /*SpO2*/pkg[5], /*pulse rate*/pkg[6])
        break

      case 0x05: // Temperature params
        callback(/*states*/pkg[4], /*temperature*/(pkg[5] * 10 + pkg[6]) / 10.0)
        break

      case 0x30: // ECG peak
        callback()
        break

      case 0x31: // SpO2 peak
        callback()
        break

      case 0xfc: // Firmware version
        break

      case 0xfd: // Hardware version
        break

      case 0xfe: // SpO2 waveform
        callback(/*ppg*/pkg[4])
        break

      case 0xff: // RESP waveform
        callback(/*ecg*/pkg[4])
        break
    }
  }
}

// 蓝牙患者监护仪类
class BMPatientMonitor {
  constructor(parser, refreshStatus) {
    this.UUID_SERVICE_COMM = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
    this.UUID_CHARACTER_RECEIVE = "49535343-1e4d-4bd9-ba61-23c647249616"
    this.UUID_CHARACTER_SEND = "49535343-8841-43f4-a8d4-ecbe34729bb3"

    this.device = null
    this.chReceive = null
    this.chSend = null
    this.server = null
    this.parser = parser
    this.refreshStatus = refreshStatus
    this.reconnectTime = 0
  }

  sleep(mseconds) {
    return new Promise((resolve => {
      setTimeout(resolve, mseconds)
    }))
  }

  startNotify() {
    // console.log('Starting notifications...')
    this.chReceive.addEventListener(
      'characteristicvaluechanged', e => {
        // console.log('Characteristic value changed:', e.target.value)
        if (e.target.value) {
          this.parser.addData(e.target.value)
        }
      }
    )

    this.chReceive.startNotifications().then(() => {
      console.log('Notifications started successfully')
    }).catch(error => {
      console.error('Failed to start notifications:', error)
    })
  }

  startNIBP() {
    if (this.chSend != null) {
      this.chSend.writeValue(new Uint8Array([0x55, 0xaa, 0x04, 0x02, 0x01, 0xf8]))
    }
  }

  async connect() {
    this.device = null
    this.chReceive = null
    this.chSend = null
    this.server = null

    try {
      this.device = await navigator.bluetooth.requestDevice({
        filters: [{ namePrefix: 'BerryMed' },{ namePrefix: 'USTB' }],
        optionalServices: [this.UUID_SERVICE_COMM]
      })

      this.device.addEventListener('gattserverdisconnected', () => {
        this.refreshStatus('Disconnected')
        console.log('bm-patient-monitor: disconnected.')
      })

      while ((this.chReceive == null) && (this.reconnectTime <= 5)) {
        // console.log('bm-patient-monitor: ', 'connect time ' + this.reconnectTime)
        this.refreshStatus('Connecting to ' + this.device.name)

        try {
          this.server = await this.device.gatt.connect()
          // console.log('bm-patient-monitor: ', this.server)

          const service = await this.server.getPrimaryService(this.UUID_SERVICE_COMM)
          // console.log('bm-patient-monitor: ', service)

          this.chReceive = await service.getCharacteristic(this.UUID_CHARACTER_RECEIVE)
          // console.log('bm-patient-monitor: recv - ', this.chReceive)

          this.chSend = await service.getCharacteristic(this.UUID_CHARACTER_SEND)
          // console.log('bm-patient-monitor: send - ', this.chSend)
        }
        catch (e) {
          console.log('bm-patient-monitor: ', this.chReceive)
        }

        await this.sleep(500)
        this.reconnectTime += 1
      }

      this.reconnectTime = 0

      if (this.chReceive != null) {
        this.startNotify()
        this.refreshStatus('Connected to ' + this.device.name)
        // console.log('bm-patient-monitor: ' + 'start notify')
      }
      else {
        this.refreshStatus('Not Connect')
      }
    } catch (error) {
      this.refreshStatus('Connection failed: ' + error.message)
      console.error('Connection error:', error)
    }
  }
}

// 波形绘制类
class BMWaveform {
  constructor(canvas, color, maxValue, step) {
    this.canvas = canvas
    this.color = color
    this.maxValue = maxValue
    this.step = step

    this.context = this.canvas.getContext("2d")
    this.context.strokeStyle = this.color
    this.context.lineWidth = 1.2
    this.context.lineCap = 'round'

    this.prevPointX = 0
    this.prevPointY = this.canvas.height / 2
  }

  add(yValue) {
    var curPointX = this.prevPointX + this.step

    if (curPointX >= this.canvas.width) {
      this.prevPointX = 0
      curPointX = 0

      this.context.clearRect(0, 0, this.canvas.width, this.canvas.height)
    }
    else {
      var curPointY = this.canvas.height - yValue * this.canvas.height / this.maxValue
      curPointY = curPointY * 0.98

      this.context.beginPath()
      this.context.fillStyle = 'rgba(0, 0, 0, 0.1)'
      this.context.fillRect(curPointX, 0, 5, this.canvas.height)
      this.context.strokeStyle = this.color
      this.context.moveTo(this.prevPointX, this.prevPointY)
      this.context.lineTo(curPointX, curPointY)
      this.context.stroke()

      this.prevPointY = curPointY
    }

    this.prevPointX = curPointX
  }

  addArray(arr) {
    while (arr.length > 0) {
      this.add(arr.shift())
    }
  }
}

// Vue 组合式函数
export function useBluetoothMonitor() {
  const bluetoothStatus = ref('Not Connected')
  const isConnecting = ref(false)

  // 生理参数
  const vitalParams = reactive({
    heartRate: '- -',
    nibp: '- - -/- -',
    spo2: '- -',
    pulseRate: '- -',
    temperature: '- -.-',
    respRate: '- -'
  })

  // 波形数据缓冲区
  const waveformBuffers = reactive({
    ecg: [],
    spo2: [],
    resp: []
  })

  // 初始化数据解析器
  const dataParser = new BMDataParser()
  let patientMonitor = null
  let waveforms = []

  // 注册数据解析回调
  const setupDataParserCallbacks = () => {
    // console.log('Setting up data parser callbacks...')

    // 心电图波形数据
    dataParser.registerCallback('on_ecg_waveform_received', (amp) => {
      // console.log('ECG waveform received:', amp)
      waveformBuffers.ecg.push(amp)
    })

    // SpO2波形数据
    dataParser.registerCallback('on_spo2_waveform_received', (ppg) => {
      // console.log('SpO2 waveform received:', ppg)
      waveformBuffers.spo2.push(ppg)
    })

    // 呼吸波形数据
    dataParser.registerCallback('on_resp_waveform_received', (ecg) => {
      // console.log('RESP waveform received:', ecg)
      waveformBuffers.resp.push(ecg)
    })

    // 心电图参数（心率和呼吸率）
    dataParser.registerCallback('on_ecg_params_received', (states, heartRate, respRate) => {
      // console.log('ECG params received:', { states, heartRate, respRate })
      // 注意：设备数据中心电参数的第二个值实际上是脉率（PR），将其赋值给 pulseRate
      vitalParams.pulseRate = (heartRate === 0) ? '- -' : heartRate.toString()
      vitalParams.respRate = (respRate === 0) ? '- -' : respRate.toString()
    })

    // 血氧参数
    dataParser.registerCallback('on_spo2_params_received', (states, spo2, pulseRate) => {
      // console.log('SpO2 params received:', { states, spo2, pulseRate })
      vitalParams.spo2 = (spo2 === 127) ? '- -' : spo2.toString()
      // 注意：将 SpO2 包中的脉率值用作显示的心率（HR），修复心率/脉率互换的问题
      vitalParams.heartRate = (pulseRate === 255) ? '- -' : pulseRate.toString()
    })

    // 血压参数
    dataParser.registerCallback('on_nibp_params_received', (states, cuffPressure, sys, mean, dia) => {
      // console.log('NIBP params received:', { states, cuffPressure, sys, mean, dia })
      if (sys === 0 && dia === 0) {
        vitalParams.nibp = '- - -/- -'
      } else {
        vitalParams.nibp = `${sys}/${dia}`
      }
    })

    // 体温参数
    dataParser.registerCallback('on_temp_params_received', (states, temperature) => {
      // console.log('Temp params received:', { states, temperature })
      vitalParams.temperature = (temperature === 0) ? '- -.-' : temperature.toFixed(1)
    })
  }

  // 刷新蓝牙状态
  const refreshBluetoothStatus = (status) => {
    bluetoothStatus.value = status
    if (status.includes('Connecting')) {
      isConnecting.value = true
    } else {
      isConnecting.value = false
    }
  }

  // 初始化波形绘制
  const initializeWaveforms = (canvasRefs) => {
    waveforms = []

    if (canvasRefs.ecg) {
      const waveformECG = new BMWaveform(canvasRefs.ecg, '#00ff88', 250, 1)
      waveforms.push({ "waveform": waveformECG, "buffer": waveformBuffers.ecg, "slice_size": 10 })
    }

    if (canvasRefs.spo2) {
      const waveformSpO2 = new BMWaveform(canvasRefs.spo2, '#ff4444', 250, 1)
      waveforms.push({ "waveform": waveformSpO2, "buffer": waveformBuffers.spo2, "slice_size": 10 })
    }

    if (canvasRefs.resp) {
      const waveformResp = new BMWaveform(canvasRefs.resp, '#ffdd00', 250, 1)
      waveforms.push({ "waveform": waveformResp, "buffer": waveformBuffers.resp, "slice_size": 10 })
    }
  }

  // 更新波形
  const updateWaveforms = () => {
    if (document.hidden) {
      for (let waveform of waveforms) {
        waveform["waveform"].addArray(waveform["buffer"].splice(0, waveform["buffer"].length))
      }
    }
    else {
      for (let waveform of waveforms) {
        // 只绘制实际接收到的ECG波形数据
        if (waveform["buffer"].length > 0) {
          const dataToProcess = Math.min(waveform["buffer"].length, waveform["slice_size"])
          waveform["waveform"].addArray(waveform["buffer"].splice(0, dataToProcess))
        }
      }
    }
  }

  // 连接蓝牙设备
  const connectDevice = async () => {
    console.log('Connecting to Bluetooth device...')

    if (!navigator.bluetooth) {
      alert('此浏览器不支持蓝牙功能')
      return
    }

    try {
      // 先设置回调
      setupDataParserCallbacks()

      patientMonitor = new BMPatientMonitor(dataParser, refreshBluetoothStatus)
      await patientMonitor.connect()
    } catch (error) {
      console.error('Connection error:', error)
      refreshBluetoothStatus('Connection failed: ' + error.message)
    }
  }

  // 开始 NIBP 测量
  const startNIBP = () => {
    if (patientMonitor) {
      patientMonitor.startNIBP()
    }
  }

  return {
    bluetoothStatus,
    isConnecting,
    vitalParams,
    waveformBuffers,
    connectDevice,
    startNIBP,
    initializeWaveforms,
    updateWaveforms,
    refreshBluetoothStatus
  }
}
