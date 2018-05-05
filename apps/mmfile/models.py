#coding=utf-8
from uliweb.orm import *
from uliweb import models

class MediaDirRoot(Model):
    path = Field(str, max_length = 512, nullable=False, index=True)
    comment = Field(str, max_length = 1024)
    mounted = Field(bool,default = True)
    deleted = Field(bool,default = False)
    scantime = Field(datetime.datetime)
    props = Field(JSON, default={})

class MediaFile(Model):
    root = Reference("mediadirroot")
    meta = Reference("mediametadata")

class MediaMetaData(Model):
    size = Field(int)
    sha1sum = Field(str, max_length = 64)

    @classmethod
    def OnInit(cls):
        Index('sizesum_indx', cls.c.size, cls.c.sha1sum, unique=True)
