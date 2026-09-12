"""Development-only source-informed orbit / inside-out route alternatives."""
from dataclasses import dataclass
import math
from p3_joint import JointRobot,JointConfig

@dataclass
class OrbitConfig(JointConfig):
    route_inner_m:float=0.
    orbit_order:bool=True

class OrbitRobot(JointRobot):
    def __init__(self,arena,cfg=None,base=None,log=None):
        super().__init__(arena,cfg or OrbitConfig(),base=base,log=log)

    def nn_2opt(self,seq):
        if len(seq)<4:return super().nn_2opt(seq)
        inner=[w for w in seq if w['kind']=='clear' and math.hypot(*w['xy'])<self.cfg.route_inner_m]
        outer=[w for w in seq if w not in inner]
        if not self.cfg.orbit_order:
            return super().nn_2opt(inner)+super().nn_2opt(outer)
        ordered=sorted(outer,key=lambda w:math.atan2(w['xy'][1],w['xy'][0]))
        front=super().nn_2opt(inner)
        if not ordered:return front
        candidates=[front+seq[k:]+seq[:k] for seq in (ordered,ordered[::-1]) for k in range(len(seq))]
        return min(candidates,key=self._route_length)
