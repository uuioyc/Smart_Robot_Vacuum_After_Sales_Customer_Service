from langchain.agents import create_agent

from agent.report_workflow import ReportWorkflow
from model.factory import chat_model
from rag.router import IntentRouter, route_tools
from utils.config_handler import rag_conf
from utils.log_handler import logger
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import rag_summarize,get_weather, get_user_id
from agent.tools.agent_tools import get_user_location, get_current_month
from agent.tools.agent_tools import fetch_external_data, fill_context_for_report
from agent.tools.middleware import log_before_model, monitor_tool, report_prompt_switch
from langchain_core.messages import AIMessageChunk, HumanMessage
SUMMARY_UPDATE_INTERVAL = 3   # 每 3 轮更新一次摘要

class ReactAgent:
    def __init__(self):
        self.all_tools = [
            rag_summarize, get_weather, get_user_id, get_current_month,
            get_user_location, fetch_external_data, fill_context_for_report
        ]
        # 2. 中间件也集中管理（构建 agent 时要复用）
        self.middleware = [log_before_model, monitor_tool, report_prompt_switch]
        # 3. 意图分类器（只初始化一次）
        self.router = IntentRouter()
        # 4. system_prompt（只加载一次）
        self.system_prompt = load_system_prompts()
        self.workflow = ReportWorkflow()
        self.max_history_turns = rag_conf['max_history_turns']
        self.summary_cache = {}

    def _summarize_history(self, old_messages: list, session_id: str = "default") -> str:
        """把较早的对话压缩成一段摘要（带缓存）"""
        if not old_messages:
            return ""

        # 缓存命中：当前 old_messages 和上次摘要时长度一致
        cache = self.summary_cache.get(session_id)
        if cache and len(old_messages) - cache["len"] < SUMMARY_UPDATE_INTERVAL:
            return cache["summary"]

        text = "\n".join([
            f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}"
            for m in old_messages
        ])
        prompt = f"""请用 100 字以内，总结以下对话的核心信息（用户身份、已讨论主题、待解决的问题）：
        {text}
        摘要："""

        try:
            response = chat_model.invoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
            self.summary_cache[session_id] = {
                "len": len(old_messages),
                "summary": summary
            }
            logger.info(f"[ReactAgent] 历史摘要: {summary[:80]}...")
            return summary
        except Exception as e:
            logger.warning(f"[ReactAgent] 摘要失败：{str(e)}")
            return ""


    def execute_stream(self, query: str, session_id: str = None, history: list = None):
        # 1. 带历史的意图分类 + 指代消解
        intent_result, re_written = self.router.classify_with_history(query, history)
        # 2. 工具路由
        allowed_tools = route_tools(intent_result.intent, self.all_tools)

        # 3. 分支处理
        if intent_result.intent == "small_talk":
            agent = create_agent(
                model=chat_model,
                system_prompt=self.system_prompt,
                middleware=self.middleware,
                tools=[]
            )
        elif intent_result.intent == 'usage_report':
            yield from self.workflow.run_stream(re_written)
            return
        else:
            agent = create_agent(
                model=chat_model,
                system_prompt=self.system_prompt,
                middleware=self.middleware,
                tools=allowed_tools
            )
        #4. 构建含历史的messages
        messages = []
        if history:
            window_size = self.max_history_turns * 2
            if len(history) > window_size:
                recent = history[- window_size:]
                old = history[: - window_size]
            else:
                recent = history
                old = []
            if old:
                summary = self._summarize_history(old, session_id)
                if summary:
                    messages.append({
                        "role": "system",
                        "content": f"【历史对话摘要】：{summary}"
                    })
            for msg in recent:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        messages.append({"role": "user", "content": re_written})

        input_dict = {"messages":messages}
        config = {"configurable": {"session_id": session_id}} if session_id else {}

        # 1. 使用 messages 模式，只吐出增量碎片
        chunks = agent.stream(
            input=input_dict,
            stream_mode="messages",
            context={"report": False},
            config=config
        )

        for chunk in chunks:
            # 2. messages 模式下，chunk 是一个元组：(message_chunk, metadata)
            msg, metadata = chunk
            if not isinstance(msg, AIMessageChunk): #如果不是AIMessageChunk直接跳过
                continue
            if getattr(msg, "tool_call_chunks", None):
                continue
            if getattr(msg, "tool_calls", None):
                continue
            if msg.content:
                yield msg.content


if __name__ == '__main__':
    agent = ReactAgent()
    history = []
    queries = [
        "机器人不充电怎么办",
        "第二个怎么处理",
        "那这个能自己修吗",
    ]

    for q in queries:
        print(f"\n{'=' * 50}\n用户：{q}\n{'=' * 50}")
        resp = ""
        for chunk in agent.execute_stream(q, history=history):
            print(chunk, end="", flush=True)
            resp += chunk
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": resp})