import re
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
from agent.tools.agent_tools import clear_rag_sources,get_rag_sources

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
        """
            history是一直增长的，所以old_messages也是一直增长的，第一轮摘要以后，每增长3条，也就是两轮对话才更新摘要
            阈值太小，缓存几乎不命中；阈值太大，摘要更新太慢，可能丢失上下文。
            其实这里3 4都一样，因为增量是偶数，不会有3的情况
        """
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

    def execute_stream(self, query: str, session_id: str = None, history: list = None, user_id=None):
        # ===== 清空本轮开始前的 sources（防止继承上一轮）=====
        if session_id:
            clear_rag_sources(str(session_id))


        # ===== 1. 意图分类 + 指代消解 =====
        intent_result, re_written = self.router.classify_with_history(query, history)

        # ===== 2. 工具路由 =====
        allowed_tools = route_tools(intent_result.intents, self.all_tools)

        intents = intent_result.intents  # 列表

        if intents == ["small_talk"]:
            # 纯闲聊
            agent = create_agent(
                model=chat_model,
                system_prompt=self.system_prompt,
                middleware=self.middleware,
                tools=[]
            )
        elif intents == ["usage_report"]:
            # 纯报告 → 状态机
            yield from self.workflow.run_stream(re_written)
            return
        else:
            # 其他（含复合意图）→ ReAct
            agent = create_agent(
                model=chat_model,
                system_prompt=self.system_prompt,
                middleware=self.middleware,
                tools=allowed_tools
            )

        # ===== 4. 构建含历史的 messages =====
        messages = []
        if history:
            window_size = self.max_history_turns * 2
            if len(history) > window_size:
                recent = history[-window_size:]
                old = history[:-window_size]
            else:
                recent = history
                old = []

            if old:
                summary = self._summarize_history(old, session_id)
                if summary:
                    messages.append({"role": "system", "content": f"【历史对话摘要】：{summary}"})

            for msg in recent:
                messages.append({"role": msg["role"], "content": msg["content"]})

        # ===== 如果意图包含 usage_report，主动注入使用记录 =====
        if "usage_report" in intent_result.intents and user_id:
            try:
                from agent.tools.agent_tools import fetch_external_data, get_current_month
                month = get_current_month.invoke({})
                # 用 user_id 映射成模拟 ID（1001-1009）
                mock_id = f"100{user_id}"
                record = fetch_external_data.invoke({"user_id": mock_id, "month": month})
                if record:
                    messages.append({
                        "role": "system",
                        "content": f"【用户 {month} 的使用记录】\n{record}"
                    })
                    logger.info(f"[ReactAgent] 主动注入使用记录: user={mock_id}, month={month}")
            except Exception as e:
                logger.warning(f"[ReactAgent] 注入使用记录失败: {e}")

        messages.append({"role": "user", "content": re_written})

        input_dict = {"messages": messages}
        config = {"configurable":
                      {
                          "session_id": session_id,
                          "user_id": user_id
                      }
                } if session_id else {}

        chunks = agent.stream(
            input=input_dict,
            stream_mode="messages",
            context={"report": False},
            config=config
        )

        # ===== 状态变量 =====
        thinking_buffer = ""  # 累积 thinking 内容
        answer_started = False  # thinking 阶段是否结束
        pending = ""  # 答案阶段开始前，待判断的内容（可能是 JSON）
        answer_buffer = ""  # 已输出的答案（用于 diff）

        for chunk in chunks:
            msg, metadata = chunk

            # 过滤非目标消息
            if not isinstance(msg, AIMessageChunk):
                continue
            if getattr(msg, "tool_call_chunks", None) or getattr(msg, "tool_calls", None):
                continue
            if not msg.content:
                continue

            content = msg.content

            # ==================== 阶段 1：thinking ====================
            if not answer_started:
                if content.startswith(thinking_buffer):
                    thinking_buffer = content
                else:
                    thinking_buffer += content

                if "</thinking>" in thinking_buffer:
                    thinking_text, _, after = thinking_buffer.partition("</thinking>")
                    thinking_text = thinking_text.replace("<thinking>", "").strip()

                    if thinking_text:
                        yield {"type": "thinking", "content": thinking_text}

                    answer_started = True
                    pending = after  # ← 答案开头内容，暂不输出
                else:
                    clean = thinking_buffer.replace("<thinking>", "")
                    if clean.strip():
                        yield {"type": "thinking", "content": clean.strip()}
                continue

            # ==================== 阶段 2：pending 判断 ====================
            if pending is not None:
                # 判断增量/全量
                if content.startswith(pending):
                    pending = content
                else:
                    pending += content

                stripped = pending.lstrip()

                # 全是空白 → 继续等
                if not stripped:
                    continue

                # 以 { 开头 → JSON，等 }
                if stripped.startswith("{"):
                    if "}" not in pending:
                        continue  # 继续攒
                    # JSON 结束，丢弃 JSON
                    idx = pending.index("}")
                    after = pending[idx + 1:]
                    pending = None
                    if after.strip():
                        answer_buffer = after
                        yield {"type": "content", "content": after}
                    continue

                # 其他 → 正常答案，开始输出
                pending = None
                answer_buffer = stripped
                yield {"type": "content", "content": stripped}
                continue

            # ==================== 阶段 3：正常答案输出 ====================
            if content.startswith(answer_buffer):
                delta = content[len(answer_buffer):]
                answer_buffer = content
            else:
                delta = content
                answer_buffer += content

            if delta:
                yield {"type": "content", "content": delta}

        # ==================== 兜底 1：只有 thinking 没有答案 ====================
        if not answer_started and thinking_buffer:
            clean = thinking_buffer.replace("<thinking>", "").replace("</thinking>", "").strip()
            if clean:
                yield {"type": "content", "content": clean}

        # ==================== 兜底 2：pending 没处理完 ====================
        if pending:
            clean = pending.lstrip()
            if clean and not clean.startswith("{"):
                yield {"type": "content", "content": clean}

        # ==================== 流结束，发 sources ====================
        # ===== 流结束，发 sources =====
        if session_id:
            sources = get_rag_sources(str(session_id))
            if sources:
                yield {"type": "sources", "content": sources}
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
        for chunk in agent.execute_stream(q, session_id="test", history=history, user_id="1"):
            print(chunk, end="", flush=True)
            resp += chunk
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": resp})