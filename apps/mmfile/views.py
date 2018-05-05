#coding=utf-8
from uliweb import expose, functions, models
import json as json_
import os

@expose('/mmfile')
class MmFile(object):
    @expose('')
    def list(self):
        return {}

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
        if self.path:
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
        return json({"success":False,"msg":"path not found"})

    def api_remove_dir_path(self):
        if self.path:
            p = self.MediaDirRoot.get(self.MediaDirRoot.c.path==self.path)
            if p:
                p.deleted = True
                p.save()
                return json({"success":True,"msg":"Successfully deleted!"})

        return json({"success":False,"msg":"path not found"})


