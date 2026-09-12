"""Optional stronger open-route planning for Q4; no hidden-state access.

This mixin changes only the proposed ordering. P4SearchRobot still owns all
measurements, localization, termination and continuous completion checks.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np
from p4_search import P4SearchConfig, P4SearchRobot


@dataclass
class P4RouteV2Config(P4SearchConfig):
    route_v2_rounds: int = 4
    route_v2_starts: int = 5
    route_service_entry: bool = False
    route_fixed_stations: bool = False
    route_information: bool = False


class P4RouteV2Mixin:
    def _route_information(self, items):
        """Reference-distribution scan latency, used only to rank full tours."""
        if not hasattr(self,'_route_info_points'):
            # Fixed quadrature nodes are independent of mock scenarios/seeds.
            rng=np.random.default_rng(170120)
            n=1024
            angle=rng.uniform(0,2*math.pi,n);radius=1800*np.sqrt(rng.uniform(0,1,n))
            self._route_info_points=np.column_stack([radius*np.cos(angle),radius*np.sin(angle)])
            direct=rng.uniform(0,2*math.pi,n)
            self._route_info_direct=np.column_stack([np.cos(direct),np.sin(direct)])
            self._route_info_range=rng.uniform(1000,1500,n)
            self._route_info_cache={}
        def bits(p):
            p=tuple(p)
            if p not in self._route_info_cache:
                delta=np.asarray(p)-self._route_info_points
                mask=(np.linalg.norm(delta,axis=1)<=self._route_info_range)&(np.sum(delta*self._route_info_direct,axis=1)>=0)
                self._route_info_cache[p]=int.from_bytes(np.packbits(mask).tobytes(),'big')
            return self._route_info_cache[p]
        covered=0
        for p in self.scan_points:covered |= bits(p)
        masks=[None]+[bits(w['xy']) if w['kind']=='station' else None for w in items]
        n=len(self._route_info_points);base=0.35+0.65*(1-covered.bit_count()/n)
        factor=30*len(self.unheard())/base
        return masks,covered,n,factor

    def _fixed_ordered(self, items):
        if not hasattr(self, '_fixed_station_order'):
            scans=[w for w in items if w['kind']=='station']
            self._fixed_station_order=[w['si'] for w in self._strong_ordered(scans)]
        by_station={w['si']:w for w in items if w['kind']=='station'}
        seq=[by_station[i] for i in self._fixed_station_order if i in by_station]
        for w in (w for w in items if w['kind']=='clear'):
            def cost_at(k):
                a=self.pos if k==0 else seq[k-1]['xy']
                b=seq[k]['xy'] if k<len(seq) else None
                return math.dist(a,w['xy'])+(math.dist(w['xy'],b)-math.dist(a,b) if b is not None else 0.)
            k=min(range(len(seq)+1),key=cost_at);seq.insert(k,w)
        # Move targets between gaps while preserving the scan sequence.
        for _ in range(3):
            changed=False
            for w in list(seq):
                if w['kind']!='clear':continue
                old=seq.index(w);seq.remove(w)
                k=min(range(len(seq)+1),key=lambda k:self._length(seq[:k]+[w]+seq[k:],self.pos))
                seq.insert(k,w);changed |= old!=k
            if not changed:break
        return seq

    def _route_key(self, item):
        return (item['kind'], item.get('si', item.get('ch')))

    def _entry_points(self, item):
        c = np.asarray(item['xy'], float)
        if not getattr(self.cfg, 'route_service_entry', False) or item['kind'] != 'clear':
            return c.reshape(1, 2)
        rec = self.recs[item['ch']]
        if rec.n_bearings != 1:
            return c.reshape(1, 2)
        s = np.asarray(rec.pts[-1], float)
        a = math.radians(rec.svds[-1]);u = np.array([math.cos(a), math.sin(a)])
        normal = np.array([-u[1], u[0]])
        along = max(0., float((c-s) @ u))
        forward = self.cfg.home_fraction * along
        lateral = min(self.cfg.home_lateral_m, max(22., .3 * max(along, 1.)))
        midpoint = s + forward * u
        return np.asarray([midpoint-lateral*normal, midpoint+lateral*normal])

    def _ordered(self, items):
        if getattr(self.cfg,'route_fixed_stations',False):
            return self._fixed_ordered(items)
        return self._strong_ordered(items)

    def _strong_ordered(self, items):
        if len(items) <= 1:
            return list(items)
        n = len(items)
        pts = np.asarray([self.pos] + [w['xy'] for w in items], float)
        entries = [pts[0].reshape(1, 2)] + [self._entry_points(w) for w in items]
        d = np.zeros((n+1,n+1))
        for j,entry in enumerate(entries):
            d[:,j] = np.min(np.linalg.norm(pts[:,None,:]-entry[None,:,:],axis=2)
                           + np.linalg.norm(entry-pts[j],axis=1)[None,:],axis=1)
        np.fill_diagonal(d, 0.)
        info=self._route_information(items) if getattr(self.cfg,'route_information',False) else None
        symmetric=not getattr(self.cfg,'route_service_entry',False)

        def cost(seq):
            total=float(np.sum(d[np.asarray([0]+seq[:-1]),seq]))
            if info:
                masks,covered,ns,factor=info
                for j in seq:
                    if masks[j] is not None:
                        total+=factor*(0.35+0.65*(1-covered.bit_count()/ns))
                        covered |= masks[j]
            return total

        def improve(seq):
            seq = list(seq); value = cost(seq)
            for iteration in range(getattr(self.cfg, 'route_v2_rounds', 4)):
                best, best_value = None, value
                # Full objective also works for directed service-entry costs.
                for i in range(n-1):
                    for j in range(i+1,n):
                        trial = seq[:i] + seq[i:j+1][::-1] + seq[j+1:]
                        if symmetric and info is None:
                            a=0 if i==0 else seq[i-1]
                            delta=d[a,seq[j]]-d[a,seq[i]]
                            if j+1<n:delta+=d[seq[i],seq[j+1]]-d[seq[j],seq[j+1]]
                            val=value+delta
                        else:val = cost(trial)
                        if val < best_value-1e-7:
                            best,best_value = trial,val
                for i in range(n):
                    node = seq[i];rest=seq[:i]+seq[i+1:]
                    a=0 if i==0 else seq[i-1]
                    removal=-d[a,node]
                    if i+1<n:removal+=d[a,seq[i+1]]-d[node,seq[i+1]]
                    for j in range(n):
                        if i==j:continue
                        trial=rest[:j]+[node]+rest[j:]
                        if info is None:
                            prev=0 if j==0 else rest[j-1]
                            delta=removal+d[prev,node]
                            if j<len(rest):delta+=d[node,rest[j]]-d[prev,rest[j]]
                            val=value+delta
                        else:val=cost(trial)
                        if val<best_value-1e-7:
                            best,best_value=trial,val
                if best is None:break
                seq,value=best,cost(best)
            return seq,value

        # A warm start avoids discarding the global path after a small move.
        id_to_i = {self._route_key(w):i+1 for i,w in enumerate(items)}
        warm = [id_to_i[k] for k in getattr(self,'_route_v2_previous',[]) if k in id_to_i]
        for j in range(1,n+1):
            if j in warm:continue
            best = min(range(len(warm)+1), key=lambda k:cost(warm[:k]+[j]+warm[k:]))
            warm.insert(best,j)
        starts=[warm]
        first_candidates=np.argsort(d[0,1:])[:getattr(self.cfg,'route_v2_starts',5)]+1
        for first in first_candidates:
            seq=[int(first)];left=set(range(1,n+1))-set(seq)
            while left:
                j=min(left,key=lambda j:d[seq[-1],j]);seq.append(j);left.remove(j)
            starts.append(seq)
        seq,value=min((improve(seq) for seq in starts),key=lambda x:x[1])
        self._route_v2_previous=[self._route_key(items[i-1]) for i in seq]
        return [items[i-1] for i in seq]


class P4RouteV2Robot(P4RouteV2Mixin, P4SearchRobot):
    pass
