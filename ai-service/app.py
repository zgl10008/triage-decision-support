# -*- coding: utf-8 -*-
# // ==============================================================================
# // 灾害现场伤情智能匹配与急救处置服务
# // 所有 IP / 端口 / URL / 配置参数从 config.ini 读取。

# // 功能概述：
# // 1. 加载创伤医疗知识库CSV文件，构建TF-IDF特征矩阵
# // 2. 接收用户伤情描述，通过余弦相似度匹配最相关的伤情类型
# // 3. 聚合匹配伤情的三元组医疗知识，调用本地DeepSeek大模型
# // 4. 生成标准化现场急救处置步骤，通过Flask接口返回结果
# // 5. 基于gevent实现高并发WSGI服务器，支持多客户端同时请求
# // 接口说明：
# // - POST /match：核心接口，提交伤情描述，返回匹配结果+急救处置方案
# // - GET /health：健康检查接口，用于服务监控、存活探针
# // 技术栈：Flask + gevent + pandas + scikit-learn + requests + configparser
# // ==============================================================================

# // ------------------------------
# // 1. 配置文件解析
# // ------------------------------
# // 导入配置文件解析器
import configparser
# // 导入os库：处理文件绝对路径，避免相对路径读取失败，无硬编码路径
import os
import builtins
# // 导入numpy库：用于数值计算、相似度排序、矩阵操作
import numpy as np
# // 导入pandas库：用于读取和处理CSV格式的医疗知识库
import pandas as pd
# // 导入TF-IDF向量器：用于伤情文本的特征向量化
from sklearn.feature_extraction.text import TfidfVectorizer
# // 导入余弦相似度计算：用于匹配用户输入与知识库伤情
from sklearn.metrics.pairwise import cosine_similarity
# // 导入Flask核心模块：创建Web服务、处理HTTP请求、返回JSON响应
from flask import Flask, request, jsonify
# // 导入跨域处理库：解决前端页面跨域调用接口的问题
from flask_cors import CORS
# // 导入gevent高并发WSGI服务器：替代Flask内置开发服务器，支持生产环境高并发
from gevent.pywsgi import WSGIServer
# // 导入requests库：用于调用本地Ollama大模型API
import requests
# // 导入异常处理模块：优化异常捕获与友好提示
import traceback
import sys
import time
# // 导入多模态融合模块：视觉证据归一化、RRF融合、冲突检测、证据prompt构造
import multimodal_fusion as fusion
# // 导入阶段3 grounded 生成模块：引用溯源 + 结构化输出 + 双层忠实度校验
from rag_generator import GroundedGenerator

# // ------------------------------
# // 动态读取配置

# // ------------------------------
# // 初始化配置解析器实例
config = configparser.ConfigParser()
# // 获取当前脚本所在目录的绝对路径，避免相对路径导致的配置文件读取失败
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# // 拼接config.ini的绝对路径，确保任何工作目录下都能正确读取配置
config_file_path = os.path.join(current_file_dir, 'config.ini')
# // 读取配置文件，指定utf-8编码避免中文乱码
config.read(config_file_path, encoding='utf-8')

# // ------------------------------
# // 服务核心配置动态读取（无任何硬编码）
# // ------------------------------
# // 1. Web 服务配置：从 match_service 段读取 IP 和端口
FLASK_HOST = config.get('match_service', 'ipAddress')
FLASK_PORT = config.getint('match_service', 'port')
# // 2. 知识库配置：动态读取CSV文件路径、相似度阈值、最大返回行数
KNOWLEDGE_FILE_PATH = config.get('match_service', 'knowledge_file_path')
SIMILARITY_THRESHOLD = config.getfloat('match_service', 'similarity_threshold')
MATCH_MARGIN = config.getfloat('match_service', 'match_margin')
TOP_K = config.getint('match_service', 'top_k')
NAME_WEIGHT = config.getfloat('match_service', 'name_weight')
MAX_ADVICE_LINES = config.getint('match_service', 'max_advice_lines')
# // 3. Ollama大模型配置：动态读取IP、端口、API路径、模型名、超时时间，无硬编码
OLLAMA_HOST = config.get('ollama_service', 'ipAddress')
OLLAMA_PORT = config.getint('ollama_service', 'port')
OLLAMA_API_PATH = config.get('ollama_service', 'api_path')
OLLAMA_MODEL_NAME = config.get('ollama_service', 'model_name')
OLLAMA_TIMEOUT = config.getint('ollama_service', 'request_timeout')
# // 5. 混合检索配置（阶段2）：检索模式、hybrid 判定阈值、索引/模型路径
RETRIEVAL_MODE = config.get('retrieval_service', 'mode')
HYBRID_THRESHOLD = config.getfloat('retrieval_service', 'hybrid_threshold')
RETRIEVAL_INDEX_PATH = config.get('retrieval_service', 'index_path')
RETRIEVAL_MODEL_PATH = config.get('retrieval_service', 'model_path')
# // 4. 网络公共配置：统一管理监听地址、回环访问地址与协议前缀，避免固定地址字面量
NETWORK_ALL_INTERFACES_HOST = config.get('network_defaults', 'all_interfaces_host')
NETWORK_LOOPBACK_HOST = config.get('network_defaults', 'loopback_host')
NETWORK_HTTP_SCHEME = config.get('network_defaults', 'http_scheme')
# // 动态拼接Ollama完整API地址，全程无硬编码IP/端口/路径
OLLAMA_FULL_API_URL = f"{NETWORK_HTTP_SCHEME}://{OLLAMA_HOST}:{OLLAMA_PORT}{OLLAMA_API_PATH}"
# // 控制台打印地址适配：监听全部网卡时，使用回环地址作为本机访问提示
PRINT_ACCESS_HOST = NETWORK_LOOPBACK_HOST if FLASK_HOST == NETWORK_ALL_INTERFACES_HOST else FLASK_HOST

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
    kwargs.setdefault("flush", True)
    builtins.print(*safe_args, **kwargs)

# // ------------------------------
# // RAG 全流程调试打印（观察链路用，置 RAG_TRACE=False 可整体关闭）
# // 覆盖：检索召回 → 匹配判定 → 知识聚合 → 生成/忠实度
# // ------------------------------
RAG_TRACE = True


def _trace_banner(title):
    # // 每次请求开头打印分隔横幅，便于区分多请求
    if not RAG_TRACE:
        return
    print("")
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _trace_line(label, value=""):
    # // 统一缩进的单行追踪输出
    if not RAG_TRACE:
        return
    print(f"  {label} {value}".rstrip())

# // ------------------------------
# // Flask服务初始化
# // ------------------------------
# // 初始化Flask应用实例
app = Flask(__name__)
# // 配置全局跨域规则：允许所有来源访问所有接口，适配前端多场景调用
CORS(app, resources={r"/*": {"origins": "*"}})

# // ------------------------------
# // 全局变量声明：存储向量化器、TF-IDF矩阵、原始知识库数据
# // 服务启动时一次性加载，避免每次请求重复加载导致的性能损耗
# // ------------------------------
vectorizer = None
tfidf_matrix = None
name_vectorizer = None
name_tfidf_matrix = None
original_df = None
injury_names = None
# // 阶段3 grounded 生成器实例（服务启动时初始化，加载 kb_records.json）
grounded_generator = None
# // 阶段2 混合检索器实例（BGE-M3 dense+char-TF-IDF 两路 RRF，BM25 已按消融结论关闭；加载失败回退字符级 TF-IDF）
hybrid_retriever = None
# // 阶段4 自适应 Agentic RAG 编排器实例（懒加载，首次 /agentic 请求时构建）
agentic_router = None


# // ============================================================
# // 核心工具函数：模型与知识库加载
# // 功能：服务启动时一次性加载CSV知识库，训练TF-IDF向量器，构建特征矩阵
# // ============================================================
def clean_kb_text(value):
    # //
    # // 知识库字段规范化：去掉 BOM、首尾空白、空值占位，
    # // 并清理历史合并残留的元组引号（如 ('XX' / XX')）。
    # //
    if value is None:
        return ''
    text = str(value).replace('\ufeff', '').strip()
    if text == 'nan':
        return ''
    if text.startswith("('"):
        text = text[2:]
    if text.endswith("')"):
        text = text[:-2]
    return text.strip()


def is_blank_text(text):
    # // 判断规范化后的文本是否只剩标点/空壳（用于丢弃无效行）
    return text.strip("()'，。、, ") == ''


def load_model_and_knowledge():
    # //
    # // 加载创伤知识库与TF-IDF向量化模型
    # // 设计：服务启动时单次调用，全局变量存储，避免重复IO和计算。
    # // 索引口径：以“去重伤情”为粒度，每类伤情把名称+全部分类/描述拼成
    # // 一个文档，使症状类描述也能参与匹配，而不是只匹配伤情名称列。
    # // 异常：文件不存在、读取失败时抛出明确异常，终止服务启动
    # //
    # // 声明使用全局变量
    global vectorizer, tfidf_matrix, name_vectorizer, name_tfidf_matrix, original_df, injury_names, grounded_generator, hybrid_retriever

    # // 拼接知识库文件的绝对路径，避免相对路径读取失败
    knowledge_full_path = os.path.join(current_file_dir, KNOWLEDGE_FILE_PATH)

    # // 前置校验：检查知识库文件是否存在
    if not os.path.exists(knowledge_full_path):
        raise FileNotFoundError(f"创伤知识库文件不存在：{knowledge_full_path}，请检查配置文件路径")

    # // 读取CSV：第一行作为表头（header=0），避免把表头当成知识记录
    original_df = pd.read_csv(knowledge_full_path, header=0, encoding='utf-8')
    # // 全字段规范化：去 BOM、去空白、清理历史合并残留的元组引号
    original_df = pd.DataFrame({col: original_df[col].map(clean_kb_text) for col in original_df.columns})
    # // 丢弃无效行：伤情名称或具体描述为空
    original_df = original_df[
        (original_df.iloc[:, 0] != '') &
        (~original_df.iloc[:, 2].map(is_blank_text))
    ].reset_index(drop=True)

    # // 获取去重后的伤情列表，作为索引粒度
    injury_names = original_df.iloc[:, 0].drop_duplicates().tolist()
    # // 每类伤情聚合一个检索文档：伤情名称 + 该伤情下所有具体描述
    # // （不拼接“分类”词，避免“临床特点/现场急救”等通用词稀释分数）
    injury_documents = []
    for name in injury_names:
        group = original_df[original_df.iloc[:, 0] == name]
        doc_parts = [name]
        for _, row in group.iterrows():
            if row.iloc[2]:
                doc_parts.append(row.iloc[2])
        injury_documents.append(' '.join(doc_parts))

    # // 通道1：伤情名称索引（短文本，精确/规范术语匹配强）
    name_vectorizer = TfidfVectorizer(
        analyzer='char',
        ngram_range=(1, 2),
        lowercase=False
    )
    name_vectorizer.fit(injury_names)
    name_tfidf_matrix = name_vectorizer.transform(injury_names)

    # // 通道2：聚合文档索引（名称+分类+描述，症状类表达匹配强）
    vectorizer = TfidfVectorizer(
        analyzer='char',
        ngram_range=(1, 2),
        lowercase=False
    )
    vectorizer.fit(injury_documents)
    tfidf_matrix = vectorizer.transform(injury_documents)

    # // 打印加载成功日志，输出关键指标
    print(f"✅ 创伤知识库加载成功：有效 {len(original_df)} 行数据，去重伤情类型 {len(injury_names)}，"
          f"名称通道维度 {name_tfidf_matrix.shape[1]}，描述通道维度 {tfidf_matrix.shape[1]}")

    # // 初始化阶段3 grounded 生成器：加载 kb_records.json（含 source_id + field_type 分层）
    grounded_generator = GroundedGenerator()
    print(f"✅ 阶段3 grounded 生成器就绪（知识条目 {len(grounded_generator._load_records())} 条）")

    # // 初始化阶段2 混合检索器：BGE-M3 三路 RRF（dense+sparse+char-TF-IDF）
    # // 加载失败（模型缺失/无 GPU 等）时回退字符级 TF-IDF，服务不中断
    hybrid_retriever = None
    if RETRIEVAL_MODE == 'hybrid':
        try:
            from FlagEmbedding import BGEM3FlagModel
            from rag_retriever import HybridRetriever
            # // 本地模型存在则用本地路径，否则回退 HuggingFace 在线加载
            index_full_path = os.path.join(current_file_dir, RETRIEVAL_INDEX_PATH)
            model_full_path = os.path.join(current_file_dir, RETRIEVAL_MODEL_PATH)
            model_path = model_full_path if os.path.exists(os.path.join(model_full_path, 'config.json')) else 'BAAI/bge-m3'
            embed_model = BGEM3FlagModel(model_path, use_fp16=True)
            hybrid_retriever = HybridRetriever.load(index_full_path, embed_model)
            print(f"✅ 阶段2 BGE-M3 混合检索器就绪（模式={RETRIEVAL_MODE}，阈值={HYBRID_THRESHOLD}）")
        except Exception as e:
            hybrid_retriever = None
            print(f"⚠️ BGE-M3 混合检索器加载失败，回退字符级 TF-IDF：{e}")


# // ============================================================
# // 检索与判定函数
# // 功能：Top-K 候选召回 + 阈值/分数差双条件判定，供接口与评测复用
# // ============================================================
def retrieve_candidates(input_text, top_k=None):
    # //
    # // 返回 Top-K 候选列表：[{"injury": 伤情名, "score": 相似度}, ...]
    # //
    if top_k is None:
        top_k = TOP_K
    # // 混合检索模式（阶段2）：BGE-M3 dense+char-TF-IDF 两路 RRF（BM25 已关闭）
    # // score 为 dense 语义相似度（[0,1]，供阈值判定），排序由 RRF 融合分决定
    if hybrid_retriever is not None:
        results = hybrid_retriever.retrieve(input_text, top_k=top_k, recall_n=100)
        _trace_line("[1/4 检索召回]", f"模式=hybrid（BGE-M3 dense+char-TF-IDF 两路 RRF） top_k={top_k}")
        for rank, r in enumerate(results, 1):
            _trace_line(f"    候选#{rank}", f"{r['injury']} | rrf={r.get('rrf', 0.0)} | dense 相似度={r['score']}")
        return [
            {"injury": r["injury"], "score": r["score"], "retrieval_mode": "hybrid"}
            for r in results
        ]
    # // 回退：字符级 TF-IDF 双通道打分（名称通道权重 NAME_WEIGHT，描述通道权重 1-NAME_WEIGHT）
    name_vector = name_vectorizer.transform([input_text])
    name_scores = cosine_similarity(name_vector, name_tfidf_matrix).flatten()
    doc_vector = vectorizer.transform([input_text])
    doc_scores = cosine_similarity(doc_vector, tfidf_matrix).flatten()
    combined_scores = NAME_WEIGHT * name_scores + (1.0 - NAME_WEIGHT) * doc_scores
    top_indices = np.argsort(combined_scores)[::-1][:top_k]
    candidates = []
    for idx in top_indices:
        candidates.append({
            "injury": injury_names[idx],
            "score": round(float(combined_scores[idx]), 4),
            "retrieval_mode": "tfidf"
        })
    _trace_line("[1/4 检索召回]", f"模式=tfidf（字符级双通道，回退） top_k={top_k}")
    for rank, c in enumerate(candidates, 1):
        _trace_line(f"    候选#{rank}", f"{c['injury']} | 余弦={c['score']}")
    return candidates


def decide_match(candidates):
    # //
    # // 双条件拒答：
    # // 1) Top-1 相似度低于阈值 → 判为“知识库中无匹配”；
    # // 2) Top-1 与 Top-2 分数差过小 → 判为“候选歧义”，宁可不答也不硬给错误方案。
    # //
    if not candidates:
        return {"matched": False, "reason": "no_candidates"}
    best = candidates[0]
    # // 混合检索用 dense 相似度阈值（0.55，实证标定）；tfidf 用余弦阈值（0.18）
    threshold = HYBRID_THRESHOLD if hybrid_retriever is not None else SIMILARITY_THRESHOLD
    _trace_line("[2/4 匹配判定]", f"阈值={threshold} | top1分数={best['score']}")
    if best["score"] < threshold:
        _trace_line("    →", "拒答（below_threshold，低于阈值）")
        return {"matched": False, "reason": "below_threshold", "score": best["score"]}
    # // 分数差歧义判定：仅 tfidf 模式启用——
    # // hybrid 模式 RRF 排序与 dense 相似度非同源（dense gap 会出现负值），
    # // 且 RRF gap 量级过小无区分度，故 hybrid 模式仅用阈值单条件判定。
    if hybrid_retriever is None and len(candidates) >= 2 and (best["score"] - candidates[1]["score"]) < MATCH_MARGIN:
        _trace_line("    →", f"拒答（ambiguous，分数差 {round(best['score'] - candidates[1]['score'], 4)} < {MATCH_MARGIN}）")
        return {
            "matched": False,
            "reason": "ambiguous",
            "score": best["score"],
            "gap": round(best["score"] - candidates[1]["score"], 4)
        }
    _trace_line("    →", f"命中：{best['injury']}（score={best['score']}）")
    return {"matched": True, "injury": best["injury"], "score": best["score"]}



# // ============================================================
# // 大模型调用函数：本地Ollama DeepSeek模型
# // 功能：格式化医疗知识三元组，构造专业提示词，调用大模型生成急救处置步骤
# // ============================================================
def call_deepseek_model(triples, visual_evidence=None):
    # //
    # // 调用本地Ollama部署的DeepSeek大模型，生成伤情急救处置步骤
    # // 参数：
    # // triples (list): 匹配到的伤情三元组列表，每个元素为[伤情名称, 属性, 值]
    # // 返回：
    # // list: 格式化后的处置步骤列表，每行一个步骤；调用失败返回错误提示列表
    # //
    try:
        # // 前置校验：三元组数据不能为空
        if not triples or len(triples) == 0:
            return ["无匹配的伤情知识，无法生成处置方案"]

        # // 提取当前伤情名称，用于提示词构造
        injury_name = triples[0][0]
        # // 格式化三元组知识为易读文本，过滤不完整的三元组
        triples_formatted_text = "\n".join([f"- {item[1]}：{item[2]}" for item in triples if len(item) >= 3])

        # // 构造灾害现场医疗专家提示词：严格限定输出格式，确保结果简洁、专业、可执行
        prompt = f"""
你是一名拥有丰富现场救援经验的灾害现场医疗急救专家，精通灾害现场环境下的伤情紧急处置。

【当前伤情名称】
{injury_name}

【该伤情的专业医疗知识】
{triples_formatted_text}
"""
        # //多模态融合：若存在现场观察证据（视频/图像分析），注入生成阶段
        evidence_block = fusion.build_visual_evidence_block(visual_evidence)
        if evidence_block:
            prompt += f"\n{evidence_block}\n"

        prompt += """
请直接输出【现场急救处置步骤】，要求：
1. 分条编号输出，简洁准确，符合现场急救优先级
2. 只输出处置步骤，不要标题、不要多余解释、不要客套话
3. 步骤符合灾害现场环境，优先保命、止血、防感染，可执行性强
4. 结合“现场观察证据”与“专业医疗知识”，证据与知识冲突时以专业医疗知识为准并提示需要人工复核
"""

        # // 构造Ollama API请求参数，全部从配置动态读取，无硬编码
        request_payload = {
            "model": OLLAMA_MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }

        # // 发送POST请求到本地Ollama服务，超时时间从配置动态读取
        response = requests.post(
            OLLAMA_FULL_API_URL,
            json=request_payload,
            timeout=OLLAMA_TIMEOUT
        )
        # // 校验HTTP请求状态，非200状态直接抛出异常
        response.raise_for_status()
        # // 解析JSON响应，提取模型生成的文本内容，去除首尾空白字符
        result_text = response.json().get("response", "").strip()
        # // 按行分割文本，过滤空行，清理每行首尾空白字符
        step_lines = [line.strip() for line in result_text.splitlines() if line.strip()]

        # // 返回格式化后的处置步骤
        return step_lines

    # // 捕获所有异常，打印详细错误日志，返回友好提示，避免服务崩溃
    except Exception as e:
        print(f"❌ 大模型调用失败：{str(e)}")
        print(f"❌ 详细错误堆栈：{traceback.format_exc()}")
        return ["大模型服务请求异常，请检查Ollama服务是否启动、模型是否正确加载"]


# // ============================================================
# // 多模态融合辅助函数：视觉证据 → 检索融合判定
# // ============================================================
def _fuse_visual(text_candidates, text_decision, visual_evidence):
    """视觉证据融合：RRF 排序 + 一致性判定 + 视觉兜底匹配。

    设计：
    - 文本检索是骨架：文本判定通过时沿用文本 Top1，视觉用于佐证与冲突提示；
    - 文本拒答时，若视觉候选置信度足够高（>= fusion_service.visual_hit_threshold），
      由视觉证据兜底给出结论（source=visual）；
    - 文本与视觉 Top1 冲突时标记 needs_review，由人工复核，不硬答。

    参数：
        text_candidates: 文本 TF-IDF Top-K 候选
        text_decision: decide_match 的原始判定
        visual_evidence: 视觉分析服务返回的结构化证据（含 injury_candidates）
    返回：
        {"decision": 融合后的判定, "fusion": 融合元信息}
    """
    vis_candidates = [
        {"name": str(c.get("name", "")).strip(), "confidence": float(c.get("confidence", 0.0))}
        for c in (visual_evidence.get("injury_candidates") or [])
        if str(c.get("name", "")).strip()
    ]
    if not vis_candidates:
        return {"decision": text_decision, "fusion": None}

    conflict = fusion.conflict_detect(text_candidates, vis_candidates)
    fused_ranking = fusion.fuse_by_rrf(text_candidates, vis_candidates)

    decision = dict(text_decision)
    if text_decision["matched"]:
        # //文本主判决成立：沿用文本 Top1，冲突时仅标记人工复核
        source = "text"
    else:
        # //文本拒答：视觉置信度足够高时由视觉兜底
        vis_top = vis_candidates[0]
        if vis_top["confidence"] >= fusion.VISUAL_HIT_THRESHOLD:
            decision = {
                "matched": True,
                "injury": vis_top["name"],
                "score": vis_top["confidence"],
                "source": "visual",
            }
            source = "visual"
        else:
            decision["source"] = "none"
            source = "none"

    if decision.get("matched"):
        decision["source"] = source

    fusion_info = {
        "enabled": True,
        "source": source,
        "text_top": text_candidates[0] if text_candidates else None,
        "visual_top": vis_candidates[0],
        "consistent": conflict["consistent"],
        "needs_review": conflict["needs_review"],
        "reason": conflict["reason"],
        "fused_ranking": fused_ranking[:TOP_K],
    }
    return {"decision": decision, "fusion": fusion_info}


# // ============================================================
# // 匹配解析辅助函数：Top-K 召回 + 双条件判定 + 多模态融合
# // 供 /match 与 /match/v2 复用，避免重复逻辑
# // ============================================================
def _resolve_match(input_injury_text, visual_evidence):
    """解析请求 → (candidates, decision, fusion_info)。"""
    _trace_banner(f"[RAG 流程] 文本查询：{input_injury_text or '(纯视觉)'}")
    # // 步骤1：Top-K 候选召回
    candidates = retrieve_candidates(input_injury_text) if input_injury_text else []
    # // 步骤2：阈值 + 分数差双条件判定
    decision = decide_match(candidates)
    # // 步骤2.5：多模态融合——请求携带视觉证据（视频/图像分析结果）时进入融合链路
    has_visual_candidates = bool(visual_evidence and visual_evidence.get('injury_candidates'))
    fusion_info = None
    if has_visual_candidates:
        _trace_line("[融合]", "检测到视觉证据，进入多模态融合链路")
        fused = _fuse_visual(candidates, decision, visual_evidence)
        decision = fused['decision']
        fusion_info = fused['fusion']
        if fusion_info:
            _trace_line("    →", f"来源={fusion_info.get('source')} | 一致性={fusion_info.get('consistent')} | needs_review={fusion_info.get('needs_review')}")
    return candidates, decision, fusion_info


# // ============================================================
# // Flask API 接口定义
# // ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    # //
    # // 健康检查接口
    # // 用途：服务监控、负载均衡健康检查、K8s容器存活/就绪探针
    # // 返回：
    # // JSON: 包含服务状态、知识库加载情况、时间戳
    # // HTTP状态码：200（正常）
    # //
    return jsonify({
        "status": "healthy",
        "message": "灾害现场伤情智能匹配服务运行正常",
        "knowledge_total_rows": len(original_df) if original_df is not None else 0,
        "injury_types": len(injury_names) if injury_names is not None else 0,
        "model_loaded": vectorizer is not None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }), 200


@app.route('/match', methods=['POST'])
def injury_match_and_advice():
    # //
    # // 核心业务接口：伤情匹配 + 急救方案生成
    # // 接口规范：
    # // - 请求方式：POST
    # // - 请求格式：JSON
    # // - 请求参数：
    # // {
    # // "text": "用户输入的伤情描述文本（必填）"
    # // }
    # // - 返回格式：JSON，包含查询内容、匹配伤情、急救处置步骤
    # //
    try:
        # // 前置校验1：模型和知识库未加载完成，返回503服务不可用
        if vectorizer is None or tfidf_matrix is None or original_df is None:
            return jsonify({
                "success": False,
                "error": "模型和知识库正在加载中，请稍后重试"
            }), 503

        # // 获取前端传入的JSON数据，silent=True避免解析失败抛出异常
        request_data = request.get_json(silent=True)
        # // 前置校验2：请求数据为空，返回400参数错误
        if not request_data:
            return jsonify({
                "success": False,
                "error": "请求参数格式错误，请使用JSON格式提交"
            }), 400

        # // 提取用户输入的伤情描述，去除首尾空白字符
        input_injury_text = request_data.get('text', '').strip()
        # // 提取视觉证据（视频/图像分析结果），文本与视觉至少提供一个
        visual_evidence = request_data.get('visual') or {}
        has_visual_candidates = bool(visual_evidence and visual_evidence.get('injury_candidates'))
        # // 前置校验3：文本与视觉候选均为空，返回400参数错误
        if not input_injury_text and not has_visual_candidates:
            return jsonify({
                "success": False,
                "error": "请输入伤情描述文本，或提供视觉分析结果"
            }), 400

        # // 步骤1~2.5：Top-K 召回 + 双条件判定 + 多模态融合（复用辅助函数）
        candidates, decision, fusion_info = _resolve_match(input_injury_text, visual_evidence)

        # // 前置校验4：未通过判定，返回404，不硬给错误方案
        if not decision["matched"]:
            response_body = {
                "success": False,
                "error": "未在知识库中找到足够匹配的伤情类型，请补充或调整描述后重试",
                "reason": decision.get("reason")
            }
            if fusion_info:
                response_body["fusion"] = fusion_info
            return jsonify(response_body), 404

        # // 步骤3：提取匹配到的伤情实体名称
        matched_injury_entity = decision["injury"]
        best_match_score = decision["score"]
        # // 步骤5：聚合该伤情对应的所有三元组知识，填充空值
        related_knowledge_triples = original_df[
            original_df.iloc[:, 0] == matched_injury_entity
        ].fillna('').values.tolist()
        _trace_line("[3/4 知识聚合]", f"匹配伤情「{matched_injury_entity}」→ 聚合三元组 {len(related_knowledge_triples)} 条")
        # // 步骤6：调用大模型生成急救处置步骤（存在视觉证据时注入现场观察证据）
        rescue_advice_steps = call_deepseek_model(
            related_knowledge_triples,
            visual_evidence=visual_evidence if fusion_info else None
        )
        _trace_line("[4/4 生成]", f"LLM 产出 {len(rescue_advice_steps)} 步，返回前 {min(len(rescue_advice_steps), MAX_ADVICE_LINES)} 条")

        # // 构造标准化返回结果，限制最大返回行数
        response_body = {
            "success": True,
            "query": input_injury_text,
            "matched_injury": matched_injury_entity,
            "similarity_score": round(float(best_match_score), 4),
            "candidates": candidates,
            "rescue_advice": rescue_advice_steps[:MAX_ADVICE_LINES]
        }
        if fusion_info:
            response_body["fusion"] = fusion_info
        return jsonify(response_body), 200

    # // 全局异常捕获：捕获所有未处理的异常，返回友好提示，避免服务崩溃
    except Exception as e:
        print(f"❌ 接口处理异常：{str(e)}")
        print(f"❌ 详细错误堆栈：{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"服务内部异常：{str(e)}"
        }), 500


@app.route('/match/v2', methods=['POST'])
def injury_match_and_advice_v2():
    # //
    # // 阶段3 grounded 生成接口：结构化 + 引用溯源 + 双层忠实度校验
    # // 与 /match 共用同一条检索判定链路（_resolve_match），生成环节升级：
    # //   - steps 每步带 citations（引用编号）
    # //   - sources 把编号映射回 source_id，实现"建议→源头"可追溯
    # //   - faithfulness 双层忠实度（lexical grounding + LLM-as-judge）
    # // 请求参数：
    # // {
    # //   "text": "用户输入的伤情描述文本（必填）",
    # //   "mode": "grounded|llm"（可选，默认 grounded，确定性零幻觉）
    # //   "with_judge": true|false（可选，默认 llm 为 true，grounded 为 false）
    # //   "visual": {...}（可选，视觉分析结果）
    # // }
    # //
    try:
        # // 前置校验1：模型、知识库、grounded 生成器未就绪，返回503服务不可用
        if vectorizer is None or tfidf_matrix is None or original_df is None or grounded_generator is None:
            return jsonify({
                "success": False,
                "error": "模型和知识库正在加载中，请稍后重试"
            }), 503

        # // 获取前端传入的JSON数据，silent=True避免解析失败抛出异常
        request_data = request.get_json(silent=True)
        # // 前置校验2：请求数据为空，返回400参数错误
        if not request_data:
            return jsonify({
                "success": False,
                "error": "请求参数格式错误，请使用JSON格式提交"
            }), 400

        # // 提取用户输入的伤情描述，去除首尾空白字符
        input_injury_text = request_data.get('text', '').strip()
        # // 提取视觉证据（视频/图像分析结果），文本与视觉至少提供一个
        visual_evidence = request_data.get('visual') or {}
        has_visual_candidates = bool(visual_evidence and visual_evidence.get('injury_candidates'))
        # // 前置校验3：文本与视觉候选均为空，返回400参数错误
        if not input_injury_text and not has_visual_candidates:
            return jsonify({
                "success": False,
                "error": "请输入伤情描述文本，或提供视觉分析结果"
            }), 400

        # // 生成模式：grounded（确定性，默认，零幻觉）/ llm（LLM 合成，需忠实度门控）
        mode = request_data.get('mode', 'grounded')
        if mode not in ('grounded', 'llm'):
            mode = 'grounded'
        # // 是否启用 LLM-as-judge：llm 模式默认开，grounded 模式默认关（lexical 天然=1.0）
        with_judge = request_data.get('with_judge', (mode == 'llm'))

        # // 步骤1~2.5：Top-K 召回 + 双条件判定 + 多模态融合
        candidates, decision, fusion_info = _resolve_match(input_injury_text, visual_evidence)

        # // 前置校验4：未通过判定，返回404，不硬给错误方案
        if not decision["matched"]:
            response_body = {
                "success": False,
                "error": "未在知识库中找到足够匹配的伤情类型，请补充或调整描述后重试",
                "reason": decision.get("reason")
            }
            if fusion_info:
                response_body["fusion"] = fusion_info
            return jsonify(response_body), 404

        # // 步骤3：提取匹配到的伤情实体名称与分数
        matched_injury_entity = decision["injury"]
        best_match_score = decision["score"]

        # // 步骤4：阶段3 grounded 生成（结构化步骤 + 引用 + 双层忠实度）
        # // 视觉证据经多模态模块格式化为文本块后注入生成提示词（llm 模式）
        evidence_text = fusion.build_visual_evidence_block(visual_evidence) if fusion_info else None
        _trace_line("[3/4 上下文构建]", f"匹配伤情「{matched_injury_entity}」→ grounded 生成（mode={mode}，with_judge={with_judge}）")
        generation = grounded_generator.generate(
            matched_injury_entity,
            visual_evidence=evidence_text,
            mode=mode,
            with_judge=with_judge,
        )
        _faith = generation.get("faithfulness", {}) or {}
        _trace_line("[4/4 生成]", f"产出 {len(generation.get('steps', []))} 步 | 引用来源 {len(generation.get('sources', []))} 条")
        _trace_line("    忠实度", f"lexical={_faith.get('overall_lexical')} | judge={_faith.get('overall_judge')} | faithful={_faith.get('overall_faithful')}")

        # // 构造标准化返回结果：保留 /match 兼容字段 + 新增结构化生成字段
        response_body = {
            "success": True,
            "query": input_injury_text,
            "matched_injury": matched_injury_entity,
            "similarity_score": round(float(best_match_score), 4),
            "candidates": candidates,
            "mode": mode,
            "steps": generation.get("steps", []),
            "sources": generation.get("sources", []),
            "faithfulness": generation.get("faithfulness", {}),
        }
        if generation.get("error"):
            response_body["generation_error"] = generation["error"]
        if fusion_info:
            response_body["fusion"] = fusion_info
        return jsonify(response_body), 200

    # // 全局异常捕获：捕获所有未处理的异常，返回友好提示，避免服务崩溃
    except Exception as e:
        print(f"❌ /match/v2 接口处理异常：{str(e)}")
        print(f"❌ 详细错误堆栈：{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"服务内部异常：{str(e)}"
        }), 500


# // ============================================================
# // 阶段4 自适应 Agentic RAG：编排器装配（懒加载）
# // ============================================================
def _get_agentic_router():
    # //
    # // 懒加载构建 AgenticRouter：复用现有 grounded_generator 与检索链路，
    # // 不新开模型/索引。检索走 retrieve_candidates（已含 hybrid→tfidf 回退）。
    # //
    global agentic_router
    if agentic_router is None:
        from agentic_router import AgenticRouter
        from agentic_evidence import EvidenceAssessmentAgent

        def _retrieve(query, top_k=3):
            return retrieve_candidates(query, top_k=top_k)

        if hybrid_retriever is not None:
            # // 混合检索：分数为 dense 相似度，用默认 dense 尺度阈值
            evidence_agent = EvidenceAssessmentAgent()
        else:
            # // tfidf 回退：分数尺度不同（阈值 0.18），用 tfidf 尺度阈值
            evidence_agent = EvidenceAssessmentAgent(
                hybrid_threshold=SIMILARITY_THRESHOLD,
                fast_path_threshold=0.25,
                fast_path_gap=0.05,
                evidence_low=0.15,
            )

        agentic_router = AgenticRouter(
            retriever=_retrieve,
            generator=grounded_generator,
            evidence_agent=evidence_agent,
            top_k=TOP_K,
        )
        print(f"✅ 阶段4 Agentic 编排器就绪（max_retrieval_retry/agent 步数等安全限制见 [agentic_service]）")
    return agentic_router


@app.route('/agentic', methods=['POST'])
def agentic_match_and_advice():
    # //
    # // 自适应 Agentic RAG 接口：与 /match、/match/v2 共用同一检索/生成链路，
    # // 但走「信息充分性判断 → 自适应检索 → 证据评估 → 生成 → 验证 → 失败重规划」状态机。
    # // 请求参数：
    # // {
    # //   "text": "伤情描述（可选，与 visual 至少一个）",
    # //   "visual": {...}（可选，视觉分析结果）,
    # //   "mode": "grounded|llm"（生成模式，默认 llm）,
    # //   "with_judge": true|false（是否启用 LLM-as-judge，llm 模式默认 true）
    # // }
    # // 返回：success=false 且 final_decision∈{reject,blocked,needs_review,ask_info} 时 HTTP 404
    # //
    try:
        # // 前置校验1：服务未就绪
        if grounded_generator is None:
            return jsonify({"success": False, "error": "模型和知识库正在加载中，请稍后重试"}), 503

        request_data = request.get_json(silent=True)
        if not request_data:
            return jsonify({"success": False, "error": "请求参数格式错误，请使用JSON格式提交"}), 400

        input_text = request_data.get('text', '').strip()
        visual_evidence = request_data.get('visual') or {}
        has_visual = bool(visual_evidence and visual_evidence.get('injury_candidates'))
        if not input_text and not has_visual:
            return jsonify({"success": False, "error": "请输入伤情描述文本，或提供视觉分析结果"}), 400

        generation_mode = request_data.get('mode', 'llm')
        if generation_mode not in ('grounded', 'llm'):
            generation_mode = 'llm'
        with_judge = request_data.get('with_judge', (generation_mode == 'llm'))

        router = _get_agentic_router()
        result = router.run(
            input_text, visual_evidence=visual_evidence,
            generation_mode=generation_mode, with_judge=with_judge,
            input_type='visual' if (has_visual and not input_text) else 'text',
        )
        status = 200 if result.get('success') else 404
        return jsonify(result), status

    except Exception as e:
        print(f"❌ /agentic 接口处理异常：{str(e)}")
        print(f"❌ 详细错误堆栈：{traceback.format_exc()}")
        return jsonify({"success": False, "error": f"服务内部异常：{str(e)}"}), 500


# // ============================================================
# // 程序主入口
# // 功能：加载模型与知识库 → 启动gevent高并发WSGI服务器
# // 无任何硬编码IP/端口，全部从配置文件动态读取
# // ============================================================
if __name__ == '__main__':
    try:
        # // 服务启动前先加载模型和知识库，加载失败直接终止启动
        print("🔧 正在加载创伤知识库与TF-IDF模型...")
        load_model_and_knowledge()

        # // 控制台打印服务启动信息，全程无硬编码
        print("\n" + "=" * 80)
        print("🚀 灾害现场伤情智能匹配与急救处置服务已启动")
        print(f"📍 服务监听地址：{FLASK_HOST}:{FLASK_PORT}")
        print(f"📎 核心业务接口：POST {NETWORK_HTTP_SCHEME}://{PRINT_ACCESS_HOST}:{FLASK_PORT}/match")
        print(f"📎 结构化生成接口：POST {NETWORK_HTTP_SCHEME}://{PRINT_ACCESS_HOST}:{FLASK_PORT}/match/v2（引用溯源+忠实度校验）")
        print(f"🤖 自适应Agentic接口：POST {NETWORK_HTTP_SCHEME}://{PRINT_ACCESS_HOST}:{FLASK_PORT}/agentic（信息充分性判断+自适应检索+证据评估+验证）")
        print(f"🔍 健康检查接口：GET {NETWORK_HTTP_SCHEME}://{PRINT_ACCESS_HOST}:{FLASK_PORT}/health")
        print(f"🤖 大模型API地址：{OLLAMA_FULL_API_URL}")
        print(f"🤖 大模型名称：{OLLAMA_MODEL_NAME}")
        retrieval_desc = "BGE-M3 三路 RRF（dense+sparse+char-TF-IDF）" if hybrid_retriever is not None else "字符级 TF-IDF（回退）"
        print(f"🔎 检索模式：{retrieval_desc}")
        print("=" * 80 + "\n")

        # // 启动gevent高并发WSGI服务器，使用从配置文件读取的IP和端口，无硬编码
        http_server = WSGIServer((FLASK_HOST, FLASK_PORT), app)
        # // 持续运行服务，阻塞主线程
        http_server.serve_forever()

    # // 捕获启动过程中的异常，打印详细错误信息
    except Exception as e:
        print(f"❌ 服务启动失败：{str(e)}")
        print(f"❌ 详细错误堆栈：{traceback.format_exc()}")
