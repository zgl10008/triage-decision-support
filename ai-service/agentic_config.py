# -*- coding: utf-8 -*-
"""
阶段4：Agentic RAG 全局配置 + LLM 调用工具
================================================================
把「自适应 Agentic RAG」的全局安全限制、阈值、以及判断型 Agent 共用的 LLM 调用
集中到一处，与既有模块（rag_generator / app）一样从 config.ini 动态读取。

设计要点：
- 所有循环（重检索/重规划）必须有明确上限：MAX_RETRIEVAL_RETRY / MAX_REPLAN / MAX_AGENT_STEPS。
- 所有 LLM 调用必须有 timeout：AGENT_TIMEOUT（判断型 agent）/ LLM_TIMEOUT（通用）。
- 阈值与既有 [retrieval_service] hybrid_threshold=0.55 分层兼容（见 plan）。
- 判断型 Agent 的 LLM 输出一律走 robust JSON 解析（复用 multimodal_fusion.extract_json_object），
  失败即抛 ValueError，由上层降级兜底——绝不假定 LLM 输出一定合法。
"""
import configparser
import json
import os

import requests

# // ------------------------------
# // 配置加载（与既有模块一致：脚本同目录 config.ini）
# // ------------------------------
config = configparser.ConfigParser()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
config.read(os.path.join(CURRENT_DIR, 'config.ini'), encoding='utf-8')

# // 自适应管线默认模式
DEFAULT_PIPELINE = config.get('agentic_service', 'default_pipeline', fallback='baseline')

# // 全局安全限制
MAX_RETRIEVAL_RETRY = config.getint('agentic_service', 'max_retrieval_retry', fallback=1)
MAX_REPLAN = config.getint('agentic_service', 'max_replan', fallback=1)
MAX_AGENT_STEPS = config.getint('agentic_service', 'max_agent_steps', fallback=8)
AGENT_TIMEOUT = config.getint('agentic_service', 'agent_timeout', fallback=30)
LLM_TIMEOUT = config.getint('agentic_service', 'llm_timeout', fallback=30)
VERIFICATION_TIMEOUT = config.getint('agentic_service', 'verification_timeout', fallback=15)

# // 阈值（与 [retrieval_service] hybrid_threshold 分层兼容）
FAST_PATH_THRESHOLD = config.getfloat('agentic_service', 'fast_path_threshold', fallback=0.65)
FAST_PATH_GAP = config.getfloat('agentic_service', 'fast_path_gap', fallback=0.10)
EVIDENCE_LOW = config.getfloat('agentic_service', 'evidence_low', fallback=0.50)
CONFLICT_GAP = config.getfloat('agentic_service', 'conflict_gap', fallback=0.03)
HYBRID_THRESHOLD = config.getfloat('retrieval_service', 'hybrid_threshold', fallback=0.55)
TFIDF_THRESHOLD = config.getfloat('match_service', 'similarity_threshold', fallback=0.18)

# // Ollama 服务（与 rag_generator 同源配置）
OLLAMA_HOST = config.get('ollama_service', 'ipAddress')
OLLAMA_PORT = config.getint('ollama_service', 'port')
OLLAMA_API_PATH = config.get('ollama_service', 'api_path')
OLLAMA_MODEL_NAME = config.get('ollama_service', 'model_name')
NETWORK_HTTP_SCHEME = config.get('network_defaults', 'http_scheme')
OLLAMA_FULL_API_URL = f"{NETWORK_HTTP_SCHEME}://{OLLAMA_HOST}:{OLLAMA_PORT}{OLLAMA_API_PATH}"


def call_ollama(prompt, temperature=0.0, model_name=None, timeout=None, format_json=True):
    """调用 Ollama /api/generate，返回模型 response 文本。

    与 rag_generator._call_ollama 同构，但独立为模块级函数供各判断型 Agent 复用。
    失败（网络/超时/非200）向上抛异常，由调用方降级——判断型 Agent 从不假设 LLM 一定可用。
    """
    request_payload = {
        "model": model_name or OLLAMA_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if format_json:
        request_payload["format"] = "json"
    response = requests.post(
        OLLAMA_FULL_API_URL,
        json=request_payload,
        timeout=timeout or LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def parse_llm_json(text):
    """严格解析 LLM 输出为 dict；失败抛 ValueError（与 rag_generator._parse_json 同口径）。

    判断型 Agent 的 JSON 输出若无法解析，绝不静默假定空/默认值，而是抛出由上层降级。
    注意：不复用 multimodal_fusion.extract_json_object——它的第 4 级正则兜底对任意文本都会
    返回一个「空 schema 字典」（非 None），会掩盖 LLM 垃圾输出，不适合严格解析场景。
    """
    if not text:
        raise ValueError("LLM 返回为空")
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"无法从 LLM 输出中提取 JSON：{text[:200]}")
    return json.loads(text[start:end + 1])
