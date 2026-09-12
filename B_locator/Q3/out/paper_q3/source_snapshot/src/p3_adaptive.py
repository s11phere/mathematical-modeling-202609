"""Experimental combination of homing and dynamic covering-tour planning."""
from dataclasses import dataclass
import math
import numpy as np
from p3_homing import HomingConfig, HomingRobot
from p3_frontier import FrontierConfig, FrontierRobot
from p3_coverage import CertifiedCoverageMixin


@dataclass
class AdaptiveConfig(HomingConfig, FrontierConfig):
    locate_mode: str = 'never'
    quick_baseline_m: float = 400.0
    cover_grid_step_m: float = 50.0


class AdaptiveRobot(CertifiedCoverageMixin, HomingRobot, FrontierRobot):
    def __init__(self, arena, cfg=None, base=None, log=None):
        super().__init__(arena, cfg or AdaptiveConfig(), base=base, log=log)
        # The route's candidate masks must use the same conservative radius.
        from dataclasses import replace
        self.cfg = replace(self.cfg,cover_radius_m=self.certified_radius(),cover_slack_m=0.0)

    def initial_stage(self):
        if self.cfg.quick_baseline_m <= 0:
            return
        pending = self.heard_pending()
        if not pending:
            return
        angles = np.arange(72)*2*math.pi/72
        bearings = np.radians([self.recs[c].svds[0] for c in pending])
        # One short shared transverse baseline, then approach while measuring.
        score = np.sum(np.sin(angles[:,None]-bearings)**2,axis=1)
        a = angles[int(np.argmax(score))]
        p = self.cfg.quick_baseline_m*np.array([math.cos(a),math.sin(a)])
        self.scan_at(*p,pending)
        self.note_pos()
        self.stop_seq += 1
