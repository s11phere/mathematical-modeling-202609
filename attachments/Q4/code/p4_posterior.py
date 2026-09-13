"""Use negative replies for a source estimate, retaining an outer proof region.

The quadrature is a planning prior only. It never excludes geometric source
possibilities, stops search, or replaces the final continuous certificate.
"""
import math
import numpy as np


class P4PosteriorMixin:
    def home_region(self,rec):
        br=super().home_region(rec)
        if br is None or rec.n_bearings!=1 or not br.get('poly') or rec.near_hits:return br
        if not getattr(self.cfg,'posterior_estimate',False):return br
        key=(rec.channel,len(rec.meas_log),len(self._p4_home_caps.get(rec.channel,[])))
        cache=getattr(self,'_posterior_cache',None)
        if cache is None:self._posterior_cache={};cache=self._posterior_cache
        if key in cache:return cache[key]
        station=np.array(rec.pts[0]);angle=math.radians(rec.svds[0])
        u=np.array([math.cos(angle),math.sin(angle)])
        polygon=np.array(br['poly']);along=(polygon-station)@u
        ts=np.linspace(max(5.,along.min()),min(1500.,along.max()),150)
        candidates=station+ts[:,None]*u
        radii=np.linspace(1000,1500,9)
        ds=angle+np.linspace(-math.pi/2+math.pi/72,math.pi/2-math.pi/72,36)
        directions=np.stack([np.cos(ds),np.sin(ds)],axis=1)
        valid=(ts[:,None,None]<=radii[None,:,None])*np.ones((1,1,len(ds)),bool)
        omni=(ts[:,None]<=radii[None,:])
        for x,y,_,res in rec.meas_log:
            if res!='no_signal':continue
            v=candidates-(x,y);d=np.linalg.norm(v,axis=1)
            within=d[:,None]<=radii[None,:]
            bearing=(v@directions.T)>=0
            valid &= ~(within[:,:,None]&bearing[:,None,:])
            omni &= ~within
        prior=getattr(self.cfg,'posterior_omni_prior',.5)
        weights=ts*(np.linalg.norm(candidates,axis=1)<=1800)
        weights*=prior*omni.mean(axis=1)+(1-prior)*valid.mean(axis=(1,2))
        if weights.sum()>0:
            center=np.average(candidates,axis=0,weights=weights)
            radius=float(np.max(np.linalg.norm(polygon-center,axis=1)))
            br=dict(br,center=tuple(center),radius=radius)
        cache[key]=br
        return br
