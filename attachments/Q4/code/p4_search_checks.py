"""Q4 reply isolation, continuous completion and action-ledger checks.

Run directly. Tests use fresh source objects and disclose source truth only
after /exit. No online simulator calls or credentials are used.
"""
from __future__ import annotations

import math
import unittest

import numpy as np

from p3_arena import MockArena, MockSource
from p4_arena_ext import directed_case
from p4_certificate import DirectionalCertificate, strict_layout
from p4_search import P4SearchConfig, P4SearchRobot, tier_config


class ProtocolOnlyArena:
    """Expose only protocol replies/command-derived state to the policy.

    In particular there are no sources, RNG, error-field, simulator config,
    action ledger, or simulator truth attributes available while running.
    """
    __slots__ = ('__backend', '__position', '__clock', '__limit', '__exited',
                 '__truth_calls', '__replies')

    def __init__(self, backend):
        self.__backend = backend
        self.__position = (0.0, 0.0)
        self.__clock = 0.0
        self.__limit = 0.0
        self.__exited = False
        self.__truth_calls = 0
        self.__replies = []

    @property
    def pos(self):
        return self.__position

    @property
    def virtual_time_s(self):
        return self.__clock

    def remaining_budget_s(self):
        return max(0.0, self.__limit - self.__clock)

    def budget_kind(self):
        return 'virtual'

    def _reply(self, reply, xy=None):
        reply = dict(reply)
        self.__replies.append(dict(reply))
        if reply.get('accepted') is True:
            self.__clock = float(reply['virtual_time_s'])
            if xy is not None:
                self.__position = tuple(map(float, xy))
        return reply

    def enter(self):
        reply = self._reply(self.__backend.enter())
        self.__limit = float(reply.get('max_virtual_duration_s', 360000.0))
        return reply

    def measure(self, x, y, channel):
        return self._reply(self.__backend.measure(x, y, channel), (x, y))

    def clear(self, x, y, channel):
        return self._reply(self.__backend.clear(x, y, channel), (x, y))

    def exit(self):
        reply = self._reply(self.__backend.exit())
        self.__exited = True
        return reply

    def truth(self):
        if not self.__exited:
            raise AssertionError('truth accessed before actual /exit')
        self.__truth_calls += 1
        return self.__backend.truth()

    @property
    def stats(self):
        if not self.__exited:
            raise AssertionError('simulator statistics accessed before /exit')
        return dict(self.__backend.stats)

    def audit(self):
        if not self.__exited:
            raise AssertionError('test audit before /exit')
        return self.__backend.actions, self.__truth_calls, self.__replies


class SearchChecks(unittest.TestCase):
    def test_legacy_thin_polygon_regression(self):
        from p4_search_bench import scenario_arena
        from p4_robot import P4GridRobot,P4Config
        arena=scenario_arena('uniform',20264414)
        rep=P4GridRobot(arena,P4Config()).run()
        self.assertEqual(rep['cleared'],15)
        self.assertEqual(rep['n_rejected'],0)

    def _run(self, backend, cfg=None):
        arena = ProtocolOnlyArena(backend)
        robot = P4SearchRobot(arena, cfg or tier_config('strict'))
        report = robot.run()
        self._ledger(report, arena)
        return robot, report, arena

    def _ledger(self, report, arena):
        actions, truth_calls, replies = arena.audit()
        self.assertEqual(actions[0]['kind'], 'enter')
        self.assertEqual(actions[-1]['kind'], 'exit')
        self.assertEqual(truth_calls, 1)
        position, channel = (0., 0.), 1
        virtual, travel, last_clear = 0., 0., 0.
        measures, successes, failures = 0, 0, 0
        for action in actions:
            if action['kind'] not in ('measure', 'clear'):
                continue
            point = (action['x'], action['y'])
            distance = math.dist(position, point)
            travel += distance
            duration = distance / 5.
            if action['kind'] == 'measure':
                duration += 5. + (1. if channel != action['channel'] else 0.)
                channel = action['channel']
                measures += 1
            elif action['clear_result'] == 'success':
                duration += 5.
                successes += 1
                last_clear = virtual + duration
            else:
                duration += 3.
                failures += 1
            virtual += duration
            self.assertAlmostEqual(action['dt'], duration, places=6)
            self.assertAlmostEqual(action['virtual_time_s'], virtual, places=6)
            position = point
        self.assertAlmostEqual(report['virtual_time_s'], virtual, places=6)
        self.assertAlmostEqual(report['travel_m'], travel, places=6)
        self.assertAlmostEqual(report['last_clear_time_s'], last_clear, places=6)
        self.assertEqual(report['n_measure'], measures)
        self.assertEqual(report['n_clear'], successes)
        self.assertEqual(report['n_clear_fail'], failures)
        self.assertEqual(report['cleared'], successes)
        self.assertEqual(report['n_rejected'], 0)
        self.assertTrue(all(r.get('accepted') for r in replies))

    def test_default_constructor_is_really_strict(self):
        cfg = P4SearchConfig()
        self.assertEqual(cfg.tier, 'strict')
        self.assertTrue(cfg.certify)
        self.assertEqual(cfg.search_layout, 'certified')

    def test_reply_only_full_run_and_original_accounting(self):
        for seed in (726103, 726149):
            with self.subTest(seed=seed):
                backend = directed_case(seed, directed_frac=1., outward_frac=0.)[0]
                robot, rep, _arena = self._run(backend)
                self.assertEqual(rep['cleared'], rep['n_sources'])
                self.assertTrue(rep['completion_certified'])
                self.assertEqual(rep['termination'], 'certified_complete')

    def test_empty_scene_requires_actual_complete_exploration(self):
        robot, rep, _arena = self._run(MockArena(seed=716, sources=[]))
        self.assertEqual(rep['cleared'], 0)
        self.assertEqual(rep['n_sources'], 0)
        self.assertTrue(rep['completion_certified'])
        self.assertGreater(rep['n_measure'], 20)
        fine = DirectionalCertificate(20, 48)
        for rec in robot.recs.values():
            self.assertTrue(fine.continuous_complete([row[:2] for row in rec.meas_log
                                                       if row[3] == 'no_signal']))

    def test_twenty_minrange_boundary_direction_sources(self):
        # Covers all twenty channels, exact disk boundary, smallest legal
        # reception disk, outward cones and tangential boundary directions.
        for heading in ('outward', 'tangent', 'mixed'):
            with self.subTest(heading=heading):
                sources = []
                for index in range(20):
                    angle = (index + .217) * 2 * math.pi / 20
                    offset = 180 if heading == 'outward' else (90 if heading == 'tangent'
                                                               else (0, 90, 180, 270)[index % 4])
                    sources.append(MockSource(index + 1, 1800 * math.cos(angle),
                                              1800 * math.sin(angle), 1000., cone_half=90.,
                                              dir_deg=math.degrees(angle) + offset))
                robot, rep, _arena = self._run(MockArena(seed=55081, sources=sources))
                self.assertEqual(rep['cleared'], 20)
                self.assertTrue(rep['completion_certified'])

    def test_low_budget_cannot_claim_complete(self):
        for budget in (0., 20., 150., 450.):
            with self.subTest(budget=budget):
                source = MockSource(1, 1780., 0., 1000., cone_half=90., dir_deg=180.)
                robot, rep, _arena = self._run(MockArena(seed=751, sources=[source], budget_s=budget))
                self.assertFalse(rep['completion_certified'])
                self.assertEqual(rep['termination'], 'budget_or_incomplete')
                self.assertLessEqual(rep['virtual_time_s'], budget)

    def test_coverage_uses_no_signal_not_planned_or_positive_sites(self):
        backend = MockArena(sources=[])
        robot = P4SearchRobot(backend, tier_config('strict'))
        backend.enter()
        self.assertFalse(robot._certify_remaining())
        # Inject a measurement history only to isolate the proof predicate.
        # Even a complete positive history never establishes source absence.
        for rec in robot.recs.values():
            rec.meas_log = [(x, y, 0., 'direction') for x, y in strict_layout()]
        self.assertFalse(robot._certify_remaining())
        for rec in robot.recs.values():
            rec.meas_log = [(x, y, 0., 'no_signal') for x, y in strict_layout()]
        self.assertTrue(robot._certify_remaining())
        robot.recs[1].near_hits = 1
        self.assertFalse(robot._certify_remaining())
        backend.exit()

    def test_near_remains_direction_dependent_and_is_cleared_immediately(self):
        backend = MockArena(sources=[MockSource(1, 3., 0., 1000., cone_half=90., dir_deg=180.)])
        robot = P4SearchRobot(backend, tier_config('strict'))
        backend.enter()
        self.assertEqual(robot.measure(0., 0., 1)['measure_result'], 'no_signal')
        robot.scan_at(6., 0., [1])
        self.assertEqual(backend.actions[-2]['measure_result'], 'near')
        self.assertEqual(backend.actions[-1]['clear_result'], 'success')
        self.assertTrue(robot.recs[1].cleared)
        backend.exit()

    def test_paired_negative_cap_geometry(self):
        # Verify the actual proof premises over rays at both bearing-error
        # extremes, all directional halfplanes containing the positive station,
        # and sources at/after the cutting cross-section.  Both cross points
        # must be no farther than the positive station; at least one endpoint
        # is in every emission halfplane that contains the positive station.
        err = math.radians(1.005 + 1e-8)
        rng = np.random.default_rng(55017)
        for _ in range(300):
            lateral = rng.uniform(20., 140.)
            low = lateral * (1 / math.cos(err) + math.tan(err)) + 1e-3
            high = lateral / math.tan(err) - 1e-3
            forward = rng.uniform(low, high)
            y = rng.uniform(-1, 1) * forward * math.tan(err)
            g = np.array([forward + rng.uniform(0, 10000), y])
            # Allow all valid wedge rays at and beyond the cross-section.
            g[1] = g[0] * rng.uniform(-math.tan(err), math.tan(err))
            qs = np.array([[forward, -lateral], [forward, lateral]])
            dist_s = np.linalg.norm(g)
            self.assertTrue(np.all(np.linalg.norm(qs - g, axis=1) <= dist_s + 1e-7))
            angles = np.linspace(0, 2 * math.pi, 1001)
            dirs = np.column_stack([np.cos(angles), np.sin(angles)])
            admissible = (-g @ dirs.T) >= 0
            covered = ((qs - g) @ dirs.T >= -1e-7).any(axis=0)
            self.assertTrue(covered[admissible].all())


if __name__ == '__main__':
    unittest.main(verbosity=2)
