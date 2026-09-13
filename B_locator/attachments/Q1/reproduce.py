#!/usr/bin/env python3
"""问题一：核验已保存结果、重跑实验或生成图表。"""
from pathlib import Path
import argparse, csv, hashlib, json, math, os, sys, tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
sys.dont_write_bytecode=True
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'b-review-mpl'))

def check():
    manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for name,entry in manifest['files'].items():
        path=ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise SystemExit(f'附件文件缺失或 SHA256 不符：{name}')
    import p1_experiments as exp
    paths=[(str(p),str(p.with_suffix('.truth.json'))) for p in sorted((ROOT/'data').glob('p1_case*.csv'))]
    actual=exp.run_cases(paths)
    saved=[json.loads(line) for line in (ROOT/'results/p1_results.jsonl').read_text().splitlines()]
    assert len(actual)==len(saved)==5
    for a,b in zip(actual,saved):
        for key in ['status','diameter_m','ratio','excess_m','excess_pct','diameter_circle_covers','truth_inside_region']:
            if isinstance(a.get(key),float):assert math.isclose(a[key],b[key],rel_tol=1e-8,abs_tol=1e-5),(key,a[key],b[key])
            else:assert a.get(key)==b.get(key),(key,a.get(key),b.get(key))
    print('问题一：附件 SHA256 核验通过；5组输入重新求解与保存结果一致；区域、直径圆覆盖及真源包含性核验通过。')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group()
    g.add_argument('--check','--audit-only',action='store_true');g.add_argument('--smoke',action='store_true');g.add_argument('--full',action='store_true');g.add_argument('--figures',action='store_true')
    p.add_argument('--font',type=Path,help='制图使用的中文字体；默认使用附件同级 fonts/simsun.ttc')
    p.add_argument('--out',type=Path,default=ROOT.parent/'reproduction-q1')
    a=p.parse_args()
    if a.out.resolve()==ROOT or a.out.resolve().is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
    if a.figures:
        import review_figures
        review_figures.main(a.out,a.font)
    elif a.full or a.smoke:
        if a.out.resolve()==(ROOT/'results').resolve():raise SystemExit('请将重跑结果写入新的目录。')
        import p1_experiments as exp
        exp.main(['--out',str(a.out)]+(['--skip-sweep'] if a.smoke else []))
    else:check()
if __name__=='__main__':main()
