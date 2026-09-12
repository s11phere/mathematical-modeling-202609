"""Meaningful checks of Q4 localization, independently of discovery routing."""
import math
import unittest

import numpy as np

from p3_arena import MockArena, MockSource
from p3_robot import _dist_point_polygon
from p4_homing import P4HomingRobot, P4HomingConfig


class ReplyFacade:
    """The planner cannot access sources, errors, action history, or truth."""
    def __init__(self, arena):
        self.__arena = arena

    @property
    def pos(self):
        return self.__arena.pos

    @property
    def virtual_time_s(self):
        return self.__arena.virtual_time_s

    def remaining_budget_s(self):
        return self.__arena.remaining_budget_s()

    def enter(self):
        return self.__arena.enter()

    def measure(self, *args):
        return self.__arena.measure(*args)

    def clear(self, *args):
        return self.__arena.clear(*args)


class FixedErrorArena(MockArena):
    fixed_error = 1.0

    def env_error(self, x, y):
        return self.fixed_error


class HomingChecks(unittest.TestCase):
    def test_single_positive_random_unknown_orientation(self):
        rng = np.random.default_rng(926062)
        for i in range(250):
            angle = rng.uniform(-math.pi, math.pi)
            radius = 1800 * math.sqrt(rng.random())
            g = np.array([radius * math.cos(angle), radius * math.sin(angle)])
            direction = rng.uniform(-180., 180.)
            observed = direction + rng.uniform(-90., 90.)
            distance = rng.uniform(5.01, 1500.)
            s = g - distance * np.array([math.cos(math.radians(observed)),
                                        math.sin(math.radians(observed))])
            src = MockSource(1, *g, max(1000., distance + 1e-5), cone_half=90., dir_deg=direction)
            arena = MockArena(seed=i, sources=[src])
            robot = P4HomingRobot(ReplyFacade(arena))
            arena.enter()
            self.assertEqual(robot.measure(*s, 1)['measure_result'], 'direction')
            self.assertTrue(robot.clear_here(1), msg=f'case {i}')
            self.assertTrue(src.cleared)
            self.assertEqual(robot.stats['n_rejected'], 0)

    def test_cone_boundary_and_extreme_error(self):
        for offset in (-90., -89.999, 0., 89.999, 90.):
            for error in (-1., 1.):
                for distance in (5.1, 25., 100., 500., 1499.9):
                    g = np.array([1799.9, 0.])
                    angle = math.radians(offset)
                    s = g - distance * np.array([math.cos(angle), math.sin(angle)])
                    src = MockSource(1, *g, 1500., cone_half=90., dir_deg=0.)
                    arena = FixedErrorArena(sources=[src])
                    arena.fixed_error = error
                    robot = P4HomingRobot(ReplyFacade(arena))
                    arena.enter()
                    self.assertEqual(robot.measure(*s, 1)['measure_result'], 'direction')
                    self.assertTrue(robot.clear_here(1), msg=str((offset, error, distance)))

    def test_negative_does_not_shrink_positive_region(self):
        src = MockSource(1, 500., 0., 1000., cone_half=90., dir_deg=0.)
        arena = MockArena(sources=[src])
        robot = P4HomingRobot(ReplyFacade(arena))
        arena.enter()
        robot.measure(0., 0., 1)
        before = robot.home_region(robot.recs[1])
        self.assertEqual(robot.measure(510., 0., 1)['measure_result'], 'no_signal')
        after = robot.home_region(robot.recs[1])
        self.assertEqual(before, after)
        self.assertLess(_dist_point_polygon((500., 0.), after['poly']), 1e-5)

    def test_geometric_fallback_clears_without_further_reception(self):
        src = MockSource(1, 790., 28., 1000., cone_half=90., dir_deg=0.)
        arena = MockArena(sources=[src])
        robot = P4HomingRobot(ReplyFacade(arena), P4HomingConfig(home_max_steps=0))
        arena.enter()
        robot.measure(0., 0., 1)
        self.assertTrue(robot.clear_here(1))
        self.assertEqual(robot.stats['n_measure'], 1)


if __name__ == '__main__':
    unittest.main()
