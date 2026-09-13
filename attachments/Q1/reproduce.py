#!/usr/bin/env python3
"""问题一：核验已保存结果、重跑实验或生成图表。"""
from pathlib import Path
import argparse, csv, hashlib, json, math, os, sys, tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
sys.dont_write_bytecode=True
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'b-review-mpl'))

def verify_package(dev=False):
    """严格核验清单；开发模式仅容许已列出的 Python 代码内容变化。"""
    try:
        manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        files=manifest['files']
        font_hash=manifest['shared_plotting_font']['sha256']
        if not isinstance(files,dict) or not files:
            raise ValueError('文件清单为空或格式错误')
        for name,entry in files.items():
            path=Path(name)
            if path.is_absolute() or '..' in path.parts or path.as_posix()!=name:
                raise ValueError(f'非法清单路径：{name}')
            if not isinstance(entry['sha256'],str) or len(entry['sha256'])!=64:
                raise ValueError(f'非法 SHA256：{name}')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise SystemExit(f'附件清单无法核验：{exc}') from exc
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
            if (p.is_file() or p.is_symlink()) and p.name!='.DS_Store'
            and '__pycache__' not in p.relative_to(ROOT).parts
            and p.relative_to(ROOT).as_posix()!='SOURCE_MANIFEST.json'}
    missing=sorted(set(files)-actual)
    extra=sorted(actual-set(files))
    if missing or extra:
        details=[]
        if missing:details.append('缺失：'+', '.join(missing))
        if extra:details.append('额外文件：'+', '.join(extra))
        raise SystemExit('附件文件清单不符；'+'；'.join(details))
    modified=[]
    for name,entry in files.items():
        path=ROOT/name
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f'附件须为普通文件：{name}')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        historical=entry.get('source_sha256') if entry.get('adaptation')=='none; byte-for-byte copy' else None
        if digest!=entry['sha256'] or (historical is not None and digest!=historical):
            parts=Path(name).parts
            is_code=name=='reproduce.py' or (len(parts)==2 and parts[0]=='code' and Path(name).suffix=='.py')
            if not (dev and is_code):
                raise SystemExit(f'附件文件 SHA256 不符：{name}；--dev 仅可用于已列出的 Python 代码修改。')
            modified.append(name)
    font=ROOT.parent/'fonts/simsun.ttc'
    if font.exists() and (not font.is_file() or hashlib.sha256(font.read_bytes()).hexdigest()!=font_hash):
        raise SystemExit('共享字体 SHA256 不符：../fonts/simsun.ttc。')
    report={'file_count':len(files),'modified_code':sorted(modified)}
    print(f'附件文件核验通过：{len(files)} 个文件。')
    if dev:
        print('修改代码列表：'+(', '.join(report['modified_code']) or '无'))
        print('开发运行不代表论文冻结结果。')
    return report

def check():
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
    p.add_argument('--dev',action='store_true',help='仅限 --smoke/--full：允许清单中 Python 代码内容变化，其他文件仍须一致')
    p.add_argument('--font',type=Path,help='制图使用的中文字体；默认使用附件同级 fonts/simsun.ttc')
    p.add_argument('--out',type=Path,default=ROOT.parent/'reproduction-q1')
    a=p.parse_args()
    if a.dev and not (a.smoke or a.full):p.error('--dev 只能与 --smoke 或 --full 一起使用。')
    if a.out.resolve()==ROOT or a.out.resolve().is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
    verify_package(dev=a.dev)
    if a.figures:
        import review_figures
        review_figures.main(a.out,a.font)
    elif a.full or a.smoke:
        if a.out.resolve()==(ROOT/'results').resolve():raise SystemExit('请将重跑结果写入新的目录。')
        import p1_experiments as exp
        exp.main(['--out',str(a.out)]+(['--skip-sweep'] if a.smoke else []))
    else:check()
if __name__=='__main__':main()
