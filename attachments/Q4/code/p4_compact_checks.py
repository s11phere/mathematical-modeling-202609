"""Targeted compact Q4 safety checks, independent of performance holdouts.

Run: python B_locator/Q4/src/p4_compact_checks.py
The policy sees ProtocolOnlyArena; expected source locations exist only in the
test harness. Continuous coverage is checked from actual negative replies.
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from p3_arena import MockArena, MockSource
from p3_robot import _dist_point_polygon
from p4_compact import P4CompactConfig, P4CompactRobot
from p4_homing import P4HomingMixin
from p4_layout_v2 import adaptive_complete, compact_layout
import p4_search_checks as previous_checks


def config(**overrides):
    options = dict(stronger_route=True, posterior_estimate=True,
                   route_information=True)
    options.update(overrides)
    return P4CompactConfig(**options)


class CompactChecks(unittest.TestCase):
    _ledger = previous_checks.SearchChecks._ledger

    def _run(self, backend, cfg=None):
        arena = previous_checks.ProtocolOnlyArena(backend)
        robot = P4CompactRobot(arena, cfg or config())
        report = robot.run()
        self._ledger(report, arena)
        return robot, report

    def test_empty_scene_actual_negative_certificate_and_reply_isolation(self):
        robot, report = self._run(MockArena(seed=716019, sources=[]))
        self.assertEqual(report['cleared'], 0)
        self.assertEqual(report['n_sources'], 0)
        self.assertTrue(report['completion_certified'])
        self.assertEqual(report['termination'], 'certified_complete')
        self.assertGreater(report['n_measure'], 20)
        # Every channel must independently have sufficient actual negatives.
        histories = {tuple(sorted({tuple(row[:2]) for row in rec.meas_log
                                   if row[3] == 'no_signal'}))
                     for rec in robot.recs.values()}
        self.assertTrue(all(adaptive_complete(points) for points in histories))

    def test_twenty_boundary_minrange_directed_sources(self):
        for heading in ('outward', 'tangent', 'mixed'):
            with self.subTest(heading=heading):
                sources = []
                for index in range(20):
                    angle = (index + .217) * 2 * math.pi / 20
                    offset = (180 if heading == 'outward' else
                              90 if heading == 'tangent' else
                              (0, 90, 180, 270)[index % 4])
                    sources.append(MockSource(
                        index + 1, 1800 * math.cos(angle),
                        1800 * math.sin(angle), 1000., cone_half=90.,
                        dir_deg=math.degrees(angle) + offset))
                _robot, report = self._run(MockArena(seed=550819, sources=sources))
                self.assertEqual(report['cleared'], 20)
                self.assertTrue(report['completion_certified'])
                self.assertEqual(report['termination'], 'certified_complete')

    def test_low_budget_never_claims_complete(self):
        for budget in (0., 20., 150., 450.):
            with self.subTest(budget=budget):
                source = MockSource(1, 1780., 0., 1000.,
                                    cone_half=90., dir_deg=180.)
                _robot, report = self._run(MockArena(
                    seed=751019, sources=[source], budget_s=budget))
                self.assertFalse(report['completion_certified'])
                self.assertEqual(report['termination'], 'budget_or_incomplete')
                self.assertLessEqual(report['virtual_time_s'], budget)

    def test_completion_uses_actual_negatives_and_rejects_pending_positive(self):
        arena = previous_checks.ProtocolOnlyArena(MockArena(sources=[]))
        robot = P4CompactRobot(arena, config())
        arena.enter()
        self.assertFalse(robot._certify_remaining())
        # Synthetic histories isolate the predicate, not policy exploration.
        for rec in robot.recs.values():
            rec.meas_log = [(x, y, 0., 'direction') for x, y in compact_layout()]
        self.assertFalse(robot._certify_remaining())
        for rec in robot.recs.values():
            rec.meas_log = [(x, y, 0., 'no_signal') for x, y in compact_layout()]
        self.assertTrue(robot._certify_remaining())
        robot.recs[1].near_hits = 1
        self.assertFalse(robot._certify_remaining())
        robot.recs[1].near_hits = 0
        robot.recs[1].pts = [(0., 0.)]
        robot.recs[1].svds = [0.]
        self.assertFalse(robot._certify_remaining())
        arena.exit()

    def test_posterior_preserves_polygon_and_encloses_all_vertices(self):
        # A positive at the origin and a negative on the far side update the
        # planning posterior without justifying any lone-negative disk cut.
        true_point = (700., 50.)
        for prior in (0., .5, 1.):
            with self.subTest(prior=prior):
                source = MockSource(1, *true_point, 1000.,
                                    cone_half=90., dir_deg=0.)
                arena = previous_checks.ProtocolOnlyArena(
                    MockArena(seed=851017, sources=[source]))
                robot = P4CompactRobot(arena, config(posterior_omni_prior=prior))
                arena.enter()
                self.assertEqual(robot.measure(0., 0., 1)['measure_result'], 'direction')
                rec = robot.recs[1]
                outer = P4HomingMixin.home_region(robot, rec)
                saved_polygon = np.asarray(outer['poly']).copy()
                saved_center, saved_radius = outer['center'], outer['radius']
                before = robot.home_region(rec)
                self.assertEqual(robot.measure(1100., 0., 1)['measure_result'], 'no_signal')
                after = robot.home_region(rec)
                self.assertEqual(rec.n_bearings, 1)
                for region in (before, after):
                    np.testing.assert_array_equal(region['poly'], saved_polygon)
                    distances = np.linalg.norm(saved_polygon - region['center'], axis=1)
                    self.assertLessEqual(float(distances.max()), region['radius'] + 1e-9)
                    self.assertLessEqual(math.dist(true_point, region['center']),
                                         region['radius'] + 1e-9)
                self.assertLessEqual(_dist_point_polygon(np.array(true_point), saved_polygon),
                                     1e-8)
                # The cached conservative estimate must not be mutated.
                unchanged = P4HomingMixin.home_region(robot, rec)
                self.assertEqual(unchanged['center'], saved_center)
                self.assertEqual(unchanged['radius'], saved_radius)
                np.testing.assert_array_equal(unchanged['poly'], saved_polygon)
                self.assertFalse(robot._certify_remaining())
                arena.exit()

    def test_adaptive_proof_rejects_empty_and_missing_outer_station(self):
        self.assertFalse(adaptive_complete([]))
        points = compact_layout()
        complete, levels = adaptive_complete(points, detail=True)
        self.assertTrue(complete)
        self.assertGreater(len(levels), 1)
        self.assertEqual(levels[-1][2], 0)
        self.assertFalse(adaptive_complete(points[:-1]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
