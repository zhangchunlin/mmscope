#coding=utf-8
from uliweb import expose, functions, models
from uliweb.utils.filedown import filedown
import json as json_
import os
import logging
import time
from sqlalchemy.sql import and_, select
from uliweb.orm import do_

log = logging.getLogger('mmfile')

@expose('/mmfile')
class MmFile(object):
    @expose('')
    def list(self):
        l = settings.MMSCOPE.mtypes
        mtype_options = json_.dumps([{"value":0,"label":"All","icon":"document"}]+[{"value":k,"label":l[k]["name"],"icon":l[k]["icon"]}for k in l])
        return {"mtype_options":mtype_options}

    def api_list(self):
        page_size = int(request.values.get("page_size",10))
        current = int(request.values.get("current",1))
        MediaDirRoot = models.mediadirroot
        MediaFile = models.mediafile
        MediaMetaData = models.mediametadata
        sort_key = request.values.get("sort_key")
        sort_order =  request.values.get("sort_order")
        select_mtype = int(request.values.get("select_mtype",0))

        keys = ["id","relpath","size","sha1sum","ctime","dup","mtype"]
        q = select([MediaFile.c.id,
            MediaFile.c.relpath,
            MediaMetaData.c.size,
            MediaMetaData.c.sha1sum,
            MediaMetaData.c.ctime,
            MediaMetaData.c.dup,
            MediaMetaData.c.mtype])
        q = q.select_from(MediaFile.table\
            .join(MediaMetaData.table,MediaFile.c.meta==MediaMetaData.c.id)
        )
        if select_mtype:
            q = q.where(MediaMetaData.c.mtype==select_mtype)
        total = q.count().execute().scalar()
        if sort_key and sort_order:
            if sort_order and (sort_order not in ("asc","desc")):
                sort_order = "asc"
            if sort_key=="ctime_str":
                q = q.order_by(getattr(MediaMetaData.c.ctime,sort_order)())
        q = q.offset((current-1)*page_size)
        q = q.limit(page_size)
        rows = [dict(zip(keys,i)) for i in do_(q)]
        tprops = settings.MMSCOPE.mtypes
        def _get_info(d):
            d["filename"] = os.path.split(d["relpath"])[-1]
            d["ctime_str"] = d["ctime"].strftime("%Y-%m-%d %H:%M")
            tprop = tprops[d["mtype"]]
            d["icon"] = tprop["icon"]
            d["type"] = tprop["type"]
            return d
        rows = [_get_info(i) for i in rows]
        return json({"rows":rows,"total":total})

    def img_thumbnail(self):
        filename = 'photo.jpeg'
        real_filename = application.get_file('photo.jpeg','static')
        return filedown(request.environ,filename=filename,real_filename=real_filename)

@expose('/mmdir')
class MmDir(object):
    def __begin__(self):
        self.path = request.values.get("path")
        if self.path:
            self.MediaDirRoot = models.mediadirroot
    @expose('')
    def list(self):
        root_dirs = json_.dumps(functions.mm_root_dirs())
        return {"root_dirs":root_dirs}

    def api_list(self):
        MediaDirRoot = models.mediadirroot
        def _get_info(i):
            mounted = os.path.isdir(i.path)
            if mounted!=i.mounted:
                i.mounted = mounted
                i.save()
            return i.to_dict()
        l = [_get_info(i) for i in MediaDirRoot.filter(MediaDirRoot.c.deleted==False)]
        return json({"list":l})

    def api_dir_children(self):
        if self.path:
            return json(functions.mm_dir_children(self.path))
        return json([])

    def api_add_dir_path(self):
        if not self.path:
            return json({"success":False,"msg":"path not found"})

        p = self.MediaDirRoot.get(self.MediaDirRoot.c.path==self.path)
        if p:
            if p.deleted:
                p.deleted = False
                p.save()
                return json({"success":True,"msg":"Successfully added!"})
            return json({"success":False,"msg":"already in the list"})
        if not os.path.isdir(self.path):
            return json({"success":True,"msg":"Directory not found"})
        p = self.MediaDirRoot(path=self.path)
        p.save()
        return json({"success":True,"msg":"Successfully added!"})

    def api_remove_dir_path(self):
        if not self.path:
            return json({"success":False,"msg":"path not found"})

        p = self.MediaDirRoot.get(self.MediaDirRoot.c.path==self.path)
        if p:
            p.deleted = True
            p.save()
            return json({"success":True,"msg":"Successfully deleted!"})

    def api_scan_dir_path(self):
        if not self.path:
            return json({"success":False,"msg":"path not found"})
        if not os.path.isdir(self.path):
            return json({"success":False,"msg":"directory not mounted?"})
        log.info("scan path: %s"%(self.path))
        return json(functions.mm_scan_dir(self.path))

@expose("/api_log")
def api_log():
    from gevent import sleep
    udb = functions.get_unqlite(name="mem")
    logs = udb.collection("logs")
    logs.create()
    count = 0
    for i in logs:
        if i:
            logs.delete(i['__id'])
            return json({"log":i})
        count += 1
        if count>10:
            break
        sleep(0.2)
    return json({})
