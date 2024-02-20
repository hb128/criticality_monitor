import json
import numpy as np
from geopy import distance as geopy_distance #geodesic accurate, great_circle has an error of 0.5% but 20x faster

class Mass:
    def load_json_file(self, path):
        ''' Open logged json in path, return json'''
        with open(path,'r') as f:
            self.json = json.load(f);
        self.locations = self.json['locations']
        self.positions = np.empty((0,2));
        self.ids = np.empty((0,1));
        self.timestamp = np.empty((0,1));
        for ident in self.locations:
            self.ids = np.append(self.ids,ident)
            loc = self.locations[ident]
            self.positions=np.append(self.positions,[[loc['latitude']*1e-6,loc['longitude']*1e-6]],axis=0)
            self.timestamp=np.append(self.timestamp,[loc['timestamp']])

    def get_lat(self):
        return self.positions[:,0]
    
    def get_long(self):
        return self.positions[:,1]
    
    def remove_points(self,indices):
        self.positions = self.positions[indices]
        self.ids = self.ids[indices]
        self.timestamp = self.timestamp[indices]
        
    def remove_points_outside_window(self,window):
        idx = np.logical_and(\
            np.logical_and(self.positions[:,0] > window[0][0],self.positions[:,0] < window[1][0]),\
            np.logical_and(self.positions[:,1] > window[0][1],self.positions[:,1] < window[1][1]))
        self.remove_points(idx)
        
    def remove_points_outside_circle(self,center,radius):
        ''' Remove positions (long, latidude) which are in a circle at center with radius given in km '''
        distances = np.array([geopy_distance.great_circle(p,center).km for p in self.positions])
        idx = distances <= radius
        self.remove_points(idx)

    def __init__(self):
        pass