import os, hashlib
from utils.log_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader
def get_file_md5_hex(file_path: str): #获取md5的十六进制值
    if not os.path.exists(file_path):
        logger.error(f"[md5计算]文件{file_path}不存在")
        return
    if not os.path.isfile(file_path):
        logger.error(f"f[md5计算]路径{file_path}不是文件")
        return

    md5_obj = hashlib.md5()

    chunk_size = 4096 #分片大小
    try:
        with open(file_path, "rb") as f: #rb 二进制方式读取
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk) #每次读取一个片，然后更新待计算数据
            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{file_path}md5失败，{str(e)}")
        return None

def listdir_with_allowed_type(path: str, allowed_types: tuple[str]): #返回文件夹内的文件列表（允许的文件后缀）
    files= []
    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]{path}不是文件夹")
        return allowed_types
    for f in os.listdir(path):
        if f.endswith(allowed_types): #f仅仅是文件名所以需要join
            files.append(os.path.join(path, f))
    return tuple(files)

def pdf_loader(file_path: str, password: str) -> list[Document]:
    return PyPDFLoader(file_path, password).load()

def txt_loader(file_path: str) -> list[Document]:
    return TextLoader(file_path, encoding='utf-8').load()
