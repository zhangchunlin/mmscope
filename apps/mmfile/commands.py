from uliweb.core.commands import Command
import os
from uliweb.orm import Begin,Commit

class FindExtCommand(Command):
    name = 'findext'
    help = 'find all exts'

    def handle(self, options, global_options, *args):
        self.get_application(global_options)
        from uliweb import settings, models

        MediaDirRoot = models.mediadirroot
        MediaFile = models.mediafile
        MediaMetaData = models.mediametadata

        extd = {}
        scan_exts = settings.MMSCOPE.scan_exts

        for dir in MediaDirRoot.all():
            for root,dnames,fnames in os.walk(dir.path):
                for fname in fnames:
                    _,ext = os.path.splitext(fname)
                    if ext and ext[0]==".":
                        ext = ext.lower()
                        if extd.has_key(ext):
                            extd[ext] += 1
                        else:
                            extd[ext] = 1
        for k in extd:
            if not scan_exts.has_key(k):
                print("%s : %s"%(k,extd[k]))

class FixModelCommand(Command):
    name = 'fixmodel'
    help = 'fix db'

    def handle(self, options, global_options, *args):
        self.get_application(global_options)
        from uliweb import settings, models

        MediaDirRoot = models.mediadirroot
        MediaFile = models.mediafile
        MediaMetaData = models.mediametadata

        Begin()
        for i in MediaFile.all():
            if i.hidden != True:
                i.hidden = True
                i.save()
                i.hidden = False
                i.save()
        Commit()