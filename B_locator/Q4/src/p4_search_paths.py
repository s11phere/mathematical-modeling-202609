"""Export a reproducible representative trajectory from the held-out set."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from p4_search_bench import run_one

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out/p4_search_validation'

if __name__=='__main__':
    rows=[json.loads(s) for s in (OUT/'new_main.jsonl').read_text().splitlines()]
    choices=[r for r in rows if r['policy']=='strict' and r['scenario']=='uniform']
    median=np.median([r['exit_s'] for r in choices])
    chosen=min(choices,key=lambda r:abs(r['exit_s']-median));seed=chosen['seed']
    traces=[run_one(p,'uniform',seed,trace=True) for p in ['legacy','strict','fast95']]
    assert abs(traces[1]['exit_s']-chosen['exit_s'])<1e-7
    (OUT/'representative_traces.json').write_text(json.dumps(traces,indent=2),encoding='utf8')
    fig,axs=plt.subplots(1,3,figsize=(15,5.4),sharex=True,sharey=True)
    for ax,r in zip(axs,traces):
        ax.add_patch(plt.Circle((0,0),1800,fill=False,color='#777',linestyle='--',lw=1))
        commands=[a for a in r['actions'] if a['kind'] in ('measure','clear')]
        xy=np.array([[0,0]]+[[a['x'],a['y']] for a in commands])
        ax.plot(xy[:,0],xy[:,1],color='#337eaf',lw=.8,alpha=.7)
        ax.scatter(xy[:,0],xy[:,1],color='#337eaf',s=4,alpha=.4)
        for s in r['truth']['sources']:
            ax.scatter(s['x_m'],s['y_m'],color='#279966' if s['cleared'] else '#d84b3f',s=40,zorder=5)
            ax.annotate(str(s['channel']),(s['x_m'],s['y_m']),xytext=(4,4),textcoords='offset points',fontsize=7)
        ax.plot(0,0,'k*',markersize=11);ax.set_aspect('equal');ax.grid(alpha=.15)
        ax.set_xlim(-2100,2100);ax.set_ylim(-2100,2100);ax.set_xlabel('x (m)')
        ax.set_title(f"{r['policy']} | {r['cleared']}/{r['total']} cleared\nexit {r['exit_s']:.0f} s; travel {r['travel_m']/1000:.1f} km",fontsize=11)
    axs[0].set_ylabel('y (m)')
    fig.suptitle(f'Q4 held-out scene {seed}, all directional | green: cleared, red: missed',fontsize=12)
    fig.tight_layout();fig.savefig(OUT/'representative_paths.png',dpi=170);plt.close(fig)
    print(seed)
