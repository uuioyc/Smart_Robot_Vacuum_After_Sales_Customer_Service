import os
def get_project_root_path():
    #获取到当前文件的绝对路径
    current_file = os.path.abspath(__file__)
    #上一级目录
    current_dir = os.path.dirname(current_file)

    project_root = os.path.dirname(current_dir)
    return project_root

def get_abs_path(relative_path):
    """
    传入相对路径，返回绝对路径
    :param relative_path:相对路径
    :return:绝对路径
    """

    project_root = get_project_root_path()
    return os.path.join(project_root, relative_path)

if __name__ == '__main__':
    print(get_abs_path("config/config.txt"))