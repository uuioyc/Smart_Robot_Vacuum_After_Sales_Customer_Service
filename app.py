import time

import streamlit as st
from agent.react_agent import ReactAgent
import uuid
from agent.tools.agent_tools import get_rag_sources
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

st.title("智能扫地机器人客服")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def render_sources(sources):
    if not sources:
        return
    with st.expander(f"📚 参考来源 {len(sources)} 个文件"):
        for s in sources:
            st.markdown(f"**{s['source']}** · {s['count']}段 · 最高分: {s['max_score']}")
            for c in s["chunks"]:
                st.caption(f"[{c['index']}] score = {c['rerank_score']}")
                st.caption(c['snippet'])
            st.divider()
#========渲染历史消息========
for message in st.session_state["messages"]:
    st.chat_message(message["role"]).write(message["content"])
    if message["role"] == "assistant" and message.get("sources"):
        render_sources(message["sources"])
prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    with st.spinner("智能客服思考中..."):
        agent = st.session_state["agent"]
        history = st.session_state["messages"][:-1]
        # 获取后端的流式生成器
        res_stream = agent.execute_stream(
            prompt,
            session_id=st.session_state["session_id"],
            history=history
        )

        # st.write_stream 会自动做打字机效果，并把所有碎片拼成完整字符串返回
        full_response = st.chat_message("assistant").write_stream(res_stream)

        current_sources = get_rag_sources(st.session_state["session_id"])
        # 存入历史记录（这里 full_response 就是完整的回答）
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": full_response,
                "sources":current_sources
            }
        )
        st.rerun()