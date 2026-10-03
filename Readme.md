# 智能扫地机器人售后客服系统

基于 **RAG + Agent** 的智能客服系统，面向扫地机器人售后场景，支持知识问答、故障排查、选购建议、使用报告生成等 6 类意图。覆盖从**文档检索 → 混合召回 → 精排 → 多轮对话 → 意图路由**的完整链路。


## 🏗️ 系统架构

```
用户提问
   │
   ▼
┌──────────────────────────────┐
│      意图路由层（Router）      │
│  Pydantic 约束的 LLM 分类器    │
│  → 6 类意图：知识问答 / 故障   │
│    排查 / 选购建议 / 天气适配  │
│    / 使用报告 / 闲聊           │
└──────────┬───────────────────┘
           │ 按意图绑定工具子集
           ▼
┌────────────────────────────────────────┐
│        RAG 三阶段检索链路                │
│                                         │
│   Query Rewrite + Multi-Query           │
│              ↓                          │
│   BM25 召回 ──┐                         │
│              ├─→ RRF 融合               │
│   向量召回 ──┘                         │
│              ↓                          │
│   BGE-Reranker 精排 → Top-5             │
└────────────────────────────────────────┘
           │
           ▼
┌──────────────────┐
│  LLM 生成 + 溯源  │  Qwen-Max
│  Streamlit 流式   │
└──────────────────┘
```

## ✨ 核心特性

### 1. 三阶段混合检索链路
- **Query Rewrite + Multi-Query**：将口语化提问（如"原地转圈"）标准化为专业术语（"定位丢失"），并拆解为多个检索子问题
- **BM25 + 向量双通道召回**：解决错误码（E12）、型号（LDS）等稀有 token 向量召回不稳的问题
- **RRF 融合**：避免向量分数与 BM25 分数量纲不可比的问题
- **BGE-Reranker 精排**：Cross-Encoder 深度语义打分
- **效果**：Top-5 召回率 **92.7%**，MRR **0.72**

### 2. 意图识别与工具路由
- 6 类用户意图识别（知识问答 / 故障排查 / 选购建议 / 天气适配 / 使用报告 / 闲聊）
- 基于意图动态绑定工具子集，将 ReAct 搜索空间从 7 个工具缩减至 2-4 个
- 使用报告意图抽离为**固定状态机**，工具调用顺序由"LLM 决策"改为"程序固定"
- **效果**：意图识别准确率 **95%**（40 条评测集，含 10 条边界案例）

### 3. 多轮对话记忆与指代消解
- **滑动窗口**：保留最近 5 轮完整对话
- **历史摘要**：超窗对话通过 LLM 压缩为摘要注入 system prompt，带 session 级缓存
- **指代消解**：短查询改写成完整问题，如"第二个怎么处理" → "机器人充电触点脏污怎么处理"
- 改写结果**三处复用**（意图分类 / RAG 检索 / 消息构建）

### 4. 离线评测体系
- 自建 **55 条评测集**，覆盖 4 类意图、3 个难度等级
- 建立 **Recall@5 / MRR** 指标体系 + 自动化评测流水线
- A/B 对照实验量化各模块增益

## 📊 量化指标

| 指标 | 数值 |
| :--- | :--- |
| Top-5 召回率 | **92.7%** |
| MRR | **0.72** |
| 意图识别准确率 | **95%**（40 条测试集） |
| 单轮响应时间 | ~1.5 分钟 |
| 知识库覆盖 | 6 个文档 / 214 个 chunk |

## 🛠️ 技术栈

| 层次 | 技术 |
| :--- | :--- |
| **Agent 框架** | LangChain、LangGraph |
| **大模型** | Qwen-Max（通义千问） |
| **向量库** | ChromaDB |
| **检索** | BM25 (rank_bm25 + jieba)、BGE-Reranker-v2-m3 |
| **前端** | Streamlit |
| **配置** | YAML + 单例 |
| **语言** | Python 3.10 |

## 📂 项目结构

```
智扫通Agent/
├── agent/                        # Agent 模块
│   ├── react_agent.py            # 主 Agent（意图路由 + 多轮对话）
│   ├── report_workflow.py        # 报告生成状态机
│   ├── eval/                     # 意图识别评测
│   │   ├── intent_eval_dataset.csv
│   │   └── test_intent_accuracy.py
│   └── tools/
│       ├── agent_tools.py        # RAG / 天气 / 用户信息等工具
│       └── middleware.py         # 中间件（日志、监控、Prompt 切换）
├── rag/                          # RAG 模块
│   ├── rag_service.py            # 检索服务主入口
│   ├── vector_store.py           # 向量库封装
│   ├── bm25_retriever.py         # BM25 检索
│   ├── fusion.py                 # RRF 融合
│   ├── reranker.py               # Cross-Encoder 精排
│   ├── router.py                 # 意图路由 + 指代消解
│   ├── query_rewriter.py         # Query Rewrite
│   └── eval/                     # RAG 检索评测
│       ├── eval_dataset.csv      # 55 条评测集
│       ├── evaluator.py          # 评测执行器
│       ├── metrics.py            # Recall@K / MRR
│       └── reports/              # 评测报告输出
├── model/                        # 模型
│   ├── factory.py                # LLM / Embedding 工厂
│   └── bge-reranker-v2-m3/       # 本地 Rerank 模型
├── utils/                        # 工具
│   ├── config_handler.py         # YAML 配置加载
│   ├── file_handler.py           # 文件读写
│   ├── log_handler.py            # 日志
│   ├── path_tool.py              # 路径工具
│   └── prompt_loader.py          # Prompt 加载
├── prompts/                      # Prompt 模板
│   ├── intent_prompt.txt         # 意图分类 Prompt
│   ├── main_prompt.txt           # Agent 主 Prompt
│   ├── rag_summarize.txt         # RAG 总结 Prompt
│   └── report_prompt.txt         # 报告生成 Prompt
├── config/                       # 配置
│   ├── agent.yml                 # Agent 配置
│   ├── chroma.yml                # 向量库配置
│   ├── prompts.yml               # Prompt 路径配置
│   └── rag.yml                   # RAG 配置（核心参数）
├── data/                         # 知识库
│   ├── external/                 # 外部数据（用户使用记录）
│   ├── 扫地机器人100问.pdf
│   ├── 扫地机器人100问2.txt
│   ├── 扫拖一体机器人100问.txt
│   ├── 故障排除.txt
│   ├── 维护保养.txt
│   └── 选购指南.txt
├── logs/                         # 日志输出
├── app.py                        # Streamlit 主入口
└── requirements.txt
```

## 🚀 快速开始

### 环境准备

```bash
# 1. 克隆项目
git clone https://github.com/你的用户名/智扫通Agent.git
cd 智扫通Agent

# 2. 创建虚拟环境
conda create -n zzz python=3.10
conda activate zzz

# 3. 安装依赖
pip install -r requirements.txt
```

### 下载 Rerank 模型

```bash
# 从 ModelScope 下载 BGE-Reranker（约 2.29GB）
python -c "from modelscope import snapshot_download; \
snapshot_download(repo_id='BAAI/bge-reranker-v2-m3', \
                  local_dir='./model/bge-reranker-v2-m3')"
```

### 配置 API Key

在项目根目录创建 `.env` 文件：

```bash
DASHSCOPE_API_KEY=你的通义千问API_KEY
```

### 构建知识库

```bash
# 首次运行会自动构建 Chroma 向量库
python rag/vector_store.py
```

### 运行

```bash
# 启动 Streamlit 前端
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可使用。

### 运行评测

```bash
# RAG 检索评测
python rag/eval/evaluator.py

# 意图识别评测
python agent/eval/test_intent_accuracy.py
```

## ⚙️ 配置说明

项目采用 **多 YAML 拆分** 的配置管理方式，`utils/config_handler.py` 统一加载。

### `config/rag.yml`（核心参数）

```yaml
enable_query_rewrite: true        # 是否启用 Query Rewrite
rewrite_query_num: 3              # 生成子查询数量
enable_hybrid_search: true        # 是否启用 BM25 + 向量混合检索
enable_rerank: true               # 是否启用 Rerank
rerank_model: "./model/bge-reranker-v2-m3"
top_k: 5                          # 最终保留文档数
max_history_turns: 5              # 多轮对话保留轮数
```

### `config/chroma.yml`

```yaml
k: 10                             # 单路召回数量
persist_directory: "./chroma_db"
```

### `config/agent.yml`

```yaml
external_data_path: "data/external/使用记录.csv"
```

## 📈 评测结果

### RAG 检索评测（55 条）

| 配置 | Recall@5 | MRR |
| :--- | :--- | :--- |
| Baseline（纯向量） | 待补充 | 待补充 |
| + Query Rewrite | 待补充 | 待补充 |
| + 混合检索 + Rerank（完整） | **0.927** | **0.72** |

### 意图识别评测（40 条，含 10 条边界案例）

| 意图 | 准确率 |
| :--- | :--- |
| 知识问答 | 100% |
| 故障排查 | 100% |
| 选购建议 | 100% |
| 天气适配 | 100% |
| 使用报告 | 100% |
| 闲聊 | 100% |
| **总体** | **95%** |

## 🎯 技术亮点与思考

### 为什么用 RRF 而不是加权分数融合？
向量的 cosine 值域 0-1，BM25 分数值域 0-∞，两者量纲不可比。RRF 只看排名，天然公平，且 `k=60` 平滑了排名差异，避免单路偏差被放大。

### 为什么报告生成要用状态机？
报告的工具调用顺序固定（获取用户 ID → 获取月份 → 查询记录 → 生成）。用 ReAct 时 LLM 会自己决定顺序，容易乱；用状态机固定顺序后，**成功率从约 70% 提升至 100%**。

### 短查询为什么触发指代消解？
短查询（<20 字）大概率是追问，本身信息量不足。"它""这个""第二个"这些指代词必须结合上文才能理解。长查询（>20 字）通常是完整问题，不需要消解。

### 如何控制大模型幻觉？
两层防护：
1. 检索为空时返回固定兜底话术，不让 LLM 自由发挥
2. Rerank 后 Top-1 分数低于阈值时主动拒答
3. 日志记录低置信度查询，反向指导知识库扩充

## 📝 TODO

- [ ] 补充 Baseline 数据（关闭所有优化开关的对照实验）
- [ ] 接入 RAGAS 评测生成质量（Faithfulness / Answer Relevancy）
- [ ] 支持多模态输入（上传故障照片识别）
- [ ] Docker 部署

## 📄 License

MIT License

## 📧 联系方式

- 邮箱：zx118586@163.com
- GitHub：[@uuioyc](https://github.com/uuioyc)