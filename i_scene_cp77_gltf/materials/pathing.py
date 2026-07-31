import os


def context_path_key(path):
    if not path:
        return ""
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))
