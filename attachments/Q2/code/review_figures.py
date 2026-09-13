"""从两套保存网格重绘问题二正文结果图和四页补充图。"""
from pathlib import Path
import shutil,tempfile
ROOT=Path(__file__).resolve().parents[1]

def main(out,font=None):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.backends.backend_pdf import PdfPages
    out=Path(out);(out/'figures').mkdir(parents=True,exist_ok=True)
    font=Path(font) if font else ROOT.parent/'fonts/simsun.ttc'
    if not font.is_file():
        raise SystemExit('缺少中文字体；请保留同级 fonts/ 或用 --font 指定中文字体。')
    font_manager.fontManager.addfont(str(font));family=font_manager.FontProperties(fname=font).get_name()
    import make_q2_paper_figures as draw
    draw.DEFAULT_MMA=str(ROOT/'data/Q2_expected_diameter_data.csv');draw.DEFAULT_PY=str(ROOT/'data/p2_grid_map.csv')
    def setup():
        plt.rcParams.update({'font.family':[family],'mathtext.fontset':'custom','mathtext.rm':'STIXGeneral','mathtext.it':'STIXGeneral:italic','mathtext.bf':'STIXGeneral:bold','axes.unicode_minus':False,'font.size':11,'pdf.fonttype':42})
        return plt
    draw._setup=setup
    with tempfile.TemporaryDirectory(prefix='q2-figures-') as folder:
        draw.LOCAL_FIG=folder;draw.PAPER_FIG=str(out/'figures');draw.main()
        import illustration_plot_Q2 as geometry
        setup();geometry.get_output_dir=lambda:folder
        geometry.draw_q2_wedge_diagram(save_fig=True,show_fig=False)
        shutil.copy2(Path(folder)/'wedge_diagram.png',out/'figures/p2-wedge-geometry.png')
    mma=np.genfromtxt(ROOT/'data/Q2_expected_diameter_data.csv',delimiter=',',names=True,encoding='utf-8-sig')
    sim=np.genfromtxt(ROOT/'data/p2_grid_map.csv',delimiter=',',names=True,encoding='utf-8-sig')
    jobs=[('理论网格：期望定位区域直径',mma['a'],mma['b'],mma['d_m'],'直径 / m',1000),
          ('数值网格：条件期望定位区域直径',sim['x_m'],sim['y_m'],sim['E_diam_given_detectable_m'],'直径 / m',1000),
          ('数值网格：候选源的可检测比例',sim['x_m'],sim['y_m'],sim['p_detectable'],'比例',1),
          ('数值网格：对测向误差平均后的条件期望',sim['x_m'],sim['y_m'],sim['E_diam_err_given_detectable_m'],'直径 / m',1000)]
    setup()
    plt.rcParams.update({'font.family':['DejaVu Serif',family],'mathtext.fontset':'cm'})
    with PdfPages(out/'supplement.pdf') as pdf:
        for page,(title,x,y,z,label,vmax) in enumerate(jobs,1):
            fig,ax=plt.subplots(figsize=(8.27,11.69));fig.subplots_adjust(left=.13,right=.87,bottom=.21,top=.86)
            ux,uy=np.unique(x),np.unique(y)
            dx,dy=np.diff(ux).min(),np.diff(uy).min()
            xs=np.arange(ux[0],ux[-1]+dx/2,dx);ys=np.arange(uy[0],uy[-1]+dy/2,dy)
            values=np.full((len(ys),len(xs)),np.nan)
            values[np.searchsorted(ys,y),np.searchsorted(xs,x)]=np.minimum(z,vmax)
            im=ax.pcolormesh(xs,ys,np.ma.masked_invalid(values),shading='nearest',cmap='viridis',vmin=0,vmax=vmax,rasterized=True)
            ax.set(xlim=(-1800,1800),ylim=(-1800,1800),aspect='equal',xlabel='$a$ / m',ylabel='$b$ / m');ax.set_title(title,pad=18)
            fig.suptitle('问题二补充图册',fontsize=16,y=.95)
            cb=fig.colorbar(im,ax=ax,shrink=.75);cb.set_label(label)
            note='色阶上限1000 m；超限值保留并使用最高颜色，完整数值见原始CSV。' if vmax==1000 else '比例按论文所用候选源位置与接收约束计算，取值在0到1之间。'
            fig.text(.5,.16,note,ha='center',fontsize=10)
            missing='白色表示原始网格未包含的位置；可检测比例为 0 的格点保留。' if vmax==1 else '白色表示原始网格未包含的位置，或没有有限条件期望的格点。'
            fig.text(.5,.125,missing,ha='center',fontsize=10)
            fig.text(.5,.06,f'数据来源见 DATA_SOURCES.md；未新增随机试验。 {page} / 4',ha='center',fontsize=10)
            pdf.savefig(fig);plt.close(fig)
    print('问题二补充图册：4页，独立热力图、可检测比例与误差平均结果。')
