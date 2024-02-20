#!/usr/bin/python
class City:
    def get_center(self):
        return [self.latitude, self.longitude]

    def get_window(self):
        center=self.get_center()
        return [[center[0]-self.extent_latitude/2,center[1]-self.extent_lontitude/2],[center[0]+self.extent_latitude/2,center[1]+self.extent_lontitude/2]]

    def __init__(self,latitude,longitude,extent_latitude,extent_lontitude):
        self.latitude = latitude
        self.longitude = longitude
        self.extent_latitude = extent_latitude
        self.extent_lontitude = extent_lontitude
