"""Route invariants and objective checks, independent of scenario truth."""
from __future__ import annotations

import math
from types import SimpleNamespace
import unittest
import numpy as np

from p4_route_v2 import P4RouteV2Mixin


class RouteHarness(P4RouteV2Mixin):
    def __init__(self):
        self.cfg=SimpleNamespace(route_v2_rounds=4,route_v2_starts=5,
                                 route_service_entry=False)
        self.pos=(10.,-20.)


def length(seq, origin):
    return sum(math.dist(a,b['xy']) for a,b in zip([origin]+[w['xy'] for w in seq],seq))


class RouteChecks(unittest.TestCase):
    def test_permutation_and_warm_start_after_target_changes(self):
        r=RouteHarness();rng=np.random.default_rng(420)
        stations=[dict(kind='station',si=i,xy=tuple(p)) for i,p in enumerate(rng.normal(size=(12,2))*1000)]
        first=r._ordered(stations)
        self.assertEqual(set(map(id,first)),set(map(id,stations)))
        r.pos=first[0]['xy']
        changed=first[1:]+[dict(kind='clear',ch=20,xy=(321.,654.))]
        second=r._ordered(changed)
        self.assertEqual(set(map(id,second)),set(map(id,changed)))

    def test_no_worse_than_nearest_neighbour(self):
        rng=np.random.default_rng(719)
        for _ in range(10):
            r=RouteHarness();items=[dict(kind='station',si=i,xy=tuple(p)) for i,p in enumerate(rng.normal(size=(14,2))*1000)]
            left=list(items);nn=[];p=r.pos
            while left:
                w=min(left,key=lambda w:math.dist(p,w['xy']));left.remove(w);nn.append(w);p=w['xy']
            route=r._ordered(items)
            self.assertLessEqual(length(route,r.pos),length(nn,r.pos)+1e-7)

    def test_empty_single(self):
        r=RouteHarness();self.assertEqual(r._ordered([]),[])
        items=[dict(kind='station',si=0,xy=(0.,0.))]
        self.assertEqual(r._ordered(items),items)


if __name__=='__main__':unittest.main()
