"""问题一正文图重绘与全部五组算例的补充说明。"""
from pathlib import Path
import csv,json,shutil,tempfile
ROOT=Path(__file__).resolve().parents[1]

def main(out,font=None):
    import make_figures as figs
    from matplotlib import font_manager
    import matplotlib.pyplot as plt
    font=Path(font) if font else ROOT.parent/'fonts/simsun.ttc'
    if not font.is_file():
        raise SystemExit('缺少中文字体；请保留同级 fonts/ 或用 --font 指定中文字体。')
    font_manager.fontManager.addfont(str(font))
    family=font_manager.FontProperties(fname=font).get_name()
    def setup():
        plt.rcParams.update({'font.family':[family],
            'mathtext.fontset':'custom','mathtext.rm':'STIXGeneral','mathtext.it':'STIXGeneral:italic','mathtext.bf':'STIXGeneral:bold','font.size':11,'axes.unicode_minus':False,
            'savefig.dpi':300,'pdf.fonttype':42})
        figs.OUT.mkdir(parents=True,exist_ok=True)
    figs.setup=setup
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='q1-figures-') as folder:
        temp=Path(folder);shutil.copytree(ROOT/'data',temp/'cases')
        figs.HERE=temp;figs.PAPER=ROOT.parent;figs.OUT=out/'figures';figs.main()
    plt.rcParams.update({'font.family':['DejaVu Serif',family],'mathtext.fontset':'cm'})
    import numpy as np
    from matplotlib.backends.backend_pdf import PdfPages
    import p1_intersection as model
    paths=sorted((ROOT/'data').glob('p1_case*.csv'))
    summary=json.loads((ROOT/'results/p1_summary.json').read_text())
    with PdfPages(out/'supplement.pdf') as pdf:
        for start in range(0,5,2):
            fig,axes=plt.subplots(2,1,figsize=(8.27,11.69));fig.subplots_adjust(left=.17,right=.87,bottom=.08,top=.90,hspace=.42)
            fig.suptitle('问题一补充算例：定位区域与直径圆',fontsize=15,y=.96)
            for ax,idx in zip(axes,range(start,min(start+2,5))):
                rows=list(csv.DictReader(paths[idx].open()))
                points=[(float(r['x_m']),float(r['y_m'])) for r in rows];bearings=[float(r['svd_deg']) for r in rows]
                vertices,_=model.region_from_bearings(points,bearings)
                figs.draw_region(ax,vertices);r=summary['per_case'][idx]
                ax.set_title(f"算例 {r['label']}：直径 {r['diameter_m']:.4f} m；直径圆"+('覆盖' if r['coverage'] else '未覆盖')+'定位区域',fontsize=11)
                ax.set_xlabel('$x$ / m');ax.set_ylabel('$y$ / m');ax.grid(alpha=.15)
            if start==4:
                ax=axes[-1];ax.axis('off')
                rows=[[r['label'],f"{r['diameter_m']:.4f}",f"{r['ratio']:.6f}",
                       '是' if r['coverage'] else '否'] for r in summary['per_case']]
                table=ax.table(cellText=rows,colLabels=['算例','直径 / m','最大圆心距 / 半径','直径圆覆盖'],
                    cellLoc='center',colWidths=[.14,.24,.36,.23],bbox=[0,.30,1,.57])
                table.auto_set_font_size(False);table.set_fontsize(10)
                for (r,c),cell in table.get_celld().items():
                    cell.set_linewidth(.5);cell.set_edgecolor('#b6c5cf')
                    if r==0:cell.set_facecolor('#eaf1f6')
                ax.text(.5,.98,'五组算例的统一判定',ha='center',va='top',fontsize=12,transform=ax.transAxes)
                ax.text(.5,.17,'比值大于 1 时，至少一个顶点落在直径圆外。\n五组真源均位于角楔交集内，失败指圆未覆盖区域。',
                    ha='center',va='center',fontsize=10,linespacing=1.8,transform=ax.transAxes)
            fig.text(.5,.032,f'红色多边形：角楔交集；蓝色圆：以区域直径为直径的圆。第 {start//2+1} 页',ha='center',fontsize=10)
            pdf.savefig(fig);plt.close(fig)
        fig,ax=plt.subplots(figsize=(8.27,11.69));fig.subplots_adjust(left=.14,right=.94,bottom=.45,top=.88)
        names=['双测点\n理想示向度','双测点\n含测向误差','多测点\n理想示向度','多测点\n含测向误差']
        scans=[summary['sweeps'][k] for k in ['two_point','two_point_err','well_conditioned','well_conditioned_err']]
        vals=[x['fail_pct'] for x in scans];bars=ax.bar(range(4),vals,color='#3b82a0')
        ax.bar_label(bars,labels=[f'{v:.2f}%' for v in vals],padding=4)
        ax.set_xticks(range(4),names);ax.set_ylabel('直径圆未覆盖比例 / %');ax.set_ylim(0,max(vals)*1.2)
        ax.set_title('直径圆未覆盖比例',pad=18)
        tab_ax=fig.add_axes([.11,.15,.83,.21]);tab_ax.axis('off')
        rows=[[name.replace('\n',''),r['n_trials'],r['n_bounded'],r['n_fail'],f"{r['worst_ratio']:.6f}"]
              for name,r in zip(names,scans)]
        table=tab_ax.table(cellText=rows,colLabels=['构型','抽样数','有界有效数','未覆盖数','最坏比值'],
            cellLoc='center',colWidths=[.35,.15,.17,.15,.18],bbox=[0,0,1,1])
        table.auto_set_font_size(False);table.set_fontsize(9)
        for (r,c),cell in table.get_celld().items():
            cell.set_linewidth(.5);cell.set_edgecolor('#b6c5cf')
            if r==0:cell.set_facecolor('#eaf1f6')
        fig.text(.5,.085,'分母为非空有界算例；多测点两组各有 528 个构型不满足筛选条件。\n比值为最大顶点圆心距除以半直径；最坏比值刻画覆盖偏离程度。',ha='center',fontsize=9,linespacing=1.8)
        fig.text(.5,.032,'来源：results/p1_summary.json；固定种子与字段说明见 DATA_SOURCES.md。 4 / 4',ha='center',fontsize=9)
        pdf.savefig(fig);plt.close(fig)
    print('问题一补充图册：4页，全部五组算例及四组几何扫描。')
