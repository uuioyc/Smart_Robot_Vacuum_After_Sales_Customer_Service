from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.log_handler import logger

def _load_prompt(config_key: str, func_name: str) -> str:
    try:
        path = get_abs_path(prompts_conf[config_key])
    except KeyError:
        logger.error(f"[{func_name}] 在 yaml 配置中没有 {config_key} 配置项")
        raise

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[{func_name}] 读取提示词出错：{e}")
        raise


def load_system_prompts():
    return _load_prompt("main_prompt_path", "load_system_prompts")


def load_rag_prompts():
    return _load_prompt("rag_summarize_prompt_path", "load_rag_prompts")


def load_report_prompts():
    return _load_prompt("report_prompt_path", "load_report_prompts")

def load_intent_prompts():
    return _load_prompt("intent_prompt_path", "load_intent_prompts")

if __name__ == '__main__':
    print(load_system_prompts())