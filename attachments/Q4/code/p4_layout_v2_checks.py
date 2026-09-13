"""Meaningful checks for adaptive continuous coverage refinement."""
import math
import unittest
import numpy as np
from p4_certificate import DirectionalCertificate,strict_layout
from p4_layout_v2 import adaptive_complete,compact_layout,compact21_layout


class LayoutChecks(unittest.TestCase):
    def test_sparse_layout_requires_and_passes_refinement(self):
        points=compact_layout()
        self.assertEqual(len(points),22)
        self.assertFalse(DirectionalCertificate(20,48).continuous_complete(points))
        complete,steps=adaptive_complete(points,detail=True)
        self.assertTrue(complete)
        self.assertEqual(steps[-1][0],5.)

    def test_real_holes_are_rejected(self):
        points=compact_layout()
        self.assertFalse(adaptive_complete([]))
        self.assertFalse(adaptive_complete(points[:8]))
        self.assertFalse(adaptive_complete(points[:-1]))

    def test_refinement_does_not_turn_coarse_gaps_into_automatic_success(self):
        self.assertFalse(adaptive_complete(compact_layout(),40,20))
        self.assertTrue(adaptive_complete(strict_layout()))

    def test_rotated_layout_retains_certificate(self):
        p=np.array(compact_layout());a=.317
        rotation=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
        self.assertTrue(adaptive_complete(p@rotation.T))

    def test_twenty_one_station_layout(self):
        p=compact21_layout()
        self.assertEqual(len(p),21)
        self.assertTrue(adaptive_complete(p))


if __name__=='__main__':unittest.main()
