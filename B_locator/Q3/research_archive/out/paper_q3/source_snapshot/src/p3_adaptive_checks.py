"""Geometry, observation ledger and end-to-end checks for adaptive Q3 policy."""
import math
import unittest
import numpy as np
from p3_adaptive import AdaptiveConfig,AdaptiveRobot
from p3_arena import MockArena,MockSource
from p3_bench import outer_annulus
from p1_intersection import wedge_halfplanes


class NoTruthDuringRun(MockArena):
    def truth(self):
        if not self.finished:
            raise AssertionError('truth accessed before /exit')
        return super().truth()


class AdaptiveChecks(unittest.TestCase):
    def test_coverage_rejects_boundary_hole(self):
        # Old 25 m point sampling falsely certifies this legitimate layout.
        src=MockSource(1,1662.9831585,688.8301783,1000.)
        rb=AdaptiveRobot(MockArena(sources=[src]),AdaptiveConfig(channels=(1,)))
        rb.arena.enter()
        positions=[(0.,0.)]+[(925*math.cos(a),925*math.sin(a)) for a in np.arange(8)*math.pi/4]
        for p in positions:
            self.assertEqual(rb.measure(*p,1)['measure_result'],'no_signal')
        self.assertFalse(rb.is_complete())
        self.assertTrue(rb.unsafe_of(1).any())

    def test_near_is_pending_until_clear(self):
        rb=AdaptiveRobot(MockArena(sources=[MockSource(1,3.,0.,1000.)]),AdaptiveConfig(channels=(1,)))
        rb.arena.enter()
        self.assertEqual(rb.measure(0,0,1)['measure_result'],'near')
        for a in np.arange(8)*math.pi/4:
            rb.measure(1300*math.cos(a),1300*math.sin(a),1)
        self.assertEqual(rb.heard_pending(),[1])
        self.assertFalse(rb.is_complete())
        self.assertTrue(rb.clear_target(1,rb.recs[1]))
        self.assertTrue(rb.is_complete())

    def test_full_disk_cells_include_boundary(self):
        rb=AdaptiveRobot(MockArena(seed=1))
        gx,gy=rb.annulus_grid()
        centers=np.column_stack([gx,gy])
        boundary=1800*np.column_stack([np.cos(np.linspace(0,2*math.pi,720)),np.sin(np.linspace(0,2*math.pi,720))])
        maxdist=max(np.linalg.norm(centers-p,axis=1).min() for p in boundary)
        self.assertLessEqual(maxdist,50/math.sqrt(2)+1e-8)
        self.assertLess(rb.certified_radius(),1000)

    def test_coverage_accepts_genuine_complete_layout(self):
        rb=AdaptiveRobot(MockArena(sources=[]),AdaptiveConfig(channels=(1,)))
        rb.arena.enter()
        for p in [(0,0)]+[(1300*math.cos(a),1300*math.sin(a)) for a in np.arange(8)*math.pi/4]:
            rb.measure(*p,1)
        self.assertTrue(rb.is_complete())

    def test_positive_observations_cannot_certify_absence(self):
        rb=AdaptiveRobot(MockArena(sources=[MockSource(1,500,500,1500)]),AdaptiveConfig(channels=(1,)))
        rb.arena.enter()
        rb.measure(0,0,1)
        self.assertTrue(rb.unsafe_of(1).all())
        self.assertFalse(rb.is_complete())

    def test_rounded_extreme_bearings_contain_truth(self):
        for err in (-1.,1.):
            rb=AdaptiveRobot(MockArena(sources=[MockSource(1,1200,800,1500)]))
            # The test supplies observations directly to exercise geometry only.
            truth=np.array([1200.,800.])
            for p in ((0.,0.),(800.,200.),(1100.,800.)):
                th=(math.degrees(math.atan2(*(truth-np.array(p))[::-1]))+err)%360
                th=round(th,2)
                rb.add_bearing(1,*p,th)
            br=rb.region_info(rb.recs[1])
            self.assertIsNotNone(br)
            self.assertLessEqual(math.dist(br['center'],truth),br['radius']+1e-5)
            for p,th in zip(rb.recs[1].pts,rb.recs[1].svds):
                for a,b in wedge_halfplanes(p,th,1.005+1e-9):
                    self.assertLessEqual(float(a@truth+b),1e-5)

    def test_no_truth_read_and_complete_end_to_end(self):
        for seed in (20260913,20261013,20261113):
            rb=AdaptiveRobot(NoTruthDuringRun(seed=seed))
            r=rb.run()
            self.assertEqual(r['cleared'],r['n_sources'])
            self.assertTrue(r['complete_proof'])
            self.assertEqual(r['n_rejected'],0)
        rb=AdaptiveRobot(outer_annulus(seed=20260913))
        r=rb.run()
        self.assertEqual(r['cleared'],r['n_sources'])
        self.assertTrue(r['complete_proof'])


if __name__=='__main__':
    unittest.main(verbosity=2)
