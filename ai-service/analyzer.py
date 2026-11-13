# //急救场景视觉分析服务（Flask）
# //功能：接收图片/视频 → 提取帧 → 调用通义千问VL大模型 → 返回伤情分析+急救建议
# //接口：/analyze 支持上传媒体文件并返回AI急救分析结果

# //导入Flask核心模块，用于创建Web服务、处理请求、返回JSON
import configparser
from flask import Flask, request, jsonify
import builtins
# //发送HTTP请求，调用阿里云大模型API
import requests
# //对图片/视频帧进行Base64编码
import base64
# //系统文件、路径操作工具
import os
import sys
import time
import threading
# //生成临时文件，存储上传的图片/视频
import tempfile
from concurrent.futures import ThreadPoolExecutor
from itertools import count
# //视频处理库，用于提取视频帧
import cv2
# //安全处理上传文件名，防止路径穿越攻击
from werkzeug.utils import secure_filename
# //解决跨域问题，允许前端页面调用接口
from flask_cors import CORS
# //从.env文件加载环境变量
from dotenv import load_dotenv
# //获取当前时间，用于日志打印
from datetime import datetime
# //多模态融合模块：实体归一化、RRF融合、冲突检测、视觉证据构造
import json
import multimodal_fusion as fusion

config = configparser.ConfigParser()
current_file_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(current_file_dir, 'config.ini')
config.read(config_file_path, encoding='utf-8')

# //加载环境变量配置：优先读取脚本同目录下的 .env（密钥文件已被 .gitignore 排除）
load_dotenv(os.path.join(current_file_dir, '.env'))

FLASK_HOST = config.get('analyzer_service', 'ipAddress')
FLASK_PORT = config.getint('analyzer_service', 'port')
FLASK_THREADED = config.getboolean('analyzer_service', 'threaded', fallback=True)
ANALYSIS_MAX_WORKERS = max(2, config.getint('analyzer_service', 'max_workers', fallback=4))
VL_MODEL_NAME = config.get('analyzer_service', 'vl_model_name', fallback='qwen-vl-plus')
NETWORK_ALL_INTERFACES_HOST = config.get('network_defaults', 'all_interfaces_host')
NETWORK_BROWSER_ACCESS_HOST = config.get('network_defaults', 'browser_access_host')
NETWORK_HTTP_SCHEME = config.get('network_defaults', 'http_scheme')
PRINT_FLASK_HOST = NETWORK_BROWSER_ACCESS_HOST if FLASK_HOST == NETWORK_ALL_INTERFACES_HOST else FLASK_HOST
LOG_LOCK = threading.Lock()
REQUEST_COUNTER = count(1)

def print(*args, **kwargs):
    console_encoding = getattr(getattr(sys, "stdout", None), "encoding", None) or "utf-8"
    safe_args = []
    for arg in args:
        if isinstance(arg, str):
            try:
                arg.encode(console_encoding)
            except UnicodeEncodeError:
                arg = arg.encode(console_encoding, errors="replace").decode(console_encoding)
        safe_args.append(arg)
    with LOG_LOCK:
        builtins.print(*safe_args, **kwargs)

# //初始化Flask应用实例
app = Flask(__name__)
# //启用跨域支持
CORS(app)
# //配置最大上传文件大小：10MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
ANALYSIS_EXECUTOR = ThreadPoolExecutor(
    max_workers=ANALYSIS_MAX_WORKERS,
    thread_name_prefix='analyzer-worker'
)

# //DashScope API 密钥：优先环境变量 DASHSCOPE_API_KEY，其次 config.ini；
# //两者均未配置时启动即报错，避免密钥硬编码进源码。
DASHSCOPE_API_KEY = (os.getenv('DASHSCOPE_API_KEY') or '').strip() or config.get('analyzer_service', 'dashscope_api_key', fallback='').strip()
if not DASHSCOPE_API_KEY:
    raise RuntimeError("未配置 DashScope API Key：请设置环境变量 DASHSCOPE_API_KEY，"
                       "或填写 config.ini 的 [analyzer_service] dashscope_api_key")

# //加载知识库伤情名称，用于视觉候选实体归一化（与 match 服务同一份 CSV）
INJURY_NAMES = fusion.load_injury_names()
print(f"✅ 知识库伤情名称加载成功：{len(INJURY_NAMES)} 类，用于视觉候选归一化")

# //阿里云通义千问VL模型的API请求地址
api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
# //API请求头：携带身份认证与数据格式信息
api_headers = {
    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
    "Content-Type": "application/json"
}

# //定义支持的图片文件格式集合
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
# //定义支持的视频文件格式集合
VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm'}

def image_to_base64(image_path):
    """图片转 Base64 编码（带 data URL 前缀）
    :param image_path: 图片本地路径
    :return: 标准 data:image/xxx;base64,xxx 格式字符串
    """
    # //以二进制方式读取图片文件
    with open(image_path, 'rb') as f:
        data = f.read()
    # //进行Base64编码并转为字符串
    b64 = base64.b64encode(data).decode('utf-8')
    # //获取文件后缀名，用于设置MIME类型
    ext = os.path.splitext(image_path)[1].lower().lstrip('.')
    # //统一jpg/jpeg的MIME类型，其他格式直接使用后缀
    mime = 'image/jpeg' if ext in ['jpg', 'jpeg'] else f'image/{ext}'
    # //返回带协议头的Base64字符串
    return f"data:{mime};base64,{b64}"


def extract_video_frames(video_path, max_frames=5):
    #//从视频中均匀提取关键帧（自动转为 Base64）
    #//:param video_path: 视频路径
    #//:param max_frames: 最大提取帧数
    #//:return: 帧 Base64 列表
    # //存储所有帧的Base64编码
    frames_base64 = []
    # //打开视频文件
    cap = cv2.VideoCapture(video_path)
    # //获取视频总帧数
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # //视频无帧，直接返回空列表
    if total_frames == 0:
        cap.release()
        return []

    # //均匀计算需要提取的帧位置
    frame_indices = [int(total_frames * i / max_frames) for i in range(max_frames)]

    # //遍历帧位置，逐帧提取
    for idx in frame_indices:
        # //设置读取位置
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        # //读取帧
        ret, frame = cap.read()
        if ret:
            # //将帧编码为JPG格式
            _, buffer = cv2.imencode('.jpg', frame)
            # //转为Base64
            b64 = base64.b64encode(buffer).decode('utf-8')
            # //加入结果列表
            frames_base64.append(f"data:image/jpeg;base64,{b64}")

    # //释放视频资源
    cap.release()
    return frames_base64


def analyze_with_qwen_vl(image_base64_list=None, request_id=None):
    #//调用通义千问 VL 大模型进行急救场景分析
    #//:param image_base64_list: 图片/视频帧 Base64 列表
    #//:return: 模型返回的急救分析文本
    # //构造消息内容列表
    content = []

    # //如果有图片，加入到请求内容中
    if image_base64_list:
        for img_b64 in image_base64_list:
            content.append({"type": "image_url", "image_url": {"url": img_b64}})

    # //加入结构化提示词，约束模型只输出 JSON（含伤情候选、部位、严重度、可见症状）
    content.append({
        "type": "text",
        "text": fusion.VLM_STRUCTURED_PROMPT
    })

    # //构造完整的API请求体
    data = {
        "model": VL_MODEL_NAME,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"}
    }

    request_prefix = f"[请求 {request_id}] " if request_id is not None else ""
    thread_name = threading.current_thread().name

    # //控制台打印请求日志，便于调试
    print("\n" + "=" * 60)
    print(f"{request_prefix}请求时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{request_prefix}执行线程：{thread_name}")
    print(f"{request_prefix}图片数量：{len(image_base64_list) if image_base64_list else 0}")
    print(f"{request_prefix}发送请求到 DashScope API...")
    print("=" * 60)

    # //发送POST请求到模型API，设置超时时间120秒
    response = requests.post(api_url, headers=api_headers, json=data, timeout=120)
    response.raise_for_status()
    # //解析响应为JSON
    result = response.json()

    # //打印响应状态码
    print(f"\n{request_prefix}API 响应状态码：{response.status_code}")

    # //解析模型返回结果
    if 'choices' in result and result['choices']:
        # //获取模型返回的文本内容
        analysis_result = result['choices'][0]['message']['content']

        # //控制台打印模型返回结果
        print("\n" + "=" * 60)
        print(f"{request_prefix}大模型识别结果：")
        print("=" * 60)
        print(analysis_result)
        print("=" * 60 + "\n")

        return analysis_result
    else:
        # //模型返回异常
        print(f"\n{request_prefix}模型返回异常：{result}")
        return "模型未返回有效内容"


def process_analysis_file(temp_path, is_image, request_id):
    #//在线程池中执行实际的媒体分析任务。"""
    if is_image:
        print(f"[请求 {request_id}] 文件类型：图片")
        image_b64 = image_to_base64(temp_path)
        analysis_text = analyze_with_qwen_vl(image_base64_list=[image_b64], request_id=request_id)
    else:
        print(f"[请求 {request_id}] 文件类型：视频")
        frames = extract_video_frames(temp_path, max_frames=5)
        if not frames:
            raise ValueError("视频帧提取失败")

        print(f"[请求 {request_id}] 提取帧数：{len(frames)}")
        analysis_text = analyze_with_qwen_vl(image_base64_list=frames, request_id=request_id)

    # //结构化解析 + 候选实体归一化，生成可供 RAG 检索/生成融合的视觉证据
    parsed = fusion.extract_json_object(analysis_text)
    visual_evidence = fusion.build_visual_evidence(parsed, INJURY_NAMES, raw_text=analysis_text)
    print(f"[请求 {request_id}] 结构化证据：{json.dumps(visual_evidence, ensure_ascii=False)}")
    return {"analysis": analysis_text, "visual_evidence": visual_evidence}


@app.route('/analyze', methods=['POST'])
def analyze():
    #//文件上传与急救分析主接口
    #//接收：图片/视频文件
    #//返回：success + analysis 分析结果
    # //检查请求中是否包含文件
    if 'file' not in request.files:
        return jsonify({"error": "缺少文件", "success": False}), 400

    # //获取上传的文件对象
    file = request.files['file']
    # //安全处理文件名
    filename = secure_filename(file.filename)
    # //获取文件后缀名
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    # //判断文件是否为图片或视频
    is_image = ext in IMAGE_EXTENSIONS
    is_video = ext in VIDEO_EXTENSIONS

    # //不支持的文件类型，返回错误
    if not (is_image or is_video):
        return jsonify({"error": "不支持的文件类型", "success": False}), 400

    request_id = next(REQUEST_COUNTER)
    start_time = time.time()

    # //打印接收文件信息
    print(f"\n[请求 {request_id}] 收到文件：{filename} ({ext})")

    # //创建临时文件保存上传内容
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        file.save(tmp.name)
        temp_path = tmp.name

    try:
        future = ANALYSIS_EXECUTOR.submit(process_analysis_file, temp_path, is_image, request_id)
        result = future.result()
        duration = time.time() - start_time
        print(f"[请求 {request_id}] 处理完成，耗时：{duration:.2f} 秒")

        # //返回成功结果（analysis 为规范字段，rescue_advice 兼容前端现有读取逻辑；
        # //visual_evidence 为结构化视觉证据，供 RAG 检索/生成融合使用）
        return jsonify({
            "success": True,
            "analysis": result["analysis"],
            "rescue_advice": result["analysis"],
            "visual_evidence": result["visual_evidence"]
        })

    except Exception as e:
        # //捕获处理过程中的异常
        print(f"[请求 {request_id}] 处理异常：{str(e)}")
        return jsonify({"error": str(e), "success": False}), 500

    finally:
        # //无论是否异常，最终都清理临时文件
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                print(f"[请求 {request_id}] 临时文件已清理：{temp_path}")
        except PermissionError:
            #// 文件被占用时，等待后重试删除
            time.sleep(0.5)
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except:
                pass


if __name__ == '__main__':
    # //启动服务时打印控制台信息
    print("\n" + "=" * 60)
    print("🚀 急救分析服务已启动")
    print(f"并发模式：threaded={FLASK_THREADED}, max_workers={ANALYSIS_MAX_WORKERS}")
    print("=" * 60 + "\n")
    # //启动Flask服务，允许所有IP访问，端口6800
    print(f"服务监听地址：{FLASK_HOST}:{FLASK_PORT}")
    print(f"接口地址：{NETWORK_HTTP_SCHEME}://{PRINT_FLASK_HOST}:{FLASK_PORT}/analyze")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=FLASK_THREADED)
