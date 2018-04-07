#coding=utf-8
from uliweb.orm import *
from uliweb import models

class MediaDirRoot(Model):
    path = Field(str, max_length = 512, nullable=False, Index=True)
    mounted = Field(bool,default = True)

class MediaFile(Model):
    root = Reference("mediadirroot")
    meta = Reference("mediametadata")

class MediaMetaData(Model):
    size = Field(int)
    sha1sum = Field(str, max_length = 64)

    @classmethod
    def OnInit(cls):
        Index('sizesum_indx', cls.c.size, cls.c.sha1sum, unique=True)