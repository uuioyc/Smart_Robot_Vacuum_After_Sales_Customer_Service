"""
报告状态机：
报告生成的核心是工具调用顺序固定：

get_user_id → get_current_month → fetch_external_data → fill_context_for_report → LLM 生成报告
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from agent.tools.agent_tools import (
    get_user_id, get_current_month, fetch_external_data, fill_context_for_report
)
from model.factory import chat_model
from utils.prompt_loader import load_report_prompts


class ReportWorkflow:
    def run_stream(self, query: str, session_id: str = None):
        # Step 1：获取用户 ID（固定调用）
        user_id = get_user_id.invoke({})

        # Step 2：获取当前月份
        month = get_current_month.invoke({})

        # Step 3：查询使用记录
        record = fetch_external_data.invoke({"user_id": user_id, "month": month})

        # Step 4：触发报告上下文注入
        fill_context_for_report.invoke({})

        prompt = PromptTemplate.from_template(load_report_prompts())
        chain = prompt | chat_model | StrOutputParser()

        for chunk in chain.stream({
            "query": query,
            "user_id": user_id,
            "month": month,
            "record": record
        }):
            yield chunk

