#coding=utf-8
from uliweb import expose, functions, models
from mimetypes import guess_type
import os

@expose('/mmmonth')
class MmMonth(object):
    def __begin__(self):
        pass

    @expose('')
    def list(self):
        MediaMonth = models.mediamonth
        MediaFile = models.mediafile
        l = MediaMonth.filter(MediaFile.filter(MediaFile.c.month==MediaMonth.c.id).count>0)
        l = l.order_by(MediaMonth.c.month.asc())
        mdict = {}
        for i in l:
            year = i.month.year
            months = mdict.get(year)
            if not months:
                months = []
            months.append(i)
            mdict[year] = months
        return {"mdict":mdict}

    def api_mm(self):
        id_ = int(request.values.get("id",0))
        full = request.values.get("full",False)
        if not id_:
            return json({"success":False,"msg":"month not found"})

        MediaMonth = models.mediamonth
        MediaFile = models.mediafile
        MediaMetaData = models.mediametadata
        month = MediaMonth.get(id_)
        if not month:
            return json({"success":False,"msg":"month %s not found"%(id_)})
        l = MediaFile.filter(MediaFile.c.month==month.id)
        total = l.count()
        if not full:
            l = l.limit(3)
        tprops = settings.MMSCOPE.mtypes
        exts_cannot_show_in_browser = settings.MMSCOPE.exts_cannot_show_in_browser
        def _get_info(i):
            d = i.to_dict()
            relpath = functions.mm_fsenc2unicode(d["relpath"])
            filename = os.path.split(relpath)[-1]
            d["filename"] = filename
            d["can_show"] = os.path.splitext(filename)[1].lower() not in exts_cannot_show_in_browser
            mtype = i.meta.mtype
            tprop = tprops[mtype]
            d["type"] = tprop["type"]
            d["full_path"] = os.path.join(i.root.path,relpath)
            d["mimetype"] = guess_type(filename)[0]
            return d
        list_ = [_get_info(i) for i in l]
        num = len(list_)
        return json({"success":True,
            "msg":"OK",
            "list":list_,
            "num" : num,
            "more" : total>num
        })
