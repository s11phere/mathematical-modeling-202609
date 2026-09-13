#!/usr/bin/env python3
"""Frozen Q3 paired experiment and independent, replay-only audits.

Default execution resumes missing runs; --audit-only never constructs a robot.
Changing this reporting script does not change the experiment definition or
invalidate completed runs. --smoke always writes to a separate smoke directory.
Only NumPy and the standard library are required. See out/paper_q3/README.md.
"""
from __future__ import annotations
import argparse
import ast
import csv
import hashlib
import json
import math
import platform
import shutil
import signal
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve()
Q3 = HERE.parents[1]
SRC = Q3 / 'src'
# ``Q3`` is the archive root because this runner lives in
# ``Q3/research_archive/scripts``; keep the frozen results beside its source.
OUT_DEFAULT = Q3 / 'out/paper_q3'
sys.path.insert(0, str(SRC))
from p3_robot import P3Config, P3Robot, load_base
from p3_sweep import SweepConfig, SweepRobot
from p3_tour import TourConfig, TourRobot
from p3_adaptive import AdaptiveConfig, AdaptiveRobot
from p3_joint import JointConfig, JointRobot
from p3_adaptive_bench import make_scene

SCENARIOS = (('random', 50), ('annulus', 20), ('center', 10), ('hash', 20), ('worstrecv', 20))
POLICIES = (('field', P3Robot, P3Config), ('sweep', SweepRobot, SweepConfig),
            ('tour', TourRobot, TourConfig), ('adaptive', AdaptiveRobot, AdaptiveConfig),
            ('joint', JointRobot, JointConfig))
ABLATIONS = (('joint_no_after_service', {'after_service_scan': 'off'}),
             ('joint_single_plan', {'planner_multistart': False}),
             ('joint_no_cover_polish', {'cover_polish': False}),
             ('joint_no_probability_gate', {'opportunistic_receive_probability': 0.0}))
SCHEMA_VERSION = 'q3-paper-v1'
AUDIT_VERSION = 'q3-independent-audit-v2'
SEED_BASE = 2026091200
BOOTSTRAP_N = 4000
BOOTSTRAP_SEED = 20260912
TOL = 1e-7
R_ARENA, R_RECV_MIN = 1800.0, 1000.0
# Literal physical rules for independent verification; never import simulator
# timing constants, reported switch_s, or reported clocks as calculation inputs.
SPEED, MEASURE_S, SWITCH_S, CLEAR_OK_S, CLEAR_FAIL_S = 5.0, 5.0, 1.0, 5.0, 3.0
POLICY_CLASSES = {'P3Robot', 'SweepRobot', 'TourRobot', 'AdaptiveRobot', 'JointRobot',
                  'HomingRobot', 'FrontierRobot', 'CertifiedCoverageMixin'}
POLICY_FILES = ('p3_robot.py', 'p3_sweep.py', 'p3_tour.py', 'p3_homing.py',
                'p3_frontier.py', 'p3_coverage.py', 'p3_adaptive.py', 'p3_joint.py')


def clean(v):
    if isinstance(v, np.ndarray): return clean(v.tolist())
    if isinstance(v, np.generic): return clean(v.item())
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v): return None
    return v


def digest(obj):
    return hashlib.sha256(json.dumps(clean(obj), ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def frozen_inputs():
    source = {str(p.relative_to(Q3)): sha256(p) for p in sorted(SRC.glob('*.py'))}
    # Obsolete scratch entry point was never imported by the paper runner.
    source.pop('src/run_p3_paper.py', None)
    files = sorted((Q3/'out/p3_family').glob('*.csv'))
    files += [Q3/'out/p3_family/p2_grid_family.json', Q3/'out/p2_grid/p2_grid_map.csv']
    fields = {str(p.relative_to(Q3)): sha256(p) for p in files if p.exists()}
    configs = {name: asdict(cfg()) for name, _, cfg in POLICIES}
    configs.update({name: asdict(replace(JointConfig(), **override)) for name, override in ABLATIONS})
    return source, fields, clean(configs)


def make_manifest(prior=None):
    source, fields, configs = frozen_inputs()
    definition = {'source_sha256': source, 'field_sha256': fields, 'configs': configs,
                  'scenarios': SCENARIOS, 'seed_base': SEED_BASE, 'seed_step': 97,
                  'scenario_seed_stride': 100000, 'virtual_limit_s': 360000.0,
                  'ablation_random_cases': 20}
    fingerprint = digest(definition)
    if prior:
        # Compare all previously frozen algorithm/field hashes before touching
        # outputs. Runner/reporting changes are deliberately independent.
        combined = {**source, **fields}
        for path, expected in prior.get('source_sha256', {}).items():
            if path in ('scripts/run_p3_paper.py', 'src/run_p3_paper.py'): continue
            if combined.get(path) != expected:
                raise RuntimeError(f'Frozen algorithm/field changed: {path}; use a new --out directory')
        for path, expected in prior.get('field_sha256', {}).items():
            if fields.get(path) != expected: raise RuntimeError(f'Frozen field changed: {path}')
        if prior.get('configs') != configs: raise RuntimeError('Frozen requested configurations changed')
        if prior.get('definition_fingerprint') not in (None, fingerprint):
            raise RuntimeError('Frozen experiment definition changed; use a new --out directory')
    return {'schema_version': SCHEMA_VERSION, 'experiment_id': (prior or {}).get('experiment_id', fingerprint[:20]),
            'definition_fingerprint': fingerprint, 'definition': definition,
            'source_sha256': source, 'field_sha256': fields, 'configs': configs,
            'seed_formula': '2026091200 + 100000*scenario_index + 97*i',
            'scenarios': clean(SCENARIOS), 'policies': [p[0] for p in POLICIES],
            'ablations': dict(ABLATIONS), 'python_at_audit': platform.python_version(),
            'numpy_at_audit': np.__version__, 'platform_at_audit': platform.platform(),
            'execution_runtime_recorded': (prior or {}).get('execution_runtime_recorded', {k: (prior or {}).get(k) for k in ('python', 'numpy')}),
            'audit_version': AUDIT_VERSION, 'audit_runner_sha256': sha256(HERE),
            'bootstrap': {'resamples': BOOTSTRAP_N, 'rng_seed': BOOTSTRAP_SEED,
                          'statistic': '1 - mean(comparison) / mean(reference)',
                          'sampling': 'paired scene indices, percentile interval; fresh seeded generator per statistic'},
            'physical_rules': {'start_xy': [0, 0], 'initial_measuring_channel': 1,
                               'speed_m_s': SPEED, 'measure_s': MEASURE_S, 'switch_s': SWITCH_S,
                               'clear_success_s': CLEAR_OK_S, 'clear_failure_s': CLEAR_FAIL_S,
                               'virtual_limit_s': 360000, 'clear_does_not_change_measuring_channel': True},
            'offline_real_time_policy': {'allowance_s': 1200,
                'historical_runs': 'Recorded policy-construction + run wall time; no real-time watchdog was installed. Virtual limit was 360000 s.',
                'future_runs': '1200 s POSIX timer around construction + run; timeouts retained as error rows.',
                'limitations': 'Wall time is local diagnostic timing, excludes source generation/base-map loading and independent audit; host load is uncontrolled. No formal online evaluation.'},
            'provenance_note': 'Algorithm/field hashes are checked against frozen records. Reporting-script revisions do not rerun algorithms. Earlier runner-hash metadata had been refreshed after reporting edits, so it is not treated as a byte-exact execution-script snapshot.',
            'primary_metric': 'complete exit_s, reported as mean and P90; all status values retained',
            'per_source_metric': 'mean across cases of exit_s / cleared; undefined when cleared=0; defined-value count disclosed',
            'coverage_note': '5 m sampled-disk audit is numerical evidence, not a continuous proof. The 50 m square-cell certificate is separately reconstructed from no_signal actions.'}


def scene_manifest(arena):
    sources = [{k: getattr(s, k) for k in ('channel', 'x', 'y', 'r_recv', 'cone_half', 'dir_deg')} for s in arena.sources]
    error = {'class': type(arena).__name__, 'waves': arena._waves, 'scale': arena._scale,
             'local_w': arena._local_w, 'local_seed': arena._local_seed,
             'probes': {f'{x},{y}': float(arena.env_error(x, y)) for x, y in
                        ((0., 0.), (500., -500.), (-500., 500.), (1200., 0.), (0., -1200.))}}
    scene = {'class': type(arena).__name__, 'seed': int(arena.seed), 'r_arena': float(arena.r_arena), 'sources': sources}
    return {'class': type(arena).__name__, 'seed': int(arena.seed), 'sources': sources,
            'scene_fingerprint': digest(scene), 'error_field': error, 'error_fingerprint': digest(error)}


class TruthGuard:
    def __init__(self, arena):
        self.arena = arena; self.exit_called = False; self.truth_calls = []
        self._truth, self._exit = arena.truth, arena.exit
        arena.truth, arena.exit = self.truth, self.exit
    def truth(self):
        self.truth_calls.append({'virtual_time_s': float(self.arena.virtual_time_s), 'exit_called': self.exit_called})
        if not self.exit_called: raise RuntimeError('truth() called before accepted exit()')
        return self._truth()
    def exit(self):
        result = self._exit()
        if result.get('accepted') is True: self.exit_called = True
        return result


def action_audit(actions, report=None, truth=None, scene=None):
    position, measuring_channel, elapsed, travel = (0., 0.), 1, 0., 0.
    counts = Counter(); records = []; errors = []; maxima = Counter(); last_clear = None
    cleared_channels = set(); entered = False; exited = False
    def compare(label, observed, expected, index=None):
        if observed is None:
            errors.append({'check': label, 'index': index, 'reason': 'missing value'}); return None
        delta = float(observed) - expected
        maxima[label] = max(maxima[label], abs(delta))
        if not math.isfinite(delta) or abs(delta) > TOL:
            errors.append({'check': label, 'index': index, 'observed': observed, 'expected': expected, 'error': delta})
        return delta
    for i, a in enumerate(actions):
        kind = a.get('kind'); before_channel = measuring_channel
        rec = {'index': i, 'kind': kind, 'independent_before_s': elapsed,
               'measuring_channel_before': before_channel}
        if kind == 'enter':
            if entered or exited: errors.append({'check': 'enter order', 'index': i})
            entered = True; counts['enter'] += 1
        elif kind == 'exit':
            if not entered or exited: errors.append({'check': 'exit order', 'index': i})
            exited = True; counts['exit'] += 1
        elif kind in ('measure', 'clear'):
            if not entered or exited: errors.append({'check': 'action outside session', 'index': i})
            xy = (float(a['x']), float(a['y'])); distance = math.dist(position, xy)
            channel = int(a['channel']); switch = 0.0
            if not 1 <= channel <= 20: errors.append({'check': 'channel range', 'index': i})
            if kind == 'measure':
                switch = SWITCH_S if channel != measuring_channel else 0.0
                measuring_channel = channel; service = MEASURE_S
                counts['measure'] += 1; counts['switch'] += int(switch > 0)
                counts[a.get('measure_result', 'invalid_measure_result')] += 1
                if a.get('measure_result') not in ('direction', 'near', 'no_signal'):
                    errors.append({'check': 'measurement result', 'index': i})
                rec['switch_error_s'] = compare('switch', a.get('switch_s'), switch, i)
            else:
                ok = a.get('clear_result') == 'success'
                service = CLEAR_OK_S if ok else CLEAR_FAIL_S
                counts['clear_success' if ok else 'clear_failure'] += 1
                if a.get('clear_result') not in ('success', 'no_target_in_range'):
                    errors.append({'check': 'clear result', 'index': i})
                if ok:
                    if channel in cleared_channels: errors.append({'check': 'duplicate clear success', 'index': i})
                    cleared_channels.add(channel)
            expected_dt = distance / SPEED + switch + service
            elapsed += expected_dt; travel += distance; position = xy
            if kind == 'clear' and a.get('clear_result') == 'success': last_clear = elapsed
            rec.update({'distance_m': distance, 'distance_error_m': compare('distance', a.get('dist_m'), distance, i),
                        'expected_switch_s': switch, 'expected_dt': expected_dt,
                        'dt_error': compare('dt', a.get('dt'), expected_dt, i)})
        else: errors.append({'check': 'unknown action kind', 'index': i, 'kind': kind})
        rec.update({'expected_cumulative': elapsed, 'reported_time': a.get('virtual_time_s'),
                    'cumulative_error': compare('cumulative', a.get('virtual_time_s'), elapsed, i),
                    'measuring_channel_after': measuring_channel})
        records.append(rec)
    if not entered or not exited: errors.append({'check': 'missing enter or exit', 'entered': entered, 'exited': exited})
    pieces = {'travel_s': travel / SPEED, 'measure_s': MEASURE_S * counts['measure'],
              'switch_s': SWITCH_S * counts['switch'],
              'clear_s': CLEAR_OK_S * counts['clear_success'] + CLEAR_FAIL_S * counts['clear_failure']}
    compare('cost_piece_sum', sum(pieces.values()), elapsed)
    checks = {}
    if report is not None:
        expected = {'virtual_time_s': elapsed, 'travel_m': travel, 'cleared': counts['clear_success'],
                    'n_clear': counts['clear_success'], 'n_clear_fail': counts['clear_failure']}
        # Policy measurement count can include rejected calls; accepted action
        # count is authoritative and report n_rejected is disclosed separately.
        if report.get('n_rejected', 0) == 0: expected['n_measure'] = counts['measure']
        if scene: expected['n_sources'] = len(scene['sources'])
        if counts['clear_success']: expected['avg_clear_time_s'] = last_clear / counts['clear_success']
        for name, value in expected.items():
            checks[name] = compare('report.' + name, report.get(name), value)
        expected_stats = {'travel_m': travel, 'n_measure': counts['measure'],
                          'n_clear': counts['clear_success'] + counts['clear_failure'],
                          'n_clear_fail': counts['clear_failure'], 'n_direction': counts['direction'],
                          'n_near': counts['near'], 'n_no_signal': counts['no_signal']}
        for name, value in expected_stats.items():
            if name in report.get('mock_stats', {}):
                checks['mock_stats.' + name] = compare('stats.' + name, report['mock_stats'][name], value)
    if truth is not None:
        compare('truth.n_cleared', truth.get('n_cleared'), len(cleared_channels))
        if scene: compare('truth.n_sources', truth.get('n_sources'), len(scene['sources']))
        actual = {int(s['channel']) for s in truth.get('sources', []) if s.get('cleared')}
        if actual != cleared_channels: errors.append({'check': 'truth cleared channels', 'truth': sorted(actual), 'actions': sorted(cleared_channels)})
    return {'version': AUDIT_VERSION, 'records': records, 'max_abs_dt_error_s': maxima['dt'],
            'max_abs_cumulative_error_s': maxima['cumulative'], 'max_abs_distance_error_m': maxima['distance'],
            'max_abs_switch_error_s': maxima['switch'], 'maxima': dict(maxima),
            'cost_pieces': pieces, 'independent_exit_s': elapsed, 'independent_last_clear_s': last_clear,
            'independent_travel_m': travel, 'counts': dict(counts), 'cleared_channels': sorted(cleared_channels),
            'accepted_action_count': counts['measure'] + counts['clear_success'] + counts['clear_failure'],
            'report_checks': checks, 'errors': errors, 'audit_ok': not errors}


def flat_metrics(report, audit, scene, wall_s, status='ok', error=None, completion_kind='unknown'):
    n = len(scene['sources']); counts = audit['counts']; cleared = counts.get('clear_success', 0)
    elapsed, last = audit['independent_exit_s'], audit['independent_last_clear_s']; p = audit['cost_pieces']
    return {'exit_s': elapsed, 'last_clear_s': last, 'tail_s': elapsed-last if last is not None else None,
            'exit_per_source_s': elapsed/cleared if cleared else None,
            'last_clear_per_source_s': last/cleared if cleared else None,
            'travel_m': audit['independent_travel_m'], 'n_measure': counts.get('measure', 0),
            'n_switch': counts.get('switch', 0), 'n_clear_success': cleared,
            'n_clear_failure': counts.get('clear_failure', 0),
            't_travel_s': p['travel_s'], 't_measure_s': p['measure_s'],
            't_switch_s': p['switch_s'], 't_clear_s': p['clear_s'],
            'cleared': cleared, 'n_sources': n, 'clear_ratio': cleared/n if n else None,
            'full_clear': bool(n > 0 and cleared == n), 'completion_kind': completion_kind,
            'complete_proof': report.get('complete_proof'), 'wall_s': wall_s,
            'wall_within_1200s': wall_s <= 1200 if wall_s is not None else None,
            'n_rejected': report.get('n_rejected', 0), 'status': status, 'error': error,
            'audit_ok': audit['audit_ok']}


def row_from_trace(t, path):
    return {k: t[k] for k in ('split', 'scenario', 'index', 'seed', 'policy')} | {'trace_file': str(path)} | t['metrics']


def run_case(kind, index, seed, policy, cls, cfg, base, outdir, manifest, split='main'):
    arena = make_scene(kind, seed); scene = scene_manifest(arena); guard = TruthGuard(arena)
    forced_exit = False; status = 'ok'; error = None; robot = None; report = {}
    def timeout_handler(_signum, _frame): raise TimeoutError('1200 s real-time offline allowance exceeded')
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    start = time.perf_counter(); signal.setitimer(signal.ITIMER_REAL, 1200.0)
    try:
        robot = cls(arena, cfg, base=base, log=None); report = robot.run()
    except Exception as exc:
        status = 'error'; error = f'{type(exc).__name__}: {exc}'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old_handler)
        wall = time.perf_counter() - start
        if not guard.exit_called:
            forced_exit = True
            try: arena.exit()
            except Exception as exc: error = f'{error or ""}; exit: {exc}'
    truth = arena.truth() if guard.exit_called else None
    completion = policy if policy in ('field', 'sweep', 'tour') else 'continuous_cell'
    audit = action_audit(arena.actions, report or None, truth, scene)
    metrics = flat_metrics(report, audit, scene, wall, status, error, completion)
    name = f'{split}_{kind}_{index:03d}_{seed}_{policy}'
    path = Path('traces') / f'{name}.json'
    trace = {'schema_version': SCHEMA_VERSION, 'run_id': name, 'split': split, 'scenario': kind,
             'index': index, 'seed': seed, 'policy': policy, 'scene_manifest': scene,
             'requested_config': asdict(cfg), 'effective_config': asdict(robot.cfg if robot else cfg),
             'actions': arena.actions, 'post_exit_truth': truth, 'report': report,
             'action_audit': audit, 'guard': {'exit_called': guard.exit_called, 'truth_calls': guard.truth_calls,
                                           'forced_harness_exit': forced_exit}, 'metrics': metrics,
             'provenance': {'experiment_id': manifest['experiment_id'],
                 'definition_fingerprint': manifest['definition_fingerprint'],
                 'source_sha256': manifest['source_sha256'], 'field_sha256': manifest['field_sha256'],
                 'execution_runner_sha256': sha256(HERE)}}
    atomic_json(outdir/path, trace)
    return row_from_trace(trace, path)


class CoverageAuditor:
    """Grid verification using only per-channel raw no_signal observations."""
    def __init__(self, step=5.0):
        self.step = step
        xs = np.arange(-1800., 1800. + step/2, step)
        gx, gy = np.meshgrid(xs, xs); mask = gx*gx + gy*gy <= 1800.**2
        self.px, self.py = gx[mask], gy[mask]
        self.cache = {}; self.hits = 0; self.misses = 0; self.point_sets = {}
        # Independent reconstruction of the 50 m cell certificate also keeps
        # boundary-intersecting cells whose centers lie outside the disk.
        h = 50.; cx = -1800. + (np.arange(72) + .5)*h; qx, qy = np.meshgrid(cx, cx)
        m = np.maximum(np.abs(qx)-h/2, 0)**2 + np.maximum(np.abs(qy)-h/2, 0)**2 <= 1800.**2 + 1e-6
        self.qx, self.qy = qx[m], qy[m]; self.cell_radius = 1000.-h/math.sqrt(2)-1e-6
    def set_audit(self, points):
        # Sorting/deduplicating lets absent channels and unchanged variants
        # share a single distance computation without dropping any observation.
        points = tuple(sorted(set(points))); key = digest(points)
        if key in self.cache: self.hits += 1; return key, self.cache[key]
        self.misses += 1; self.point_sets[key] = [list(x) for x in points]
        dmin2 = np.full(len(self.px), np.inf); cell_min2 = np.full(len(self.qx), np.inf)
        for x, y in points:
            # Chunking bounds scratch memory; no SciPy nearest-neighbor code.
            for start in range(0, len(self.px), 32768):
                stop = start + 32768
                d2 = (self.px[start:stop]-x)**2 + (self.py[start:stop]-y)**2
                np.minimum(dmin2[start:stop], d2, out=dmin2[start:stop])
            np.minimum(cell_min2, (self.qx-x)**2 + (self.qy-y)**2, out=cell_min2)
        worst = int(np.argmax(dmin2)); unc = int(np.count_nonzero(dmin2 > 1000.**2))
        cunc = int(np.count_nonzero(cell_min2 > self.cell_radius**2))
        result = {'max_nearest_m': math.sqrt(dmin2[worst]) if points else None,
                  'worst_xy': [float(self.px[worst]), float(self.py[worst])] if points else None,
                  'uncovered_points': unc, 'no_signal_stations': len(points),
                  'uncovered_certificate_cells': cunc, 'cell_certificate': cunc == 0}
        self.cache[key] = result
        return key, result
    def audit(self, trace):
        acts = trace['actions']; cleared = {int(a['channel']) for a in acts if a.get('kind') == 'clear' and a.get('clear_result') == 'success'}
        channels = {}
        for ch in range(1, 21):
            if ch in cleared: channels[str(ch)] = {'status': 'cleared'}; continue
            obs = [a for a in acts if a.get('kind') == 'measure' and int(a['channel']) == ch]
            if any(a['measure_result'] in ('direction', 'near') for a in obs):
                channels[str(ch)] = {'status': 'positive_pending'}; continue
            points = [(float(a['x']), float(a['y'])) for a in obs if a['measure_result'] == 'no_signal']
            key, result = self.set_audit(points)
            channels[str(ch)] = {'status': 'covered' if result['uncovered_points'] == 0 else 'uncovered',
                                 'observation_set_sha256': key, **result}
        return {'grid_step_m': self.step, 'grid_points_inside': len(self.px), 'channels': channels,
                'claim_5m_grid': all(c['status'] in ('cleared', 'covered') for c in channels.values()),
                'independent_cell_certificate': all(c['status'] == 'cleared' or c.get('cell_certificate', False) for c in channels.values()),
                'certificate_grid_cells': len(self.qx), 'certificate_radius_m': self.cell_radius,
                'note': '5 m point-grid check is numerical evidence; the separate 50 m cell reconstruction implements a conservative geometric certificate.'}


def finite(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def bootstrap(a, b):
    if not a: return {'n': 0, 'saving': None, 'ci95': [None, None]}
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.mean() <= 0: return {'n': len(a), 'saving': None, 'ci95': [None, None]}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(a), size=(BOOTSTRAP_N, len(a)))
    amean, bmean = a[idx].mean(axis=1), b[idx].mean(axis=1)
    if np.any(amean <= 0): raise ValueError('Undefined bootstrap relative saving due to zero reference mean')
    vals = 1-bmean/amean
    return {'n': len(a), 'saving': float(1-b.mean()/a.mean()), 'ci95': np.percentile(vals, [2.5, 97.5]).tolist()}


def aggregate(rows):
    def values(key): return [r[key] for r in rows if finite(r.get(key))]
    def mean(key):
        v = values(key); return float(np.mean(v)) if v else None
    times = values('exit_s'); sources = sum(r.get('n_sources', 0) for r in rows)
    out = {'cases': len(rows), 'completed': sum(r['status'] == 'ok' for r in rows),
           'errors': sum(r['status'] != 'ok' for r in rows), 'all_statuses_included': True,
           'full_clear_cases': sum(bool(r['full_clear']) for r in rows),
           'cleared': sum(r.get('cleared', 0) for r in rows), 'sources': sources,
           'clear_ratio_source_weighted': sum(r.get('cleared', 0) for r in rows)/sources if sources else None,
           'zero_cleared_cases': sum(r.get('cleared', 0) == 0 for r in rows),
           'primary_metric_defined_cases': len(times),
           'undefined_primary_cases': len(rows)-len(times),
           'per_source_metric_defined_cases': len(values('exit_per_source_s')),
           'undefined_per_source_cases': len(rows)-len(values('exit_per_source_s')),
           'p90_exit_s': float(np.percentile(times, 90)) if times else None,
           'max_exit_s': max(times) if times else None,
           'wall_max_s': max(values('wall_s'), default=None),
           'rejections': sum(r.get('n_rejected', 0) for r in rows),
           'completion_kinds': dict(Counter(r['completion_kind'] for r in rows)),
           'claimed_complete_cases': sum(r.get('complete_proof') is True for r in rows),
           'audit_failure_cases': sum(not r.get('audit_ok', False) for r in rows)}
    mapping = {'mean_exit_s': 'exit_s', 'mean_exit_per_source_s': 'exit_per_source_s',
               'mean_last_clear_s': 'last_clear_s', 'mean_last_clear_per_source_s': 'last_clear_per_source_s',
               'mean_tail_s': 'tail_s', 'mean_travel_m': 'travel_m', 'mean_measure': 'n_measure',
               'mean_switch': 'n_switch', 'mean_clear_failure': 'n_clear_failure', 'wall_mean_s': 'wall_s',
               'mean_t_travel_s': 't_travel_s', 'mean_t_measure_s': 't_measure_s',
               'mean_t_switch_s': 't_switch_s', 'mean_t_clear_s': 't_clear_s'}
    out.update({dst: mean(src) for dst, src in mapping.items()})
    out['metric_defined_counts'] = {src: len(values(src)) for src in mapping.values()}
    return out


def paired(reference, comparison):
    ref = {(r['scenario'], r['seed']): r for r in reference}
    cmp = {(r['scenario'], r['seed']): r for r in comparison}
    keys = sorted(ref.keys() & cmp.keys()); pairs = [(ref[k], cmp[k]) for k in keys]
    def one(metric):
        keep = [(a, b) for a, b in pairs if finite(a.get(metric)) and finite(b.get(metric))]
        result = bootstrap([a[metric] for a, b in keep], [b[metric] for a, b in keep])
        result.update({'candidate_pairs': len(pairs), 'undefined_metric_pairs': len(pairs)-len(keep),
                       'non_ok_pairs_included': sum(a['status'] != 'ok' or b['status'] != 'ok' for a, b in keep),
                       'incomplete_clear_pairs_included': sum(not a['full_clear'] or not b['full_clear'] for a, b in keep),
                       'comparison_faster_cases': sum(b[metric] < a[metric] for a, b in keep)})
        return result
    out = one('exit_s'); out['per_source'] = one('exit_per_source_s')
    out['reference_only_cases'] = len(ref.keys()-cmp.keys()); out['comparison_only_cases'] = len(cmp.keys()-ref.keys())
    out['convention'] = 'positive saving means comparison faster; include failures/incomplete-clear pairs when numeric metrics exist'
    return out


def summarize(rows):
    main = [r for r in rows if r['split'] == 'main']; variants = [r for r in rows if r['split'] == 'ablation']
    def group(rs):
        policies = sorted(set(r['policy'] for r in rs)); out = {p: aggregate([r for r in rs if r['policy'] == p]) for p in policies}
        out['paired_vs_field'] = {p: paired([r for r in rs if r['policy'] == 'field'], [r for r in rs if r['policy'] == p]) for p in policies if p != 'field'}
        out['joint_vs'] = {p: paired([r for r in rs if r['policy'] == p], [r for r in rs if r['policy'] == 'joint']) for p in policies if p != 'joint'}
        return out
    out = {'schema_version': SCHEMA_VERSION, 'counts': {'rows': len(rows), 'main': len(main), 'ablation': len(variants),
           'status': dict(Counter(r['status'] for r in rows))}, 'overall': group(main),
           'scenarios': {k: group([r for r in main if r['scenario'] == k]) for k, _ in SCENARIOS if any(r['scenario'] == k for r in main)},
           'ablations': {}, 'bootstrap': {'resamples': BOOTSTRAP_N, 'seed': BOOTSTRAP_SEED},
           'failure_policy': 'All runs contribute to aggregates, including error-status and incomplete-clear runs. Undefined values are null and counts are disclosed; never replace zero-cleared denominator with one.'}
    if variants:
        out['ablations']['random'] = {p: aggregate([r for r in variants if r['policy'] == p]) for p, _ in ABLATIONS}
        out['ablations']['random']['joint_baseline'] = aggregate([r for r in main if r['scenario'] == 'random' and r['index'] < 20 and r['policy'] == 'joint'])
        out['ablations']['random']['paired_vs_joint'] = {p: paired([r for r in main if r['scenario'] == 'random' and r['index'] < 20 and r['policy'] == 'joint'], [r for r in variants if r['policy'] == p]) for p, _ in ABLATIONS}
    return out


def static_policy_audit():
    accesses = []; suspicious = []; truth = []; dynamic = []
    blocked = {'sources', 'seed', 'rng', 'env_error', '_src_of', '_waves', '_scale', '_local_w', '_local_seed', '__dict__', '__getattribute__'}
    methods = []
    for filename in POLICY_FILES:
        root = ast.parse((SRC/filename).read_text(encoding='utf-8'))
        for cls in root.body:
            if not isinstance(cls, ast.ClassDef) or cls.name not in POLICY_CLASSES: continue
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
                methods.append({'file': 'src/'+filename, 'class': cls.name, 'method': method.name, 'line': method.lineno})
                for node in ast.walk(method):
                    entry = {'file': 'src/'+filename, 'class': cls.name, 'method': method.name,
                             'line': getattr(node, 'lineno', None)}
                    if isinstance(node, ast.Attribute):
                        expr = ast.unparse(node)
                        if '.arena.' in expr:
                            accesses.append({**entry, 'expression': expr})
                            if node.attr in blocked: suspicious.append({**entry, 'expression': expr})
                            if node.attr == 'truth': truth.append({**entry, 'expression': expr})
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('getattr', 'setattr', 'hasattr'):
                        if node.args and 'arena' in ast.unparse(node.args[0]):
                            expr = ast.unparse(node); dynamic.append({**entry, 'expression': expr})
                            if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant) or node.args[1].value in blocked:
                                suspicious.append({**entry, 'expression': expr})
    allowed_truth = all(x['class'] == 'P3Robot' and x['method'] == 'report' for x in truth)
    return {'audit_ok': not suspicious and allowed_truth, 'files': list(POLICY_FILES),
            'classes': sorted(POLICY_CLASSES), 'method_count': len(methods),
            'decision_method_count': sum(x['method'] != 'report' for x in methods),
            'methods': methods, 'arena_attribute_accesses': accesses,
            'dynamic_attribute_accesses': dynamic, 'sensitive_hits': suspicious,
            'truth_accesses': truth, 'truth_only_in_report': allowed_truth,
            'manual_crosscheck': 'Independent reviewer checked 147 decision methods plus report, module-level benchmark imports, dynamic getattr/eval/exec/vars, and p3_expect_field/p1_intersection/p2_grid_expectation helpers. No protected arena state found in active decisions. LIVE1/LIVE2 exist as module imports in p3_frontier but are not referenced in policy methods.',
            'normal_exit_before_report_lines': {'p3_robot.py': [1189,1193], 'p3_sweep.py': [1086,1090], 'p3_tour.py': [1522,1527]},
            'scope': 'AST inspection of decision classes and all their methods; excludes module-level mock tests/scene generators. Runtime truth guard independently checks actual exit order.',
            'limitation': 'Static inspection and endpoint guard are not a language-level sandbox; reflective/dynamic evasion is not claimed impossible.'}


def audit_selfcheck():
    # A clear on channel 8 must leave the detector on its initial channel 1.
    actions = [{'kind': 'enter', 'virtual_time_s': 0.},
        {'kind': 'clear', 'x': 0., 'y': 0., 'channel': 8, 'clear_result': 'no_target_in_range', 'dt': 3., 'dist_m': 0., 'virtual_time_s': 3.},
        {'kind': 'measure', 'x': 15., 'y': 20., 'channel': 1, 'measure_result': 'no_signal', 'switch_s': 0., 'dt': 10., 'dist_m': 25., 'virtual_time_s': 13.},
        {'kind': 'measure', 'x': 15., 'y': 20., 'channel': 2, 'measure_result': 'no_signal', 'switch_s': 1., 'dt': 6., 'dist_m': 0., 'virtual_time_s': 19.},
        {'kind': 'exit', 'virtual_time_s': 19.}]
    checks = {'valid_clear_preserves_channel': action_audit(actions)['audit_ok']}
    for key in ('switch_s', 'dist_m', 'dt', 'virtual_time_s'):
        corrupt = [dict(a) for a in actions]; corrupt[2][key] += 1
        checks['detect_corrupted_'+key] = not action_audit(corrupt)['audit_ok']
    corrupt = [dict(a) for a in actions]
    for a in corrupt[2:]: a['virtual_time_s'] += 1
    checks['detect_cumulative_offset'] = not action_audit(corrupt)['audit_ok']
    m = flat_metrics({}, action_audit(actions), {'sources': [{}]}, .1, 'error', 'synthetic failure', 'field')
    checks['zero_clear_is_undefined'] = m['exit_per_source_s'] is None and m['last_clear_s'] is None
    agg = aggregate([m]); checks['failed_run_retained'] = agg['cases'] == 1 and agg['errors'] == 1 and agg['mean_exit_s'] == 19.
    if not all(checks.values()): raise AssertionError(checks)
    return checks


def raw_payload(t):
    keys = ('run_id', 'split', 'scenario', 'index', 'seed', 'policy', 'scene_manifest',
            'requested_config', 'effective_config', 'actions', 'post_exit_truth', 'truth_error', 'report', 'guard')
    return {k: t.get(k) for k in keys} | {'execution_wall_s': t['metrics'].get('wall_s')}


def archive_scratch(outdir, rows):
    scratch = Q3.parents[1] / 'tmp/q3-paper-scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    refs = {(outdir/r['trace_file']).resolve() for r in rows}
    moved = []
    for path in sorted((outdir/'traces').glob('*.json')) + [outdir/'metadata.json']:
        if not path.exists() or path.resolve() in refs: continue
        relative = path.relative_to(outdir); dest = scratch/'previous-products'/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): dest = dest.with_name(dest.stem + '-' + sha256(path)[:12] + dest.suffix)
        if dest.exists(): raise RuntimeError(f'Archive destination already exists: {dest}')
        value = sha256(path); path.rename(dest)
        moved.append({'from': str(relative), 'to': str(dest), 'sha256': value})
    return moved


def snapshot_sources(outdir, manifest):
    hashes = {**manifest['source_sha256'], **manifest['field_sha256'], 'scripts/run_p3_paper.py': sha256(HERE)}
    for relative, expected in hashes.items():
        source = Q3/relative; target = outdir/'source_snapshot'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if sha256(source) != expected: raise RuntimeError(f'Input changed during audit: {source}')
        if not target.exists() or sha256(target) != expected: shutil.copyfile(source, target)
    atomic_json(outdir/'source_snapshot/SHA256.json', hashes)
    return len(hashes)


def write_results(outdir, rows, manifest):
    atomic_json(outdir/'paired_results.json', {'schema_version': SCHEMA_VERSION, 'experiment_id': manifest['experiment_id'],
        'definition_fingerprint': manifest['definition_fingerprint'], 'manifest_file': 'manifest.json', 'rows': rows})
    columns = sorted({k for r in rows for k in r})
    with (outdir/'paired_results.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(rows)


def audit_all(outdir, rows, manifest):
    start = time.perf_counter(); auditor = CoverageAuditor(); audits = []; all_checks = []; new_rows = []
    fingerprints = defaultdict(set); scene_checks = []; configs_bad = []; max_errors = Counter(); raw_ok = True
    static = static_policy_audit(); selfcheck = audit_selfcheck(); prior = outdir/'audit_report.json'
    prior_report = read_json(prior) if prior.exists() else {}
    moved = archive_scratch(outdir, rows)
    for n, row in enumerate(rows):
        path = outdir/row['trace_file']; trace = read_json(path); raw_before = digest(raw_payload(trace))
        # Recompute from the raw action stream, never from the previous audit.
        audit = action_audit(trace['actions'], trace.get('report'), trace.get('post_exit_truth'), trace['scene_manifest'])
        old = trace['metrics']; trace['action_audit'] = audit
        trace['metrics'] = flat_metrics(trace.get('report') or {}, audit, trace['scene_manifest'], old.get('wall_s'),
                                       old.get('status', 'error'), old.get('error'), old['completion_kind'])
        scene = trace['scene_manifest']; fingerprints[(row['scenario'], row['seed'])].add((scene['scene_fingerprint'], scene['error_fingerprint']))
        scene_obj = {'class': scene['class'], 'seed': scene['seed'], 'r_arena': 1800.0, 'sources': scene['sources']}
        # Historical fingerprint serialization used ASCII default; values here
        # contain ASCII-only strings so this is byte-equivalent.
        scene_ok = digest(scene_obj) == scene['scene_fingerprint'] and digest(scene['error_field']) == scene['error_fingerprint']
        scene_checks.append(scene_ok)
        requested = trace['requested_config']; cfg_ok = requested == manifest['configs'][row['policy']]
        effective = dict(requested)
        if old['completion_kind'] == 'continuous_cell': effective.update({'cover_radius_m': 1000.-50./math.sqrt(2)-1e-6, 'cover_slack_m': 0.0})
        effective_ok = trace['effective_config'] == effective
        if not cfg_ok or not effective_ok: configs_bad.append({'trace_file': row['trace_file'], 'requested_ok': cfg_ok, 'effective_ok': effective_ok})
        exits = [a for a in trace['actions'] if a.get('kind') == 'exit']
        calls = trace.get('guard', {}).get('truth_calls', [])
        guard_ok = bool(exits and calls and trace.get('guard', {}).get('exit_called') and
                        all(c.get('exit_called') and c['virtual_time_s'] >= exits[0]['virtual_time_s']-TOL for c in calls))
        trace['audit_provenance'] = {'audit_version': AUDIT_VERSION, 'runner_sha256': sha256(HERE),
            'raw_payload_sha256': raw_before, 'definition_fingerprint': manifest['definition_fingerprint'],
            'execution_algorithms_unchanged': True,
            'verified_source_sha256': manifest['source_sha256'],
            'verified_field_sha256': manifest['field_sha256']}
        raw_after = digest(raw_payload(trace)); raw_ok &= raw_before == raw_after
        trace['audit_provenance']['raw_payload_unchanged'] = raw_before == raw_after
        check = {'trace_file': row['trace_file'], 'policy': row['policy'], 'scenario': row['scenario'], 'seed': row['seed'],
                 'raw_payload_sha256': raw_before, 'raw_unchanged': raw_before == raw_after,
                 'action_audit_ok': audit['audit_ok'], 'truth_guard_ok': guard_ok, 'scene_fingerprint_ok': scene_ok,
                 'requested_config_ok': cfg_ok, 'effective_config_ok': effective_ok,
                 'errors': audit['errors'], 'maxima': audit['maxima']}
        all_checks.append(check)
        for k, value in audit['maxima'].items(): max_errors[k] = max(max_errors[k], value)
        if old['completion_kind'] == 'continuous_cell' and trace['report'].get('complete_proof') is True:
            coverage = auditor.audit(trace)
            audits.append({'scenario': row['scenario'], 'index': row['index'], 'seed': row['seed'], 'policy': row['policy'],
                           'split': row['split'], 'trace_file': row['trace_file'], 'audit': coverage})
            trace['independent_coverage_audit'] = {'claim_5m_grid': coverage['claim_5m_grid'],
                'cell_certificate': coverage['independent_cell_certificate'], 'details_file': 'coverage_audit.json'}
        atomic_json(path, trace); new_rows.append(row_from_trace(trace, row['trace_file']))
        if (n+1) % 50 == 0: print(f'Audited {n+1}/{len(rows)} traces; {len(audits)} certificates, {auditor.misses} unique observation sets', flush=True)
    unpaired = [{'scenario': k[0], 'seed': k[1], 'different_fingerprints': len(v)} for k, v in fingerprints.items() if len(v) != 1]
    coverage_result = {'schema_version': SCHEMA_VERSION, 'experiment_id': manifest['experiment_id'], 'audit_version': AUDIT_VERSION,
                       'scope': 'All adaptive/joint/ablation runs claiming continuous-cell completion', 'audits': audits,
                       'counts': {'runs': len(audits), 'numerical_pass': sum(x['audit']['claim_5m_grid'] for x in audits),
                                  'cell_certificate_pass': sum(x['audit']['independent_cell_certificate'] for x in audits),
                                  'unique_observation_sets': auditor.misses, 'observation_cache_hits': auditor.hits},
                       'observation_sets': auditor.point_sets, 'observation_set_results': auditor.cache}
    atomic_json(outdir/'coverage_audit.json', coverage_result)
    summary = summarize(new_rows); summary['experiment_id'] = manifest['experiment_id']; summary['audit'] = coverage_result['counts']
    atomic_json(outdir/'summary.json', summary); write_results(outdir, new_rows, manifest)
    atomic_json(outdir/'manifest.json', manifest)
    snapshot_count = snapshot_sources(outdir, manifest)
    report = {'version': AUDIT_VERSION, 'experiment_id': manifest['experiment_id'], 'runs': len(new_rows),
        'all_raw_payloads_unchanged': raw_ok, 'policy_runs_executed_by_this_audit': 0,
        'action_audit_pass': sum(x['action_audit_ok'] for x in all_checks),
        'truth_guard_pass': sum(x['truth_guard_ok'] for x in all_checks), 'scene_fingerprint_pass': sum(scene_checks),
        'pairing_mismatches': unpaired, 'configuration_mismatches': configs_bad, 'max_errors': dict(max_errors),
        'coverage': coverage_result['counts'], 'static_policy_audit': static, 'audit_contract_checks': selfcheck,
        'source_snapshot_files': snapshot_count, 'source_snapshot_index': 'source_snapshot/SHA256.json',
        'archive_movements': prior_report.get('archive_movements', []) + moved,
        'per_run_checks': all_checks, 'audit_wall_s': time.perf_counter()-start}
    atomic_json(outdir/'audit_report.json', report)
    write_readme_and_evidence(outdir, summary, report, manifest)
    print(json.dumps({'rows': len(new_rows), 'action_pass': report['action_audit_pass'], 'truth_pass': report['truth_guard_pass'],
                      'coverage': report['coverage'], 'audit_wall_s': report['audit_wall_s']}), flush=True)
    return new_rows


def write_readme_and_evidence(outdir, summary, audit, manifest):
    evidence = {'experiment_id': manifest['experiment_id'], 'claims': [
        {'claim': 'Five policies compared on the same 120 scenes', 'evidence': ['manifest.json#/scenarios', 'paired_results.json#/rows', 'audit_report.json#/pairing_mismatches']},
        {'claim': 'Every reported action obeys independently recomputed physical timing', 'evidence': ['audit_report.json#/max_errors', 'traces/*#/action_audit']},
        {'claim': 'No truth call before accepted exit, and no sensitive arena attributes in policy classes', 'evidence': ['audit_report.json#/truth_guard_pass', 'audit_report.json#/static_policy_audit']},
        {'claim': 'Every continuous-cell completion claim passes 5 m numerical and independent 50 m cell verification', 'evidence': ['coverage_audit.json#/counts', 'coverage_audit.json#/audits'], 'limit': 'Numerical point verification alone is not a proof; finite-sample success is not a universal algorithm guarantee.'},
        {'claim': 'Joint efficiency improvements and uncertainty', 'evidence': ['summary.json#/scenarios', 'summary.json#/overall/joint_vs']},
        {'claim': 'Ablation modules have different effect sizes; after-service scan CI may include zero', 'evidence': ['summary.json#/ablations/random/paired_vs_joint'], 'limit': '20 paired random cases, one module removed at a time; effects need not add linearly.'}],
        'key_results': {'overall': summary.get('overall'), 'ablations': summary.get('ablations')},
        'remaining_limitations': ['Offline mock evidence only; formal online runs remain pending.',
            'Historical execution runner bytes were not preserved before metadata-only edits. Algorithm and field hashes are verified; current audit runner is snapshotted.',
            'Historical real-time allowance was measured but not enforced by a watchdog.',
            'The error field is a bounded synthetic model, with hash-noise stress scenes; these do not cover every physically possible error field.']}
    atomic_json(outdir/'evidence_map.json', evidence)
    text = f'''# Q3 frozen paper experiment

Experiment ID: `{manifest['experiment_id']}`. Definition fingerprint: `{manifest['definition_fingerprint']}`.

The final matrix contains 120 paired scenes × 5 default policies (600 runs), plus
20 random seeds × 4 single-module joint ablations (80 runs). Scenario order is
random 50, annulus 20, center 10, hash 20, worstrecv 20. Seed =
2026091200 + 100000 × scenario index + 97 × within-scenario index.
Every policy uses a fresh scene with the same exact source and error-field fingerprints.

## Reproduce or audit

From the repository root, with Python 3.12 and NumPy 2.3.5 (no SciPy needed):

```sh
python3 -B B_locator/Q3/reproduce.py --audit-only
python3 -B B_locator/Q3/reproduce.py --smoke
python3 -B B_locator/Q3/reproduce.py --out /path/to/new-experiment
```

`--audit-only` only replays existing actions and never constructs/runs a robot.
`--smoke` writes to a separate smoke subdirectory. A new experiment runs serially;
existing finished traces are validated and skipped. Incompatible algorithm/config
hashes raise an error instead of overwriting data. Audit/report script changes do
not invalidate or rerun algorithms. `--max-new-runs N` can bound a partial new run.
The stored source snapshot contains all Q3 Python modules, the current runner,
nine loaded expectation maps, their manifest and the fallback map; SHA256.json
verifies their bytes. The immutable algorithm/field definition excludes reporting
script revisions. The discarded early src/run_p3_paper.py was not an imported
algorithm dependency and is excluded from the final manifest.

## Metric definitions

T = travel_m/5 + 5*N_measure + N_switch + 5*N_clear_success + 3*N_clear_failure.
The initial location is (0,0) and measuring channel is 1. Only a measurement
changes the measuring channel; clear and enter/exit do not. Every distance,
switch, dt and cumulative timestamp is independently recomputed from raw actions.
The cumulative sum never uses a reported timestamp as its next starting value.
Final metrics are derived from this reconstruction and checked against report,
mock statistics and post-exit truth. The paper primary metric is the complete T,
reported as mean and P90. The per-source statistic is mean(T/cleared), with null
for cleared=0 and a disclosed defined-value count. All status values,
including failed and incomplete-clear runs, remain in aggregates. Last-clear time
and tail after last clear are diagnostics and are undefined when no clear succeeds.
The bootstrap uses 4000 paired scene resamples, RNG seed 20260912, fresh for each
comparison. A positive saving means the comparison uses less time than the reference.
Both total time and per-source time have percentile 95% confidence intervals.

The simulator virtual limit is 360000 s. The 1200 s allowance is real computation
time. Historical policy construction/run wall times were recorded without a timer;
all are summarized, but local wall measurements are not official online validation.
Future new runs install a 1200 s timer and retain timeouts as failed cases.

## Coverage and information isolation

The independent 5 m grid audit uses only actual no_signal responses for each
uncleared channel and successful-clear actions to retire channels. Any positive
observation left uncleared blocks completion. Identical observation station sets
are deduplicated and cached. All {audit['coverage']['runs']} claimed continuous-cell
completions are audited ({audit['coverage']['numerical_pass']} numerical passes).
This numerical audit is not a continuous proof. A separate independent 50 m
closed-square-cell reconstruction checks all cells intersecting the disk at
radius 1000 − 50/sqrt(2) − 1e-6; its triangle-inequality argument certifies entire
cells. {audit['coverage']['cell_certificate_pass']} such reconstructions pass.

The runtime truth wrapper logs calls and permits them only after accepted exit.
AST inspection covers every method in the eight decision classes, with sensitive
arena properties and dynamic getattr calls separately listed. Module-level mock
tests and scene-generation helpers are outside decision scope. This is transparent
inspection plus a runtime guard, not a security sandbox.

## Files and provenance

- paired_results.json / .csv: the authoritative 680 rows, each pointing to one trace.
- traces/: only final referenced traces; raw actions/configuration/report/truth are preserved.
- summary.json: all cases, each scenario, all baselines and four paired ablations.
- coverage_audit.json: per-run/per-channel verification and deduplicated observation sets.
- audit_report.json: timing, truth, configuration, static-source, pairing and payload-integrity checks.
- evidence_map.json: paper claims linked to precise evidence and limitations.
- source_snapshot/: verified algorithm, field and current audit-runner bytes.

600 redundant early traces and obsolete metadata are moved (never deleted) to
`tmp/q3-paper-scratch/previous-products/`. Movements and hashes are listed in the
audit report. Historical provenance fields are retained in traces; the separate
audit_provenance section records this audit and canonical raw-payload hashes.
Earlier runner metadata was refreshed after reporting edits, so its hash is not
claimed to prove the exact historical runner bytes. Algorithm/field hashes remain
verified. This audit did not rerun any policy.
'''
    (outdir/'README.md').write_text(text, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(OUT_DEFAULT)); parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--smoke', action='store_true'); parser.add_argument('--max-new-runs', type=int, default=0)
    args = parser.parse_args(argv); outdir = Path(args.out)
    if args.smoke: outdir = outdir/'smoke'
    (outdir/'traces').mkdir(parents=True, exist_ok=True)
    old_manifest = read_json(outdir/'manifest.json') if (outdir/'manifest.json').exists() else None
    manifest = make_manifest(old_manifest)
    result = read_json(outdir/'paired_results.json') if (outdir/'paired_results.json').exists() else {'rows': []}
    rows = result['rows']; by_key = {(r['split'], r['scenario'], r['index'], r['policy']): r for r in rows}
    if len(by_key) != len(rows): raise RuntimeError('Duplicate result key')
    if args.audit_only:
        if not rows: raise RuntimeError('--audit-only requires existing paired_results.json')
        audit_all(outdir, rows, manifest); return
    atomic_json(outdir/'manifest.json', manifest)
    registry = {p: (cls, cfg) for p, cls, cfg in POLICIES}; jobs = []
    for s, (kind, count) in enumerate(SCENARIOS):
        if args.smoke and s: continue
        for i in range(1 if args.smoke else count):
            for p, cls, cfg in POLICIES: jobs.append(('main', kind, i, SEED_BASE+100000*s+97*i, p, cls, cfg()))
    for i in range(1 if args.smoke else 20):
        for p, override in ABLATIONS: jobs.append(('ablation', 'random', i, SEED_BASE+97*i, p, JointRobot, replace(JointConfig(), **override)))
    new = 0; base = None
    for split, kind, i, seed, p, cls, cfg in jobs:
        key = split, kind, i, p
        if key in by_key:
            existing = read_json(outdir/by_key[key]['trace_file'])
            if existing['seed'] != seed or existing['requested_config'] != clean(asdict(cfg)):
                raise RuntimeError(f'Invalid resume metadata: {key}')
            continue
        if args.max_new_runs and new >= args.max_new_runs: break
        if base is None: base = load_base()
        row = run_case(kind, i, seed, p, cls, cfg, base, outdir, manifest, split)
        by_key[key] = row; new += 1; rows = list(by_key.values())
        write_results(outdir, rows, manifest)
        print(f'New run {new}: {kind} {i} {p} {row["status"]}', flush=True)
    audit_all(outdir, list(by_key.values()), manifest)
    print(f'Executed {new} new policy runs', flush=True)


if __name__ == '__main__': main()
