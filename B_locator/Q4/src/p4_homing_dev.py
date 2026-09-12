"""Small paired development experiment for Q4 localization only."""
import argparse
import json
from pathlib import Path
import statistics

from p4_arena_ext import directed_case
from p4_homing import P4HomingRobot, P4HomingConfig
from p4_robot import P4GridRobot, P4Config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', type=int, default=12)
    ap.add_argument('--out', default='B_locator/Q4/out/p4_homing_development.json')
    ap.add_argument('--tune', action='store_true')
    args = ap.parse_args()
    if args.tune:
        for fraction in (.4, .6, .9, 1.2):
            for lateral in (60., 100., 160.):
                reports = []
                for i in range(args.cases):
                    arena, _ = directed_case(20260914 + 100 * i, directed_frac=1., outward_frac=0.)
                    cfg = P4HomingConfig(home_fraction=fraction, home_lateral_m=lateral)
                    reports.append(P4HomingRobot(arena, cfg).run())
                print(fraction, lateral,
                      round(statistics.mean(r['virtual_time_s'] for r in reports)),
                      sum(r['cleared'] for r in reports),
                      round(statistics.mean(r['n_clear_fail'] for r in reports), 1), flush=True)
        return
    rows = []
    for scenario, frac, outward in [('mixed', .5, .5), ('uniform', 1., 0.)]:
        for i in range(args.cases):
            seed = 20260914 + 100 * i
            for name, cls, cfg in [('base', P4GridRobot, P4Config()),
                                   ('home', P4HomingRobot, P4HomingConfig())]:
                arena, _ = directed_case(seed, directed_frac=frac, outward_frac=outward)
                robot = cls(arena, cfg)
                report = robot.run()
                rows.append(dict(scenario=scenario, seed=seed, policy=name,
                                 time=report['virtual_time_s'], cleared=report['cleared'],
                                 total=report['n_sources'], measures=report['n_measure'],
                                 travel=report['travel_m'], failed=report['n_clear_fail'],
                                 fallbacks=robot.stats.get('n_home_fallback', 0)))
        for name in ('base', 'home'):
            sub = [r for r in rows if r['scenario'] == scenario and r['policy'] == name]
            print(scenario, name, 'time', round(statistics.mean(r['time'] for r in sub)),
                  'clear', sum(r['cleared'] for r in sub), '/', sum(r['total'] for r in sub),
                  'failed', round(statistics.mean(r['failed'] for r in sub), 1), flush=True)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
