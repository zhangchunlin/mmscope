#coding=utf-8
from uliweb.orm import *

class MediaMonth(Model):
    month = Field(datetime.datetime)

    def get_month_str(self):
        return "%s-%02d"%(self.month.year,self.month.month)
