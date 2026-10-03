"""
核心思想：不同意图绑不同的工具子集，LLM 只能在子集里选，不能在全集里乱选。
"""
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from utils.log_handler import logger
from utils.prompt_loader import load_intent_prompts
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from model.factory import chat_model

IntentType = Literal[
    "knowledge_qa", #"知识问题"
    "troubleshooting", #故障排查
    "purchase_advice", #选购建议
    "weather_adaptation", #天气/湿度适配
    "usage_report", #个人使用报告
    "small_talk" #闲聊
]

class IntentResult(BaseModel):
    intent: IntentType = Field(description="用户的意图分类")
    confidence: float = Field(description="分类置信度,0-1")
    reason: str = Field(description="简短分类理由")

INTENT_PROMPT = load_intent_prompts()

class IntentRouter:
    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=IntentResult)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", INTENT_PROMPT)
        ]).partial(format_instructions=self.parser.get_format_instructions())
        self.chain = self.prompt | chat_model | self.parser

    def classify(self, question: str) -> IntentResult:
        try:
            result: IntentResult = self.chain.invoke({"question": question})
            logger.info(f"[Router] 意图={result.intent} | 置信度={result.confidence} | 理由={result.reason}")
            return result
        except Exception as e:
            logger.warning(f"[Router] 分类失败，默认knowledge_qa: {str(e)}")
            return IntentResult(intent="knowledge_qa", confidence=0.0, reason="分类失败兜底")
    def _rewrite_query(self, query: str, history: list) -> str:
        if len(query) >= 20 or not history:
            return query
        recent = history[-6:]
        history_text = "\n".join([
            f"{'用户' if m['role'] =='user' else 'AI'}: {m['content'][:200]}"
            for m in recent
        ])
        prompt = f"""
            请将用户"当前问题"改写成一个完整独立的问题，
            结合历史对话理解指代词（如"它""这个""第二个"）。
            【历史对话】{history_text}
            【当前问题】{query}
            要求：
            - 只输出改写后的问题，不要其他内容
            - 如果无法确定指代对象，原样输出当前问题
            - 保留用户原意     
            改写后:
        """
        try:
            response = chat_model.invoke([HumanMessage(content=prompt)])  # ← 直接调模型
            rewritten = response.content.strip()
            logger.info(f"[Router]指代消解：'{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.warning(f"[Router] 指代消解失败: {str(e)}")
            return query

    def classify_with_history(self, query: str, history: list = None):
        if not history:
            return (self.classify(query), query)

        #短查询先做指代消解
        rewritten = self._rewrite_query(query, history)
        result = self.classify(rewritten)
        return (result, rewritten)

def route_tools(intent: str, all_tools: list[BaseTool]) -> list[BaseTool]:
    """
    根据意图过滤可调用的工具子集
    :param intent:
    :param all_tools:
    :return:
    """

    TOOL_MAP = {
        "knowledge_qa": ["rag_summarize"],
        "troubleshooting": ["rag_summarize"],
        "purchase_advice": ["rag_summarize"],
        "weather_adaptation": ["rag_summarize", "get_user_location", "get_weather"],
        "usage_report": ["get_user_id", "get_current_month", "fetch_external_data", "fill_context_for_report"],
        "small_talk": [],
    }

    allowed_names = TOOL_MAP.get(intent, ["rag_summarize"])
    allowed_tools = [t for t in all_tools if t.name in allowed_names]
    logger.info(f"[Router] 意图={intent} | 可用工具={[t.name for t in allowed_tools]}")
    return allowed_tools