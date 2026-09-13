"""Make the compact Q3 paper figures from frozen experiment records.

The script is intentionally a renderer only: it never runs a policy and never
rewrites the frozen JSON.  The runner writes ``out/paper_q3`` using the schema
documented in the module docstring of the evidence runner; this script reads
that directory and writes ``paper/figures/q3-*.pdf`` and ``.png``.

Usage (from the repository root)::

    python B_locator/Q3/research_archive/scripts/make_paper_figures.py

The five figures are sized for the 160 mm text width of the paper.  Full trajectories remain in the frozen evidence directory.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea
from matplotlib.patches import Circle, Rectangle


MM = 1.0 / 25.4
FIG_W = 160 * MM
DPI = 330
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "Q3" / "research_archive" / "out" / "paper_q3"
OUT = ROOT / "paper" / "figures"

POLICIES = ["field", "sweep", "tour", "adaptive", "joint"]
POLICY_LABEL = {
    "field": "field",
    "sweep": "sweep",
    "tour": "tour",
    "adaptive": "adaptive",
    "joint": "joint",
}
POLICY_COLOR = {
    "field": "#667085", "sweep": "#b7791f", "tour": "#3b82a0",
    "adaptive": "#7656a6", "joint": "#118a8c",
}
SCENE_LABEL = {
    "random": "随机", "annulus": "外圈", "center": "中心",
    "hash": "非平滑误差", "worstrecv": "最小接收半径",
    "live1": "重建布局1", "live2": "重建布局2",
}


def setup_style() -> None:
    """Use paper-safe sizes; all visible text stays >= 8.5 pt."""
    from matplotlib import font_manager
    font = ROOT / "paper" / "fonts" / "simsun.ttc"
    font_manager.fontManager.addfont(str(font))
    # Resolve Latin glyphs before the CJK fallback: SimSun also contains Latin
    # glyphs, so listing it first silently gives letters and digits its face.
    latin = Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf")
    if latin.exists():
        font_manager.fontManager.addfont(str(latin))
    matplotlib.rcParams["font.family"] = ["Times New Roman", font_manager.FontProperties(fname=font).get_name()]
    matplotlib.rcParams["mathtext.fontset"] = "cm"
    matplotlib.rcParams.update({
        "font.size": 9.0,
        "axes.titlesize": 9.2,
        "axes.labelsize": 9.0,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "font.style": "normal",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def load_data(data_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = data_dir / "paired_results.json"
    if not path.exists():
        raise FileNotFoundError(f"冻结数据不存在：{path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = obj.get("rows")
    if rows is None:
        # Backward-compatible reader for the older nested benchmark files.
        rows = []
        for scenario, group in obj.get("scenarios", {}).items():
            for old in group.get("rows", []):
                seed = old.get("seed")
                for policy in POLICIES:
                    if policy in old:
                        r = dict(old[policy])
                        r.update({"scenario": scenario, "seed": seed,
                                  "policy": policy, "split": "main"})
                        rows.append(r)
    if not isinstance(rows, list) or not rows:
        raise ValueError("paired_results.json 中没有可绘图的 rows")
    return obj, rows


def val(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    """Look up a scalar in metrics/report/audit and then at row level."""
    buckets: list[Any] = [row.get("metrics"), row.get("report"),
                          row.get("audit"), row]
    for name in names:
        for bucket in buckets:
            if isinstance(bucket, dict) and name in bucket:
                return bucket[name]
    return default


def num(row: dict[str, Any], *names: str, default: float = float("nan")) -> float:
    x = val(row, *names, default=default)
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def policy_of(row: dict[str, Any]) -> str:
    return str(row.get("policy", row.get("strategy", ""))).lower()


def scene_of(row: dict[str, Any]) -> str:
    return str(row.get("scenario", row.get("scene", "random"))).lower()


def is_ok(row: dict[str, Any]) -> bool:
    return str(row.get("status", "ok")).lower() in {"ok", "complete", "success", ""} and not row.get("error")


def time_value(row: dict[str, Any]) -> float:
    return num(row, "virtual_time_s", "exit_s", "total_time_s", "exit_time_s", "T_s")


def trace_path(row: dict[str, Any], data_dir: Path) -> Path | None:
    p = row.get("trace_file")
    if not p:
        return None
    q = Path(str(p).replace("\\", "/"))
    return q if q.is_absolute() else data_dir / q


def first_trace(rows: list[dict[str, Any]], policies: Iterable[str], data_dir: Path,
                scenario: str = "random") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    policies = list(policies)
    candidates = [r for r in rows if is_ok(r) and scene_of(r) == scenario and
                  str(r.get("split", "main")) == "main" and int(r.get("index", -1)) == 0]
    # Select one key for which every requested policy has a saved trace.  This
    # prevents silently comparing different seeds when one policy failed.
    groups: dict[tuple[Any, Any], dict[str, dict[str, Any]]] = {}
    for row in candidates:
        p = trace_path(row, data_dir)
        if not p or not p.exists():
            continue
        key = (row.get("index", 0), row.get("seed", 0))
        groups.setdefault(key, {})[policy_of(row)] = row
    for key in sorted(groups, key=lambda z: (int(z[0]), int(z[1]))):
        if all(pol in groups[key] for pol in policies):
            for pol in policies:
                row = groups[key][pol]; p = trace_path(row, data_dir)
                out[pol] = json.loads(p.read_text(encoding="utf-8"))
            break
    return out


def actions(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in trace.get("actions", [])
            if isinstance(a, dict) and "x" in a and "y" in a]


def action_points(trace: dict[str, Any]) -> np.ndarray:
    aa = actions(trace)
    return np.asarray([[0.0, 0.0]] + [[float(a["x"]), float(a["y"])] for a in aa], float)


def source_points(trace: dict[str, Any]) -> np.ndarray:
    truth = trace.get("post_exit_truth", trace.get("truth", {})) or {}
    src = truth.get("sources", []) if isinstance(truth, dict) else []
    return np.asarray([[float(s["x_m"]), float(s["y_m"])] for s in src
                      if "x_m" in s and "y_m" in s], float)


def route_legend():
    return [Line2D([], [], color="#d7a06b", marker="o", ls="", ms=3, label="检测点"),
            Line2D([], [], color="#b33e36", marker="x", ls="", ms=4.5, label="成功清除"),
            Line2D([], [], color="#b7791f", marker="^", mfc="none", ls="", ms=4, label="清除失败"),
            Line2D([], [], color="#424b54", marker="o", mfc="none", ls="", ms=4.2, label="源位（事后）"),
            Line2D([], [], color="#252a35", marker="s", ls="", ms=3.5, label="起点")]


def draw_route(ax, trace: dict[str, Any], color: str, title: str,
               annotate_sources: bool = True, show_ylabel=True,
               compact: bool = False) -> None:
    p = action_points(trace)
    if len(p) > 1:
        ax.plot(p[:, 0], p[:, 1], color=color, lw=.95, zorder=3)
    aa = actions(trace)
    m = np.asarray([[a['x'], a['y']] for a in aa if a.get('kind') == 'measure'])
    if len(m):
        m = np.unique(np.round(m, 2), axis=0)
        ax.scatter(m[:, 0], m[:, 1], s=5, color='#d7a06b', alpha=.65, zorder=4)
    src = source_points(trace)
    if annotate_sources and len(src):
        ax.scatter(src[:, 0], src[:, 1], marker='o', s=20,
                   facecolors='none', edgecolors='#424b54', linewidth=.65, zorder=6)
    for success, marker, size in ((True, 'x', 13), (False, '^', 15)):
        q = np.asarray([[a['x'], a['y']] for a in aa if a.get('kind') == 'clear' and
                       (a.get('clear_result') == 'success') == success])
        if len(q):
            if success:
                ax.scatter(q[:, 0], q[:, 1], marker=marker, s=size,
                           color='#b33e36', linewidth=.8, zorder=7)
            else:
                ax.scatter(q[:, 0], q[:, 1], marker=marker, s=size,
                           facecolors='none', edgecolors='#b7791f', linewidth=.8, zorder=8)
    th = np.linspace(0, 2 * math.pi, 400)
    ax.plot(1800*np.cos(th), 1800*np.sin(th), '--', color='#aeb5bd', lw=.65)
    ax.scatter([0], [0], marker='s', s=13, color='#252a35', zorder=9)
    met = trace.get('metrics', {})
    t = met.get('exit_s', trace.get('report', {}).get('virtual_time_s', 0))
    length = met.get('travel_m', trace.get('report', {}).get('travel_m', 0))
    n = met.get('cleared', 0); total = met.get('n_sources', 0)
    metric = f'$T={t:.0f}$ s; $L={length/1000:.2f}$ km'
    ax.set_title(title, fontsize=9.2, pad=16 if compact else 26)
    ax.text(.5, 1.025, metric if compact else f'{metric}\n清除 {n}/{total}',
            transform=ax.transAxes, ha='center', va='bottom', fontsize=8.5,
            linespacing=1.2)
    ax.set(xlim=(-1950, 1950), ylim=(-1950, 1950), xlabel='$x$ / m')
    if show_ylabel: ax.set_ylabel('$y$ / m')
    else: ax.tick_params(labelleft=False)
    ax.set_xticks([-1000, 0, 1000]); ax.set_yticks([-1000, 0, 1000])
    ax.set_aspect('equal'); ax.grid(alpha=.17, lw=.4)


def save_figure(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Exact print canvas; individual builders reserve their own text margins.
    fig.savefig(OUT / f'{stem}.pdf')
    fig.savefig(OUT / f'{stem}.png', dpi=DPI)
    plt.close(fig)


def mixed_label(ax, xy, *parts: str) -> None:
    """Place adjacent CJK and math runs without routing CJK through mathtext."""
    runs=[TextArea(part,textprops={'fontsize':9}) for part in parts]
    box=HPacker(children=runs,align='center',pad=0,sep=3)
    ax.add_artist(AnnotationBbox(box,xy,frameon=False,box_alignment=(0,.5)))


def fig1_geometry(rows, data_dir) -> None:
    """Two deterministic geometric diagrams, explicitly independent of data."""
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(FIG_W, 57*MM))
    fig.subplots_adjust(left=.02, right=.98, bottom=.04, top=.84, wspace=.16)
    ax.set_title('(a) 单元整体排除：三角不等式', fontsize=9.5)
    ax.set_xlim(-3.9, 1.7); ax.set_ylim(-1.4, 2.05); ax.set_aspect('equal'); ax.axis('off')
    s = np.array([-3., 0.]); q = np.array([0., 0.]); x = np.array([.65, .65])
    ax.add_patch(Circle(s, 3.98, fill=False, lw=1.2, ec='#3b82a0'))
    ax.add_patch(Rectangle((-.65, -.65), 1.3, 1.3, fc='#e3f0f1', ec='#118a8c'))
    ax.plot([s[0], q[0], x[0]], [s[1], q[1], x[1]], color='#118a8c', lw=1.2)
    ax.plot([s[0], x[0]], [s[1], x[1]], ls='--', color='#b7791f', lw=1)
    ax.plot(s[0], s[1], 's', color='#252a35', ms=4)
    ax.plot(q[0], q[1], 'o', color='#118a8c', ms=3)
    ax.plot(x[0], x[1], 'o', color='#b7791f', ms=3)
    mixed_label(ax,(-3.45,-.55),'$s$','无信号测点')
    ax.text(.03, -.34, '$q$', ha='center'); ax.text(.75, .74, '$x$')
    ax.text(-1.55, -.22, r'$\|q-s\|\leq r_{\rm cert}$', ha='center')
    ax.text(.20, 1.13, r'$\|x-q\|\leq h/\sqrt{2}$', ha='center')
    ax.text(-2.95, 1.5, r'$R_{\min}=1000$ m', color='#3b82a0')
    ax.text(-.95, -1.13, r'$r_{\rm cert}=1000-h/\sqrt{2}-\delta_r$', ha='center')
    bx.set_title('(b) 测站滑移：保留独占覆盖职责', fontsize=9.5)
    bx.set_xlim(-.4, 5.2); bx.set_ylim(-.95, 3.8); bx.set_aspect('equal'); bx.axis('off')
    a=np.array([0., 0.]); b=np.array([4.8, 0.]); old=np.array([2.2, 2.0])
    centers=[np.array([1.4,2.4]),np.array([2.95,2.0])]; radius=1.7
    v=np.array([0.,-2.]); delta=np.array(centers)-old
    bb=-2*delta@v; cc=np.sum(delta**2,axis=1)-radius**2
    tt=min(1., float(np.min((-bb+np.sqrt(bb**2-4*(v@v)*cc))/(2*(v@v)))))
    new=old+tt*v
    for c in centers:
        bx.add_patch(Circle(c,radius,fill=False,ec='#cbd6dc',lw=.7,ls=':'))
        bx.add_patch(Rectangle(c-.12,.24,.24,fc='#bededb',ec='#118a8c',lw=.7))
    bx.plot([a[0], b[0]],[0,0],color='#aeb5bd',lw=.8)
    bx.plot([a[0],old[0],b[0]],[0,old[1],0],'--',color='#b7791f',lw=1)
    bx.plot([a[0],new[0],b[0]],[0,new[1],0],color='#118a8c',lw=1.6)
    bx.annotate('',xy=new,xytext=old,arrowprops=dict(arrowstyle='->',color='#252a35',lw=1))
    bx.plot(old[0],old[1],'o',mfc='white',mec='#b7791f',ms=5)
    bx.plot(new[0],new[1],'o',color='#118a8c',ms=4)
    mixed_label(bx,(old[0]+.50,old[1]+.60),'原站','$p_0$')
    mixed_label(bx,(new[0]+.18,new[1]+.23),'新站','$p(t)$')
    mixed_label(bx,(.25,3.20),'方格：必须保留的单元中心','$Q$')
    bx.text(2.4,-.6,r'$\forall q\in Q:\ \|p(t)-q\|\leq r_{\rm cert}$',ha='center')
    bx.text(0,-.30,'$a$'); bx.text(4.8,-.30,'$b$')
    save_figure(fig,'q3-geometry-certificate')


def route_comparison(rows, data_dir, selected, stem):
    trs=first_trace(rows,POLICIES,data_dir)
    if len(trs)!=5: raise ValueError('固定首局的五策略轨迹必须齐全')
    fig,axes=plt.subplots(1,3,figsize=(FIG_W,65*MM))
    fig.subplots_adjust(left=.075,right=.99,bottom=.235,top=.82,wspace=.10)
    for i,pol in enumerate(selected):
        ax=axes[i]
        draw_route(ax,trs[pol],POLICY_COLOR[pol],f'({chr(97+i)}) {pol}',
                   show_ylabel=i==0, compact=True)
        # Emphasize the trajectory portion discussed in the text directly;
        # labels and leader lines are deliberately kept out of the panels.
        if pol=='sweep':
            radius,count=trs[pol]['effective_config']['sweep_rings'][0]
            ang=np.linspace(0,2*math.pi,int(count)+1)
            ring=np.column_stack([radius*np.cos(ang),radius*np.sin(ang)])
            measured=np.asarray([[a['x'],a['y']] for a in actions(trs[pol])
                                 if a.get('kind')=='measure'])
            if not all(np.min(np.linalg.norm(measured-q,axis=1))<.01 for q in ring[:-1]):
                raise ValueError('The annotated ring must consist of observed measuring stations')
            ax.plot(ring[:,0],ring[:,1],ls=':',lw=1.15,color=POLICY_COLOR[pol],alpha=.65,zorder=2)
            ax.text(-1540,-1690,'八站覆盖骨架',fontsize=8.2,color='#596773',alpha=.88)
        else:
            pts=action_points(trs[pol])
            if len(pts)>3:
                # The terminal quarter is where the text discusses tail
                # search, fold-back, or final exclusion.  A translucent
                # overlay keeps the original route legible.
                if pol=='adaptive':
                    seg=pts[1:min(len(pts),8)]
                else:
                    seg=pts[max(1,int(.72*len(pts))):]
                ax.plot(seg[:,0],seg[:,1],color=POLICY_COLOR[pol],lw=2.6,
                        alpha=.30,zorder=2.5,solid_capstyle='round')
                label_pos={'field':(-1730,1710),'tour':(300,-1740),
                           'adaptive':(-1710,-1710),'joint':(-1710,-1710)}[pol]
                label={'field':'收尾搜索','tour':'局部折返',
                       'adaptive':'共享横向基线','joint':'收尾排除'}[pol]
                ax.text(*label_pos,label,fontsize=8.2,color='#596773',alpha=.88)
    fig.legend(handles=route_legend(),loc='lower center',ncol=5,frameon=False,
               bbox_to_anchor=(.52,.001),columnspacing=.8,handletextpad=.4,handlelength=1.0)
    save_figure(fig,stem)


def fig2_field_sweep_tour(rows,data_dir):
    route_comparison(rows,data_dir,['field','sweep','tour'],'q3-route-field-sweep-tour')


def fig3_tour_adaptive_joint(rows,data_dir):
    route_comparison(rows,data_dir,['tour','adaptive','joint'],'q3-route-tour-adaptive-joint')


def audit_from_actions(trace: dict[str, Any]) -> dict[str, float]:
    aa = actions(trace)
    if not aa:
        return {"travel": 0., "measure": 0., "switch": 0., "clear": 0., "time": 0., "cleared": 0.}
    prev = np.array([0., 0.]); channel = 1; parts = {"travel": 0., "measure": 0., "switch": 0., "clear": 0.}
    cleared = 0
    for a in aa:
        q = np.array([float(a["x"]), float(a["y"])])
        d = float(np.linalg.norm(q - prev)); parts["travel"] += d / 5.; prev = q
        if a.get("kind") == "measure":
            parts["measure"] += 5.; parts["switch"] += float(int(a.get("channel", channel)) != channel)
            channel = int(a.get("channel", channel))
        elif a.get("kind") == "clear":
            ok = a.get("clear_result") == "success"; parts["clear"] += 5. if ok else 3.; cleared += int(ok)
    parts["time"] = sum(parts[k] for k in ("travel", "measure", "switch", "clear"))
    parts["cleared"] = float(cleared)
    return parts


def fig4_cost_and_clear(rows: list[dict[str, Any]], data_dir: Path) -> None:
    main=[r for r in rows if str(r.get('split','main'))=='main' and scene_of(r)=='random' and policy_of(r) in POLICIES]
    fig,(ax,bx)=plt.subplots(1,2,figsize=(FIG_W,70*MM))
    fig.subplots_adjust(left=.105,right=.985,bottom=.30,top=.87,wspace=.39)
    parts=['t_travel_s','t_measure_s','t_switch_s','t_clear_s']
    cols=['#3b82a0','#d97736','#7656a6','#55a868']; labels=['移动','检测','切频','清除']
    means=np.array([[np.mean([num(r,key) for r in main if policy_of(r)==pol]) for key in parts] for pol in POLICIES])
    y=np.arange(5); left=np.zeros(5)
    for k in range(4):
        ax.barh(y,means[:,k],left=left,color=cols[k],label=labels[k],height=.60); left+=means[:,k]
    for i,t in enumerate(left):ax.text(t+60,i,f'{t:.0f}',va='center',fontsize=8.5)
    ax.set_yticks(y,POLICIES);ax.invert_yaxis();ax.set_xlim(0,left.max()*1.18)
    ax.set_xlabel('平均完整时间 / s');ax.set_title('(a) 随机50局：动作时间分解',fontsize=9.5)
    ax.grid(axis='x',alpha=.16,lw=.4)
    ax.legend(frameon=False,ncol=2,loc='upper center',
              bbox_to_anchor=(.46,-.26),columnspacing=1.0,handlelength=.9,handletextpad=.4)
    trs=first_trace(rows,POLICIES,data_dir)
    for i,pol in enumerate(POLICIES):
        tr=trs[pol];aa=actions(tr)
        ts=[float(a['virtual_time_s']) for a in aa if a.get('kind')=='clear' and a.get('clear_result')=='success']
        tend=float(tr.get('metrics',{}).get('exit_s',aa[-1]['virtual_time_s']))
        bx.step([0.]+ts+[tend],[0]+list(range(1,len(ts)+1))+[len(ts)],where='post',
                color=POLICY_COLOR[pol],lw=1.2,ls=['-','--','-.',':','-'][i],label=pol)
        bx.plot(tend,len(ts),'s',ms=3.5,color=POLICY_COLOR[pol],zorder=6)
    bx.set(xlabel='虚拟时间 / s',ylabel='累计清除数',ylim=(-.3,14.0))
    bx.set_title('(b) 固定首局：清除进度',fontsize=9.5)
    last=float(trs['field']['metrics']['last_clear_s'])
    exit_=float(trs['field']['metrics']['exit_s'])
    bx.annotate('',xy=(last,13.1),xytext=(exit_,13.1),
                arrowprops=dict(arrowstyle='|-|',lw=.7,color=POLICY_COLOR['field']))
    bx.text((last+exit_)/2,13.35,f'收尾 {exit_-last:.0f} s',
            fontsize=8.5,ha='center',va='bottom',color=POLICY_COLOR['field'])
    bx.set_xticks([0,2000,4000]);bx.set_yticks([0,4,8,12]);bx.grid(alpha=.16,lw=.4)
    handles,labels=bx.get_legend_handles_labels()
    handles.append(Line2D([],[],marker='s',color='#333333',ls='',ms=3.5))
    labels.append('退出时刻')
    # Matplotlib fills legend columns vertically; this order reads naturally
    # by row as field / sweep / tour, then adaptive / joint / exit marker.
    order=[0,3,1,4,2,5]
    bx.legend([handles[i] for i in order],[labels[i] for i in order],frameon=False,
              ncol=3,loc='upper center',bbox_to_anchor=(.5,-.26),
              handlelength=1.2,columnspacing=.75,handletextpad=.35)
    save_figure(fig,'q3-time-cost-clearance')


def fig5_scenarios_ablation(rows: list[dict[str,Any]]) -> None:
    main=[r for r in rows if str(r.get('split','main'))=='main' and policy_of(r) in POLICIES]
    scenes=['random','annulus','center','hash','worstrecv']
    mat=np.array([[np.mean([time_value(r) for r in main if scene_of(r)==sc and policy_of(r)==p]) for p in POLICIES] for sc in scenes])
    bad=np.array([[any(not val(r,'full_clear',default=False) for r in main if scene_of(r)==sc and policy_of(r)==p) for p in POLICIES] for sc in scenes])
    ratio=mat/mat[:,2,None]
    fig,(ax,bx)=plt.subplots(2,1,figsize=(FIG_W,92*MM),gridspec_kw={'height_ratios':[1.1,1]})
    fig.subplots_adjust(left=.19,right=.89,bottom=.14,top=.92,hspace=.85)
    from matplotlib.colors import TwoSlopeNorm
    norm=TwoSlopeNorm(vmin=min(.7,float(ratio.min())),vcenter=1.,vmax=max(1.5,float(ratio.max())))
    cmap=plt.get_cmap('RdYlBu_r');im=ax.imshow(ratio,cmap=cmap,norm=norm,aspect='auto')
    ax.set_xticks(range(5),POLICIES);ax.set_yticks(range(5),[SCENE_LABEL[s] for s in scenes])
    ax.set_title('(a) 五类场景：平均完整时间（s）',fontsize=9.5,pad=6)
    for i in range(5):
        for j in range(5):
            rgba=cmap(norm(ratio[i,j]));lum=.299*rgba[0]+.587*rgba[1]+.114*rgba[2]
            ax.text(j,i,f'{mat[i,j]:.0f}'+('*' if bad[i,j] else ''),ha='center',va='center',fontsize=9,color='white' if lum<.48 else '#1f2933')
    cax=fig.add_axes([.91,.632,.015,.28]); cb=fig.colorbar(im,cax=cax,ticks=[.75,1,1.5]);cb.ax.tick_params(labelsize=8.5)
    ax.text(0,-.39,'颜色：相对 tour 耗时；*：该组存在未全清局',transform=ax.transAxes,fontsize=8.5)
    base={(scene_of(r),r['seed']):r for r in main if policy_of(r)=='joint'}
    variants=['joint_no_after_service','joint_single_plan','joint_no_cover_polish','joint_no_probability_gate']
    labels=['取消先清后测','单一规划权重','取消测站精修','取消概率筛选']
    values=[];ci=[]
    for p in variants:
        ab=[r for r in rows if r.get('split')=='ablation' and policy_of(r)==p and scene_of(r)=='random']
        pair=np.array([[time_value(base[(scene_of(r),r['seed'])]),time_value(r)] for r in ab])
        if len(pair)!=20:raise ValueError(f'{p}: requires 20 paired ablations, got {len(pair)}')
        values.append(100*(pair[:,1].mean()/pair[:,0].mean()-1))
        rng=np.random.default_rng(918120);idx=rng.integers(0,len(pair),(4000,len(pair)))
        means=pair[idx].mean(axis=1);ci.append(np.percentile(100*(means[:,1]/means[:,0]-1),[2.5,97.5]))
    values=np.asarray(values);ci=np.asarray(ci)
    bx.bar(range(4),values,color='#5b7f99',width=.50)
    bx.errorbar(range(4),values,yerr=[values-ci[:,0],ci[:,1]-values],fmt='none',ecolor='#263846',capsize=3,lw=1)
    bx.axhline(0,color='#767e87',lw=.65)
    for i,v in enumerate(values):bx.annotate(f'{v:+.2f}%',(i,ci[i,1]),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8.5)
    bx.set_xticks(range(4),labels);bx.set_ylabel('耗时增加 / %')
    bx.set_title('(b) 配对20局消融：均值及95%区间',fontsize=9.5,pad=6)
    bx.set_ylim(min(-.8,float(ci.min())-.6),float(ci.max())+1.0)
    bx.grid(axis='y',alpha=.16,lw=.4)
    save_figure(fig,'q3-scenarios-ablation')


def main() -> None:
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    OUT = args.out
    setup_style()
    obj, rows = load_data(args.data)
    fig1_geometry(rows, args.data)
    fig2_field_sweep_tour(rows, args.data)
    fig3_tour_adaptive_joint(rows, args.data)
    fig4_cost_and_clear(rows, args.data)
    fig5_scenarios_ablation(rows)
    # Full raw trajectories remain available in the frozen evidence directory.
    print(f"wrote five Q3 paper figures to {OUT} (width={160} mm, dpi={DPI})")


if __name__ == "__main__":
    main()
