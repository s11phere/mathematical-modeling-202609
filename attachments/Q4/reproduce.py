#!/usr/bin/env python3
"""问题四独立复现：核验230份动作、试运行、重跑实验、生成图表。"""
from pathlib import Path
import argparse,json,os,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'));sys.dont_write_bytecode=True
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'b-review-mpl'))

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--check','--audit-only',action='store_true');g.add_argument('--smoke',action='store_true');g.add_argument('--full',action='store_true');g.add_argument('--figures',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=2);p.add_argument('--resume',action='store_true',help='在相同输出目录续跑完整实验')
    p.add_argument('--dev',action='store_true',help='仅用于 smoke/full 开发实验；允许已有 Python 源码修改，仍严格核验数据和结果')
    a=p.parse_args()
    if a.dev and not (a.smoke or a.full):p.error('--dev 只能搭配 --smoke 或 --full，不能用于审计或制图。')
    from review_tools import verify_package
    verification=verify_package(dev=a.dev)
    print(json.dumps(verification,ensure_ascii=False),flush=True)
    if a.check:
        if a.out is not None:
            audit_out=a.out.expanduser().resolve()
            if audit_out==ROOT or audit_out.is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
        else:audit_out=None
        from review_tools import check
        check(audit_out);return
    if a.out is None:p.error('请用 --out 指定附件之外的新输出目录。')
    out=a.out.expanduser().resolve()
    if out==ROOT or out.is_relative_to(ROOT):p.error('输出目录须在本题附件之外。')
    out.mkdir(parents=True,exist_ok=True)
    if a.dev:
        (out/'development_source_changes.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if a.figures:
        import make_paper_figures as figures
        figures.OUT=out/'figures';figures.setup_style();figures.fig_geometry();figures.fig_homing()
        figures.fig_routes(ROOT/'results');summary=figures.load_summary(ROOT/'results')
        figures.fig_results(summary);figures.fig_ablation(summary)
        from review_tools import supplement
        supplement(out/'supplement.pdf')
        subprocess.run([sys.executable,'-B',str(ROOT/'code/make_paper_tables.py')],env={**os.environ,'Q4_REVIEW_OUT':str(out)},check=True)
    else:
        import run_paper_q4 as runner
        runner.ROOT=ROOT;runner.SRC=ROOT/'code'
        sys.argv=[str(ROOT/'code/run_paper_q4.py'),'--out',str(out),'--workers',str(a.workers)]
        if a.smoke:sys.argv+=['--main-cases','1','--stress-cases','1','--extra-cases','1']
        if a.resume:sys.argv+=['--resume']
        runner.main()
    print(f'复现输出：{out}')
if __name__=='__main__':main()
