#coding=utf-8
from uliweb.orm import *
from uliweb import models
import os

class MediaDirRoot(Model):
    path = Field(str, max_length = 512, nullable=False, index=True)
    comment = Field(str, max_length = 1024)
    mounted = Field(bool,default = True)
    deleted = Field(bool,default = False)
    scantime = Field(datetime.datetime)
    props = Field(JSON, default={})

class MediaFile(Model):
    root = Reference("mediadirroot")
    relpath = Field(str, max_length = 512, nullable=False, index=True)
    meta = Reference("mediametadata", collection_name='file')

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

    def update_dup(self):
        dup = MediaFile.filter(MediaFile.c.meta==self.id).count()

    @classmethod
    def get_mtype(cls,path):
        from uliweb import settings
        _,ext = os.path.splitext(path)
        return settings.MMSCOPE.scan_exts[ext.lower()]
