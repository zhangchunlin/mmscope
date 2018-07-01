#coding=utf-8
from uliweb.orm import *
from uliweb import settings, models
import os
import logging
import subprocess
import re
import datetime
import time
import math
import re

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

#https://www.linuxquestions.org/questions/programming-9/python-datetime-to-epoch-4175520007/
def datetime2epoch(dt):
    return time.mktime(dt.timetuple())

def epoch2datetime(epoch):
    return datetime.datetime.fromtimestamp(epoch)

class MediaFile(Model):
    root = Reference("mediadirroot")
    relpath = Field(str, max_length = 512, nullable=False, index=True)
    meta = Reference("mediametadata", collection_name='files')
    month = Reference("mediamonth", collection_name='files')
    deleted = Field(bool,default = False)
    props = Field(JSON, default={})

    def get_filename(self):
        return os.path.split(self.relpath)[-1]

    def get_fpath(self):
        return os.path.join(self.root.path,self.relpath)

    def get_video_preview_img(self):
        rdpath,fname = os.path.split(self.relpath)
        dpath = os.path.join(self.root.path,"_mm_preview",rdpath)
        if not os.path.exists(dpath):
            log.info("mkdir %s"%(dpath))
            os.makedirs(dpath)
        if not os.path.exists(dpath):
            log.error("create %s failed"%(dpath))
            return None
        fpath_pimg = os.path.join(dpath,"%s.jpg"%(fname))
        fpath = self.get_fpath()
        if not os.path.exists(fpath_pimg):
            if not os.path.exists(fpath):
                return None
            #get DAR by ffmpeg -i
            wratio,hratio = 16,9
            cmd = "ffmpeg -i '%s'"%(fpath)
            p = subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            p.wait()
            stderr = p.stderr.read()
            cobj = re.compile(r"""DAR (\d+):(\d+)""")
            mobj = cobj.search(stderr)
            if mobj:
                try:
                    wratio,hratio = mobj.group(1,2)
                    wratio = int(wratio)
                    hratio = int(hratio)
                except IndexError as e:
                    pass

            w = 256
            h = w*hratio/wratio

            #https://www.oschina.net/code/snippet_54100_2865
            cmd = "ffmpeg -v 0 -y -i '%(infile)s' -vframes 1 -ss 5 -vcodec mjpeg -f rawvideo -s %(w)sx%(h)s -aspect %(wratio)s:%(hratio)s '%(outfile)s'"%{"wratio":wratio,"hratio":hratio,"h":h,"w":w,"infile":fpath,"outfile":fpath_pimg}
            log.info(cmd)
            if isinstance(cmd,unicode):
                cmd = cmd.encode(settings.GLOBAL.FILESYSTEM_ENCODING)
            os.system(cmd)
        if os.path.exists(fpath_pimg) and os.path.getsize(fpath_pimg)!=0:
            return fpath_pimg
        return None

    def get_ctime_options(self):
        from mmfile import Scanner
        options = []
        def add_option(d):
            epoch = d.get("epoch")
            found = False
            for i in options:
                if i.get("epoch")==epoch:
                    i["from"] = d["from"]
                    found = True
            if not found:
                options.append(d)
        #current
        epoch = datetime2epoch(self.meta.ctime)
        dt_str = self.meta.ctime.strftime("%Y-%m-%d %H:%M:%S")
        d = {"epoch":epoch,"dt_str":dt_str,"current":True,"from":"current"}
        add_option(d)

        #file stat
        fpath = self.get_fpath()
        st = os.stat(fpath)
        epoch = math.floor(st.st_ctime)
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(epoch))
        d = {"epoch":epoch,"dt_str":dt_str,"from":"file"}
        add_option(d)

        #file name
        cfg_list = [
            {"rep":r"20\d{12}","strp":"%Y%m%d%H%M%S"},
            {"rep":r"20\d{2}-\d{1,2}-\d{1,2}","strp":"%Y-%m-%d"},
        ]
        for cfg in cfg_list:
            rep = cfg["rep"]
            strp = cfg["strp"]
            l = re.findall(rep,self.relpath)
            for i in l:
                epoch = time.mktime(time.strptime(i, strp))
                dt_str = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(epoch))
                d = {"epoch":epoch,"dt_str":dt_str,"from":"file name"}
                add_option(d)

        #image exif
        _, ext = os.path.splitext(self.relpath)
        ext = ext.lower()
        scannner = Scanner(self.root.path)
        if ext in scannner.image_ext_set:
            epoch = scannner.get_image_exif_ctime(fpath)
            if epoch:
                dt_str = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(epoch))
                d = {"epoch":epoch,"dt_str":dt_str,"from":"image exif"}
                add_option(d)

        return options

    def update_ctime(self, epoch):
        self.meta.ctime = epoch2datetime(epoch)
        self.meta.save()
        self.update_month()
        self.save()

    def update_month(self):
        ctime = self.meta.ctime
        mdt = datetime.datetime(ctime.year,ctime.month,1)
        MediaMonth = models.mediamonth
        m = MediaMonth.get(MediaMonth.c.month==mdt)
        if not m:
            m = MediaMonth(month=mdt)
            m.save()
        if self.month!=m.id:
            self.month = m.id

class MediaMetaData(Model):
    size = Field(int)
    sha1sum = Field(str, max_length = 64, index=True)
    ctime = Field(datetime.datetime)

    MEDIA_TYPE_IMAGE = 1
    MEDIA_TYPE_AUDIO = 2
    MEDIA_TYPE_VIDEO = 3
    mtype = Field(int)

    dup = Field(int,default = 1)
    star = Field(bool,default = False)

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
