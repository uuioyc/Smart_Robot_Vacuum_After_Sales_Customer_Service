from typing import Callable, Any

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command

from utils.log_handler import logger
from utils.prompt_loader import load_system_prompts, load_report_prompts

@wrap_tool_call
def monitor_tool( #工具监控,监督一个工具的执行就需要他的入参和工具本身
        #请求的数据封装
        request: ToolCallRequest,
        #执行的函数本身
        handler: Callable[[ToolCallRequest], ToolMessage | Command]
) -> ToolMessage:
    #自定义逻辑
    logger.info(f"[tool monitor]执行工具{request.tool_call['name']}")
    logger.info(f"[tool monitor]传入参数{request.tool_call['args']}")
    try:
        result = handler(request)
        logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")
        if request.tool_call['name'] == 'fill_context_for_report':
            request.runtime.context['report'] = True
        return result
    except Exception as e:
        logger.error(f"工具{request.tool_call['name']}调用失败，原因:{str(e)}")
        raise e

@before_model
def log_before_model(
        state: AgentState, #整个agent的状态记录
        runtime: Runtime #记录了整个执行过程的上下文信息
):
    logger.info(f"[log_before_model]即将调用模型，带有({len(state['messages'])}条消息)")
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | "
                 f"{state['messages'][-1].content.strip()}")
    return None

@dynamic_prompt #每次生成提示词之前调用此函数
def report_prompt_switch(request: ModelRequest): #动态切换提示词
    is_report = request.runtime.context.get("report", False)
    if is_report:
        return load_report_prompts()
    return load_system_prompts()
