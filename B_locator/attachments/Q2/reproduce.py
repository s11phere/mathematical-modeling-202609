#!/usr/bin/env python3
"""问题二：核验理论和数值网格，重跑数值实验并生成补充图。"""
from pathlib import Path
import argparse,csv,json,os,sys,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
sys.dont_write_bytecode=True
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'b-review-mpl'))

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
    p.add_argument('--font',type=Path,help='制图使用的中文字体；默认使用附件同级 fonts/simsun.ttc')
    p.add_argument('--out',type=Path,default=ROOT.parent/'reproduction-q2')
    a=p.parse_args()
    if a.out.resolve()==ROOT or a.out.resolve().is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
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
