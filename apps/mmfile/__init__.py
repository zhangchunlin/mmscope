#coding=utf-8

import os
import platform
import hashlib
import logging
from pickle import dumps as pickle_dumps, loads as pickle_loads
from datetime import datetime
from sqlalchemy.sql import and_


log = logging.getLogger('mmfile')

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

BLOCKSIZE = 10*1024*1024
def _get_file_info(fpath):
    h = hashlib.sha1()
    with open(fpath, 'rb') as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            h.update(buf)
            buf = f.read(BLOCKSIZE)
    st = os.stat(fpath)
    return {"size":st.st_size,"ctime":st.st_ctime,"sha1":h.hexdigest()}

def mm_scan_dir(path):
    from uliweb import settings, functions, models
    from uliweb.orm import Begin,Commit
    import gevent

    udb = functions.get_unqlite(name="mem")
    if ('scanning' in udb) and udb["scanning"]=='true':
        log.info("already scanning,cancel")
        return {"success":False,"msg":"already scanning,please wait until finished"}

    def scan():
        gevent.sleep(0)
        if 'scanning' in udb and udb["scanning"]=='true':
            log.error("already scanning, cancel")
            return

        logs = udb.collection("logs")
        logs.create()
        def log2(msg,finished=False):
            logs.store({"msg":msg,"finished":finished})
            log.info(msg)

        try:
            udb["scanning"] = 'true'
            log2("begin to scan %s"%(path))
            ext_set = set(settings.MMSCOPE.scan_exts)
            mmudb = functions.get_unqlite(path=os.path.join(path,"_mm.udb"))
            with mmudb.transaction():
                for root,dnames,fnames in os.walk(path):
                    for fname in fnames:
                        _, ext = os.path.splitext(fname)
                        if ext.lower() not in ext_set:
                            break
                        fpath = os.path.join(root,fname)
                        rel_fpath = os.path.relpath(fpath,path)
                        if not mmudb.exists(rel_fpath):
                            info = _get_file_info(fpath)
                            mmudb[rel_fpath] = pickle_dumps(info)
                            log2("%s: %s scanned"%(path,rel_fpath))
                            gevent.sleep(0)
        finally:
            log2("%s scan finished"%(path))
            udb["scanning"] = 'false'

        MediaDirRoot = models.mediadirroot
        MediaFile = models.mediafile
        MediaMetaData = models.MediaMetaData
        root = MediaDirRoot.get(MediaDirRoot.c.path==path)
        if not root:
            log.error("root dir %s not found"%(path))
            logs.store({"msg":"error %s not found in database"%(path),"finished":True})
            return
        Begin()
        for k,v in mmudb:
            if not isinstance(k,unicode):
                k = k.decode("utf8")
            d = pickle_loads(v)
            size = d["size"]
            sha1 = d["sha1"]
            ctime = d["ctime"]
            meta = MediaMetaData.get(MediaMetaData.c.sha1sum==sha1 and MediaMetaData.c.size==size)
            if not meta:
                #log.info("add meta data: size=%s, sha1=%s"%(size,sha1))
                meta = MediaMetaData(size=size,sha1sum=sha1,ctime=datetime.fromtimestamp(ctime))
                meta.save()
            mfile = MediaFile.get(and_(MediaFile.c.root==root.id, MediaFile.c.relpath==k))
            if not mfile:
                log.info("add %s in db"%(k))
                mfile = MediaFile(root=root.id,relpath=k,meta=meta.id)
                mfile.save()
                meta.update_dup()
                meta.save()
        Commit()
        log2("finished scanning and update '%s'"%(path),finished=True)

    gevent.spawn(scan)
    return {"success":True,"msg":"Scan started"}
