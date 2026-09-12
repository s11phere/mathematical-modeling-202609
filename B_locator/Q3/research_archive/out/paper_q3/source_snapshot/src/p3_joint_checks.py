"""Reply-ledger, coverage-preservation and end-to-end checks for joint policy."""
import math
import unittest
from unittest.mock import patch
from itertools import permutations
import numpy as np
import p3_adaptive_checks as common
from p3_joint import JointConfig,JointRobot
from p3_arena import MockArena,MockSource


class JointChecks(common.AdaptiveChecks):
    # Run all established geometry / no-truth checks against the new subclass.
    def setUp(self):
        self.robot_patch=patch.object(common,'AdaptiveRobot',JointRobot)
        self.config_patch=patch.object(common,'AdaptiveConfig',JointConfig)
        self.robot_patch.start();self.config_patch.start()
        self.addCleanup(self.robot_patch.stop);self.addCleanup(self.config_patch.stop)

    def test_planning_preserves_full_projected_coverage_and_has_no_actions(self):
        rb=JointRobot(MockArena(seed=20260913))
        rb.arena.enter();rb.scan_at(0,0,list(rb.cfg.channels));rb.initial_stage()
        before=len(rb.arena.actions);cfg=rb.cfg
        gx,gy,needed=rb.uncovered_mask()
        route,_=rb.assemble_route(1.)
        covered=np.zeros(len(gx),bool)
        for w in route:
            if w.get('cover_duty'):
                x,y=w['xy'];covered|=(gx-x)**2+(gy-y)**2<=rb.certified_radius()**2+1e-6
        self.assertFalse(np.any(needed&~covered))
        self.assertEqual(len(rb.arena.actions),before)
        self.assertIs(rb.cfg,cfg)

    def test_two_and_three_target_route_is_exact(self):
        rb=JointRobot(MockArena(seed=1))
        for pts in [[(1000,0),(100,0)],[(1000,0),(0,100),(50,0)]]:
            seq=[{'xy':p,'kind':'clear','ch':i+1} for i,p in enumerate(pts)]
            got=rb.nn_2opt(seq)
            expected=min(rb._route_length(p) for p in permutations(seq))
            self.assertAlmostEqual(rb._route_length(got),expected)

    def test_service_scan_occurs_after_clear_at_actual_endpoint(self):
        arena=MockArena(sources=[MockSource(1,1200,800,1500)])
        rb=JointRobot(arena,JointConfig(channels=(1,2)))
        arena.enter()
        rb.measure(0,0,1);rb.measure(400,0,1)
        br=rb.region_info(rb.recs[1]);start=len(arena.actions)
        wp={'kind':'clear','ch':1,'xy':br['center'],'r':br['radius'],'cover_duty':True,'n_bearings':2}
        rb.visit(wp)
        acts=arena.actions[start:]
        clear=next(i for i,a in enumerate(acts) if a['kind']=='clear' and a['clear_result']=='success')
        unknown=next(i for i,a in enumerate(acts) if a['kind']=='measure' and a['channel']==2)
        self.assertLess(clear,unknown)
        self.assertEqual((acts[unknown]['x'],acts[unknown]['y']),wp['xy'])
        self.assertTrue(rb.recs[1].cleared)

    def test_optional_probability_filter_cannot_drop_mandatory_source(self):
        arena=MockArena(sources=[MockSource(1,1300,0,1500)])
        rb=JointRobot(arena,JointConfig(channels=(1,),opportunistic_receive_probability=1.0))
        arena.enter();rb.measure(0,0,1)
        self.assertFalse(rb._cross_ok(rb.recs[1],-1700,600))
        self.assertFalse(rb.is_complete())
        wp=rb.target_waypoints()[0]
        rb.visit(wp)
        self.assertTrue(rb.recs[1].cleared)
        self.assertTrue(rb.is_complete())

    def test_failed_speculative_clear_remeasures_before_moving(self):
        class OffsetEstimate(JointRobot):
            def region_info(self,rec):
                br=super().region_info(rec)
                if br and rec.n_bearings==2:
                    return dict(br,center=(1100.,700.),radius=250.)
                return br
        arena=MockArena(sources=[MockSource(1,1200,800,1500)])
        rb=OffsetEstimate(arena,JointConfig(channels=(1,)))
        arena.enter();rb.measure(0,0,1);rb.measure(400,0,1)
        start=len(arena.actions)
        self.assertTrue(rb.clear_target(1,rb.recs[1]))
        acts=arena.actions[start:]
        self.assertEqual(acts[0]['kind'],'clear')
        self.assertNotEqual(acts[0]['clear_result'],'success')
        self.assertEqual(acts[1]['kind'],'measure')
        self.assertEqual((acts[0]['x'],acts[0]['y']),(acts[1]['x'],acts[1]['y']))


if __name__=='__main__':unittest.main(verbosity=2)
