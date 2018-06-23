#coding=utf-8

import os
import platform
import hashlib
import logging
import time
from pickle import dumps as pickle_dumps, loads as pickle_loads
from datetime import datetime
from sqlalchemy.sql import and_
import gevent
from PIL import Image

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

logs = []

class Scanner(object):
    def __init__(self,path):
        from uliweb import functions, settings
        self.udb = functions.get_unqlite(name="mem")
        self.path = path
        self.BLOCKSIZE = 10*1024*1024
        scan_exts = settings.MMSCOPE.scan_exts
        self.ext_set = set(scan_exts.keys())
        self.image_ext_set = set([ext for ext in self.ext_set if scan_exts[ext]==1])
        #https://github.com/python-pillow/Pillow/blob/master/src/PIL/ExifTags.py
        self.exif_keys = [0x0132,0x9003,0x9004]

    def _get_file_info(self,fpath,ext):
        h = hashlib.sha1()
        with open(fpath, 'rb') as f:
            buf = f.read(self.BLOCKSIZE)
            while len(buf) > 0:
                h.update(buf)
                buf = f.read(self.BLOCKSIZE)
        st = os.stat(fpath)
        return {"size":st.st_size,"ctime":st.st_ctime,"sha1":h.hexdigest()}

    def get_image_exif_ctime(self,fpath):
        img = Image.open(fpath)
        try:
            d = img._getexif()
        except AttributeError as e:
            log.error("'%s' error: %s"%(fpath,e))
            return None
        except SyntaxError as e:
            log.error("'%s' error: %s"%(fpath,e))
            return None
        if d:
            timestr = ""

            for k in self.exif_keys:
                if d.has_key(k):
                    try:
                        timestr = d[k]
                        return time.mktime(time.strptime(timestr, "%Y:%m:%d %H:%M:%S"))
                    except ValueError as e:
                        log.error("'%s' error: %s"%(fpath,e))
        return None

    def _scan(self):
        from uliweb import functions, models
        from uliweb.orm import Begin,Commit

        udb = self.udb
        path = self.path

        gevent.sleep(0)
        if 'scanning' in udb and udb["scanning"]=='true':
            log.error("already scanning, cancel")
            return

        def log2(msg,finished=False):
            logs.append({"msg":msg,"finished":finished})
            log.info(msg)

        fcount = 0
        try:
            udb["scanning"] = 'true'
            log2("begin to scan %s"%(path))

            mmudb = functions.get_unqlite(path=os.path.join(path,"_mm.udb"))
            with mmudb.transaction():
                ext_set = self.ext_set
                c = 0
                for root,dnames,fnames in os.walk(path):
                    dname_root = os.path.split(root)[1]
                    if dname_root.startswith(".") or dname_root.startswith("_mm"):
                        del dnames[:]
                        log.warning("ignore %s"%(root))
                        continue
                    log2("scan %s"%(root))
                    gevent.sleep(0.01)
                    for fname in fnames:
                        _, ext = os.path.splitext(fname)
                        ext = ext.lower()
                        if ext not in ext_set:
                            continue
                        fpath = os.path.join(root,fname)
                        rel_fpath = os.path.relpath(fpath,path)
                        info = None
                        need_update = False
                        isimage = ext in self.image_ext_set
                        if not mmudb.exists(rel_fpath):
                            info = self._get_file_info(fpath,ext)
                            need_update = True
                        else:
                            info = pickle_loads(mmudb[rel_fpath])
                        if isimage and not info.has_key("ctime_exif"):
                            info["ctime_exif"] = self.get_image_exif_ctime(fpath)
                            need_update = True

                        c += 1
                        if c%100==0:log2("scan %s files"%(c))

                        if info and need_update:
                            mmudb[rel_fpath] = pickle_dumps(info)
                            fcount += 1
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
            logs.append({"msg":"error %s not found in database"%(path),"finished":True})
            return
        Begin()
        ncount = 0
        log.info("check all items in mmudb to create new in db")
        c = 0
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
                meta = MediaMetaData(size=size,
                    sha1sum=sha1,
                    ctime=datetime.fromtimestamp(ctime),
                    mtype=MediaMetaData.get_mtype(k)
                )
                meta.save()
            else:
                if d.has_key("ctime_exif"):
                    ctime = d["ctime_exif"]
                if ctime:
                    dt = datetime.fromtimestamp(ctime)
                    if meta.ctime!=dt:
                        meta.ctime = dt
                        meta.save()
            mfile = MediaFile.get(and_(MediaFile.c.root==root.id, MediaFile.c.relpath==k))
            if not mfile:
                ncount += 1
                log.info("add %s in db,%s new files"%(k,ncount))
                mfile = MediaFile(root=root.id,relpath=k,meta=meta.id)
                mfile.save()
                meta.update_dup()
            c += 1
            if c%100==0:log2("check %s files for detecting new"%(c))
            gevent.sleep(0)
        log2("check %s files for new at last"%(c))
        log.info("check all deleted items")
        c = 0
        dcount = 0
        for mf in MediaFile.filter(MediaFile.c.root==root.id):
            fpath = os.path.join(root.path,mf.relpath)
            deleted = not os.path.isfile(fpath)
            if deleted!=mf.deleted:
                log2("'%s' update deleted: %s -> %s"%(fpath,mf.deleted,deleted))
                mf.deleted = deleted
                mf.save()
                mf.meta.update_dup()
                dcount += 1
            c += 1
            if c%100==0:log2("check %s files for detecting deleted"%(c))
        log2("check %s files for deleted at last"%(c))
        Commit()
        log2("finished scanning and update '%s', scan %s new files, add %s files, deleted %s files in db"%(path,fcount,ncount,dcount),finished=True)

    def scan(self):
        if ('scanning' in self.udb) and self.udb["scanning"]=='true':
            log.info("already scanning,cancel")
            return {"success":False,"msg":"already scanning,please wait until finished"}
        gevent.spawn(self._scan)
        return {"success":True,"msg":"Scan started"}

def mm_scan_dir(path):
    o = Scanner(path)
    return o.scan()

def mm_get_image_exif_ctime(root,relpath):
    o = Scanner(root)
    return o.get_image_exif_ctime(os.path.join(root,relpath))
