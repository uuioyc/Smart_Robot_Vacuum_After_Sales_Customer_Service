from agent.tools.agent_tools import get_weather

# 测试中文城市名
result = get_weather.invoke({"city": "深圳"})
print(result)
print("=" * 50)

# 测试英文城市名（更稳定）
result2 = get_weather.invoke({"city": "Beijing"})
print(result2)