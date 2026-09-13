#!/usr/bin/env python3
"""问题二：核验理论和数值网格，重跑数值实验并生成补充图。"""
from pathlib import Path
import argparse,csv,hashlib,json,os,sys,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
sys.dont_write_bytecode=True
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'b-review-mpl'))

def verify_package(dev=False):
    """严格核验清单；开发模式仅容许已列出的 Python 代码内容变化。"""
    try:
        manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        files=manifest['files']
        font_hash=manifest['font_dependency']['sha256']
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
    import numpy as np
    import p2_grid_expectation as model
    mma=np.genfromtxt(ROOT/'data/Q2_expected_diameter_data.csv',delimiter=',',names=True,encoding='utf-8-sig')
    x=1500*(np.arange(200)+.5)/200;w=x/x.sum()
    max_error=0.
    for i in np.linspace(0,len(mma)-1,41,dtype=int):
        row=mma[i];a,b=float(row['a']),float(row['b'])
        d=np.pi/90/abs(b)*np.sqrt((x-a)**2+b*b)*np.sqrt((x+abs(x-a))**2+b*b)
        error=abs(float(w@d)-float(row['d_m']));max_error=max(max_error,error)
        assert np.isclose(w@d,row['d_m'],rtol=1e-10,atol=1e-7)
    rows=list(csv.DictReader((ROOT/'data/p2_grid_map.csv').open(encoding='utf-8-sig')))
    ids=np.linspace(0,len(rows)-1,41,dtype=int)
    X=np.array([float(rows[i]['x_m']) for i in ids]);Y=np.array([float(rows[i]['y_m']) for i in ids])
    ts,weights,_=model.source_samples((0.,0.),0.,n_t=300)
    computed=model.expected_diameter_measured(X,Y,ts,weights)['E_det']
    saved=np.array([float(rows[i]['E_diam_given_detectable_m']) for i in ids])
    assert np.allclose(computed,saved,rtol=1e-8,atol=1e-6,equal_nan=True)
    print(f'问题二：理论网格{len(mma)}点、数值网格{len(rows)}点；各41点独立重算通过，理论最大误差{max_error:.2g} m。')

def theory(out):
    import numpy as np
    out.mkdir(parents=True,exist_ok=True)
    xs=1500*(np.arange(200)+.5)/200;w=xs/xs.sum()
    with (out/'Q2_expected_diameter_data.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['a','b','d_m'])
        for b in range(-1800,1801,15):
            if b==0:continue
            for a in range(-500,1796,15):
                d=np.pi/90/abs(b)*np.sqrt((xs-a)**2+b*b)*np.sqrt((xs+abs(xs-a))**2+b*b)
                writer.writerow([a,b,float(w@d)])

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--check','--audit-only',action='store_true');g.add_argument('--smoke',action='store_true');g.add_argument('--full',action='store_true');g.add_argument('--figures',action='store_true')
    p.add_argument('--dev',action='store_true',help='仅限 --smoke/--full：允许清单中 Python 代码内容变化，其他文件仍须一致')
    p.add_argument('--font',type=Path,help='制图使用的中文字体；默认使用附件同级 fonts/simsun.ttc')
    p.add_argument('--out',type=Path,default=ROOT.parent/'reproduction-q2')
    a=p.parse_args()
    if a.dev and not (a.smoke or a.full):p.error('--dev 只能与 --smoke 或 --full 一起使用。')
    if a.out.resolve()==ROOT or a.out.resolve().is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
    verify_package(dev=a.dev)
    if a.figures:
        import review_figures
        review_figures.main(a.out,a.font)
    elif a.full or a.smoke:
        if a.out.resolve() in [(ROOT/'data').resolve(),(ROOT/'results').resolve()]:raise SystemExit('请将重跑结果写入新的目录。')
        import p2_grid_expectation as model
        a.out.mkdir(parents=True,exist_ok=True)
        if a.full:theory(a.out)
        model.main(['--step','30' if a.full else '300','--n-t','300' if a.full else '30','--n-e','200' if a.full else '10','--no-figures','--out',str(a.out)])
    else:check()
if __name__=='__main__':main()
