"""
“用户不按说明书提问”。
用户说“原地转圈”，知识库里写的是“定位丢失”。
传统的向量检索对这种“口语 vs 专业术语”的跨越能力极差。
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from model.factory import chat_model
from utils.log_handler import logger

"""
改写成几个问题 rag['rewrite_query_num']，
搜索几篇相关文章，chroma['k']
最后剩下几篇 rag['top_k']
"""
class QueryRewriterResult(BaseModel):
    standard_query: str = Field("标准化后的检索核心问题")
    sub_queries: list[str] = Field("从不同的角度拆解问题，最多3个")

class QueryRewriter:
    def __init__(self):
        self.chat_model = chat_model
        # 告诉parser需要json的格式是什么样的
        self.parser = PydanticOutputParser(pydantic_object=QueryRewriterResult)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个扫地机器人售后领域的检索查询改写专家。将用户口语化、"
                           "模糊的提问，改写为标准化多角度的检索查询。\n{format_instructions}"),
                ("human","用户提问：{question}")
            ]
        ).partial(format_instructions=self.parser.get_format_instructions())
        #.partial直接填写结构，不用每次invoke都传
        self.chain = self.prompt | self.chat_model | self.parser

    def rewrite(self, question: str) -> QueryRewriterResult:
        try:
            return self.chain.invoke({"question":question})
        except Exception as e:
            logger.error(f"改写问题失败 {str(e)}")
            return QueryRewriterResult(standard_query=question, sub_queries=[])