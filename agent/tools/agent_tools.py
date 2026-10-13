from datetime import datetime

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
import requests
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



@tool(description="获取指定城市的天气，以消息字符串形式返回")
def get_weather(city: str) -> str:
    """查询指定城市的实时天气和未来预报"""
    # 天气描述映射
    WEATHER_ZH = {
        "Sunny": "晴",
        "Clear": "晴",
        "Partly cloudy": "局部多云",
        "Cloudy": "多云",
        "Overcast": "阴",
        "Mist": "薄雾",
        "Fog": "雾",
        "Light rain": "小雨",
        "Moderate rain": "中雨",
        "Heavy rain": "大雨",
        "Thunderstorm": "雷阵雨",
        "Snow": "雪",
        # ... 其他
    }
    try:
        # 使用 wttr.in 的 JSON 格式，lang=zh-cn 指定中文输出
        url = f"https://wttr.in/{city}?format=j1&lang=zh-cn"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # ---- 解析当前天气 ----
        current = data['current_condition'][0]
        weather_desc_en = current['weatherDesc'][0]['value']
        weather_desc = WEATHER_ZH.get(weather_desc_en, weather_desc_en)  # 一次到位
        temp_c = current['temp_C']
        feels_like = current['FeelsLikeC']
        humidity = current['humidity']
        wind_speed = current['windspeedKmph']
        wind_dir = current['winddir16Point']


        # ---- 解析今日预报（最高/最低温） ----
        today = data['weather'][0]
        max_temp = today['maxtempC']
        min_temp = today['mintempC']
        sunrise = today['astronomy'][0]['sunrise']
        sunset = today['astronomy'][0]['sunset']

        # ---- 组装成自然语言返回给 LLM ----
        result = (
            f"【{city} 实时天气】\n"
            f"天气状况: {weather_desc}\n"
            f"当前温度: {temp_c}°C (体感 {feels_like}°C)\n"
            f"今日温度: {min_temp}°C ~ {max_temp}°C\n"
            f"湿度: {humidity}%\n"
            f"风向风速: {wind_dir} {wind_speed} km/h\n"
            f"日出/日落: {sunrise} / {sunset}"
        )

        logger.info(f"[Weather Tool] 成功获取 {city} 天气: {weather_desc} {temp_c}°C")
        return result

    except requests.exceptions.Timeout:
        logger.error(f"[Weather Tool] 请求 {city} 天气超时")
        return f"抱歉，查询 {city} 天气时网络超时，请稍后重试。"
    except Exception as e:
        logger.error(f"[Weather Tool] 查询 {city} 天气失败: {str(e)}")
        return f"抱歉，暂时无法获取 {city} 的天气信息。"

@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() ->str:
    return random.choice(['深圳','合肥','杭州'])

@tool(description="获取当前登录用户的ID")
def get_user_id(config: RunnableConfig) -> str:
    user_id = config.get("configurable", {}).get("user_id")
    return f"100{str(user_id)}" if user_id else ""

@tool(description="获取当前月份，格式为 YYYY-MM")
def get_current_month() -> str:
    return "2025-02"

def get_rag_sources(session_id: str) -> list:
    with _sources_lock:
        result =  _rag_sources_by_session.get(session_id, [])
    logger.info(
        f"[Sources] 读取 session={session_id} (type={type(session_id).__name__}), 命中 {len(result)} 条, 现有 keys={list(_rag_sources_by_session.keys())}")
    return result
def clear_rag_sources(session_id: str):
    """清空某个 session 的 sources"""
    with _sources_lock:
        _rag_sources_by_session.pop(session_id, None)

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
