#coding=utf-8

import os
import platform

def _have_sub_dirs(path):
    try:
        l = os.listdir(path)
    except OSError as e:
        return False
    for i in l:
        p = os.path.join(path,i)
        if os.path.isdir(p):
            return True
    return False

def mm_root_dirs():
    from uliweb import settings

    system = platform.system()
    if system=='Linux':
        root = "/"
        l = os.listdir(root)
        l = list(set(l)-set(settings.MMSCOPE.root_ignore_items))
        def _get_info(i):
            p = os.path.join(root,i)
            if os.path.isdir(p):
                d = dict(path=p,title=i)
                if _have_sub_dirs(p):
                    d["children"] = []
                    d["loading"] = False
                return d
        l = [_get_info(i) for i in l]
        l = [i for i in l if i]
        l = sorted(l,key=lambda v: v.get("title","").lower())
        return l
    return []

def mm_dir_children(path):
    try:
        l = os.listdir(path)
    except OSError as e:
        return []
    if l:
        def _get_info(i):
            p = os.path.join(path,i)
            if os.path.isdir(p):
                d = dict(path=p,title=i)
                if _have_sub_dirs(p):
                    d["children"] = []
                    d["loading"] = False
                return d
        l = [_get_info(i) for i in l]
        l = [i for i in l if i and i["title"][0]!='.']
        l = sorted(l,key=lambda v: v.get("title","").lower())
        return l
    return []
