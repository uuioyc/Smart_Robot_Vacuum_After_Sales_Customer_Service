import streamlit as st
import os.path
import random

from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.log_handler import logger
from utils.path_tool import get_abs_path
import threading
from langchain_core.runnables import RunnableConfig

rag = RagSummarizeService()
user_ids = ["1001","1002","1003","1004","1005","1006","1007","1008","1009","1010"]
month_arr = [f"2025-{x:02d}" for x in range(1, 13)]
external_data = {}
_rag_sources_by_session = {}
_sources_lock = threading.Lock()

def set_rag_sources(session_id: str, sources: list):
    with _sources_lock:
        _rag_sources_by_session[session_id] = sources

def get_rag_sources(session_id: str) -> list:
    with _sources_lock:
        return _rag_sources_by_session.get(session_id, [])

@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str, config: RunnableConfig) -> str:
    """扫地机器人售后知识库检索工具"""
    result = rag.rag_summarize(query)

    session_id = config.get("configurable", {}).get("session_id")
    if session_id:
        set_rag_sources(session_id, result["sources"])

    logger.info(f"[RAG Tool] sources: {result['sources']}")
    return result["answer"]

    logger.info(f"[RAG Tool] sources: {result['sources']}")
    return result["answer"]

@tool(description="获取指定城市的天气，以消息字符串形式返回")
def get_weather(city: str) ->str:
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风一级，AQI21，最近6小时降雨概率低"

@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() ->str:
    return random.choice(['深圳','合肥','杭州'])

@tool(description="获取用户的ID，以纯字符串形式返回")
def get_user_id() -> str:
    return random.choice(user_ids)

@tool(description="获取当前月份，以纯字符串形式返回")
def get_current_month() ->str:
    return random.choice(month_arr)

def generate_external_data():
    """
    {
        "user_id":{
            "month":{'效率','特征'....}
            "month":{'效率','特征'....}
            "month":{'效率','特征'....}
        },
        "user_id":{
            "month":{'效率','特征'....}
            "month":{'效率','特征'....}
            "month":{'效率','特征'....}
        }
    }
    :return:
    """
    data_path = get_abs_path(agent_conf['external_data_path'])
    if not external_data:
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"外部数据{data_path}不存在")

    with open(data_path, 'r', encoding='utf-8') as f:
        next(f, None)
        for line in f:
            arr = line.strip().split(',')
            user_id = arr[0].replace('"',"")
            feature = arr[1].replace('"',"")
            efficiency = arr[2].replace('"',"")
            consumables = arr[3].replace('"',"")
            comparison = arr[4].replace('"',"")
            time = arr[5].replace('"',"")
            if user_id not in external_data:
                external_data[user_id] = {}

            external_data[user_id][time] = {
                '特征':feature,
                '效率':efficiency,
                '耗材':consumables,
                '对比':comparison
            }

@tool(description="从外部系统获取用户的使用记录，以纯字符串的形式返回，如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError as e:
        logger.warning(f"[fetch_external_data]未能检索到：{user_id}在{month}的使用记录")
        return ""

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"

if __name__ == '__main__':
    print(fetch_external_data("1001", "2025-01"))
