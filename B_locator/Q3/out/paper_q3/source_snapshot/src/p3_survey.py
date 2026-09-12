"""Offline experimental early shared survey and staged clearance variants."""
from dataclasses import dataclass, replace
import argparse
import json
import math
from pathlib import Path

import numpy as np

from p3_adaptive import AdaptiveConfig, AdaptiveRobot
from p3_arena import MockArena
from p3_bench import run_one, summarize, fmt_row, HDR, outer_annulus


@dataclass
class SurveyConfig(AdaptiveConfig):
    survey_radius_m: float = 700.0
    survey_stops: int = 2
    survey_turn_deg: float = 90.0
    survey_scan_all: bool = True
    survey_bearings: int = 2
    survey_near_clear_m: float = 0.0
    survey_orientation: str = 'cross'
    survey_skip_origin: bool = False


class SurveyRobot(AdaptiveRobot):
    def chans_at(self, x, y, ch=None, cover_duty=False):
        if self.cfg.survey_skip_origin and not self.meas_pts and self.stats['n_measure'] == 0 and x == 0 and y == 0:
            return []
        return super().chans_at(x,y,ch,cover_duty)

    def initial_stage(self):
        pending = self.heard_pending()
        if self.cfg.survey_stops <= 0:
            return super().initial_stage()
        angles = np.arange(72)*math.tau/72
        if pending:
            bearings = np.radians([self.recs[c].svds[0] for c in pending])
            if self.cfg.survey_orientation == 'toward':
                score = np.sum(np.cos(angles[:,None]-bearings), axis=1)
            else:
                score = np.sum(np.sin(angles[:,None]-bearings)**2, axis=1)
            a0 = angles[int(np.argmax(score))]
        else:
            a0 = 0.0
        for i in range(self.cfg.survey_stops):
            a = a0 + math.radians(self.cfg.survey_turn_deg)*i
            p = self._safe_point(self.cfg.survey_radius_m*np.array([math.cos(a),math.sin(a)]))
            chans = [ch for ch in self.pending() if
                     ((self.cfg.survey_scan_all and self.recs[ch].n_bearings == 0
                       and self.adds_coverage(ch,*p)) or
                      (0 < self.recs[ch].n_bearings < self.cfg.survey_bearings))]
            if chans:
                self.scan_at(*p,chans)
                self.note_pos()
                self.stop_seq += 1
            if self.cfg.survey_near_clear_m:
                self.opportunistic_clear(radius=self.cfg.survey_near_clear_m,max_n=4)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',type=int,default=10)
    ap.add_argument('--seed',type=int,default=20260913)
    ap.add_argument('--step',type=int,default=100)
    ap.add_argument('--scenario',default='random')
    ap.add_argument('--configs',default='[]')
    ap.add_argument('--out',default=str(Path(__file__).resolve().parents[1] / 'out/p3_survey_dev.json'))
    args=ap.parse_args()
    configs=json.loads(args.configs)
    variants=[('adaptive',AdaptiveRobot,AdaptiveConfig())]
    variants += [(v.get('name',str(i)),SurveyRobot,replace(SurveyConfig(),**{k:x for k,x in v.items() if k!='name'})) for i,v in enumerate(configs)]
    output={}
    maker=MockArena if args.scenario=='random' else outer_annulus
    for name,cls,cfg in variants:
        reps=[run_one(cls,cfg,maker(seed=args.seed+i*args.step),None,True) for i in range(args.cases)]
        s=summarize(reps)
        print(fmt_row(name,s),flush=True)
        output[name]={'config':vars(cfg),'summary':s,'per_case':[{k:v for k,v in r.items() if k not in ('_actions','truth','channels')} for r in reps]}
        p=Path(args.out); p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(output,indent=2,default=str),encoding='utf-8')


if __name__=='__main__':
    main()
