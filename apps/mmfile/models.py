#coding=utf-8
from uliweb.orm import *
from uliweb import models
import os
import logging

log = logging.getLogger('mmfile')

class MediaDirRoot(Model):
    path = Field(str, max_length = 512, nullable=False, index=True)
    comment = Field(str, max_length = 1024)
    mounted = Field(bool,default = True)
    deleted = Field(bool,default = False)
    scantime = Field(datetime.datetime)
    props = Field(JSON, default={})

    def update_mounted(self,save=True):
        mounted = os.path.isdir(self.path)
        if mounted:
            if os.path.isfile(os.path.join(self.path,"_mm_ignore")):
                mounted = False
        if mounted!=self.mounted:
            self.mounted = mounted
            if save:
                self.save()

class MediaFile(Model):
    root = Reference("mediadirroot")
    relpath = Field(str, max_length = 512, nullable=False, index=True)
    meta = Reference("mediametadata", collection_name='file')
    deleted = Field(bool,default = False)

    def get_filename(self):
        return os.path.split(self.relpath)[-1]

    def get_fpath(self):
        return os.path.join(self.root.path,self.relpath)

class MediaMetaData(Model):
    size = Field(int)
    sha1sum = Field(str, max_length = 64, index=True)
    ctime = Field(datetime.datetime)

    MEDIA_TYPE_IMAGE = 1
    MEDIA_TYPE_AUDIO = 2
    MEDIA_TYPE_VIDEO = 3
    mtype = Field(int)

    dup = Field(int,default = 1)

    @classmethod
    def OnInit(cls):
        Index('sizesum_indx', cls.c.size, cls.c.sha1sum, unique=True)

    def update_dup(self,save=True):
        self.dup = MediaFile.filter(MediaFile.c.meta==self.id).filter(MediaFile.c.deleted==False).count()
        log.info("update %s with dup: %s"%(self.sha1sum, self.dup))
        if save:
            self.save()

    @classmethod
    def get_mtype(cls,path):
        from uliweb import settings
        _,ext = os.path.splitext(path)
        return settings.MMSCOPE.scan_exts[ext.lower()]
