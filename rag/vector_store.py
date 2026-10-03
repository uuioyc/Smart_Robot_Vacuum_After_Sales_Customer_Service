import os
from langchain_chroma import Chroma
from utils.config_handler import chroma_conf
from utils.log_handler import logger
from utils.path_tool import  get_abs_path
from utils.file_handler import pdf_loader, txt_loader
from utils.file_handler import listdir_with_allowed_type
from utils.file_handler import get_file_md5_hex
from langchain_text_splitters import RecursiveCharacterTextSplitter
from model.factory import embedding_model

class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embedding_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"])
        )
        self.splitter=RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf['chunk_size'],
            chunk_overlap=chroma_conf['chunk_overlap'],
            separators=chroma_conf['separators'],
            length_function=len,
            is_separator_regex=True
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_document(self):
        """
            从数据文件中读取内容，转化为向量存入向量库
            要计算文件的MD5做去重
        :return:
        """

        def check_md5_hex(md5_for_check: str):
            md5_file_path = get_abs_path(chroma_conf["md5_hex_store"])
            if not os.path.exists(md5_file_path):
                with open(md5_file_path, 'w', encoding='utf-8') as f:
                    return False

            with open(md5_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() == md5_for_check.strip():
                        return True
                return False

        def save_md5_hex(md5_for_check: str):
            md5_file_path = get_abs_path(chroma_conf["md5_hex_store"])
            with open(md5_file_path, 'a', encoding='utf-8') as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path, None)
            return []

        allowed_file_path = listdir_with_allowed_type(get_abs_path(chroma_conf['data_path']),
                                                      tuple(chroma_conf['allow_knowledge_file_type']))

        for path in allowed_file_path:
            md5_hex = get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在于知识库内，跳过")
                continue

            try:
                documents = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                split_document = self.splitter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue
                self.vector_store.add_documents(split_document)
                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info=True会记录详细堆栈
                logger.error(f"[加载知识库]{path}加载失败, {str(e)}", exc_info=True)

if __name__ == '__main__':
    v = VectorStoreService()

    v.load_document()

    retriever = v.get_retriever()

    res = retriever.invoke('扫地机器人为什么会迷路？定位丢失的原因是什么')

    for r in res:
        print(r.page_content)
        print('*'*20)