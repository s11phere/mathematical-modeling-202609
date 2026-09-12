"""Embed complete, unchanged Python sources with TeX escapes for Unicode glyphs.

Only the display copy gains listing escape markers; original files remain the
reproducible executable source.  Source text and SHA256 are retained alongside.
"""
from pathlib import Path
import hashlib

Q3 = Path(__file__).resolve().parents[1]
FILES = ['src/p1_intersection.py','src/p2_grid_expectation.py','src/p3_arena.py',
         'src/p3_expect_field.py','src/p3_robot.py','src/p3_sweep.py','src/p3_tour.py',
         'src/p3_homing.py','src/p3_frontier.py','src/p3_coverage.py',
         'src/p3_adaptive.py','src/p3_joint.py','src/p3_bench.py','src/p3_adaptive_bench.py',
         'scripts/run_p3_paper.py','scripts/make_paper_tables.py','scripts/make_paper_figures.py',
         'scripts/make_paper_trajectory_atlas.py']
GLYPHS = dict(zip('εθλπρφ', [r'\epsilon',r'\theta',r'\lambda',r'\pi',r'\rho',r'\phi']))
GLYPHS.update({'⁺':r'{}^{+}','⁻':r'{}^{-}','↷':r'\curvearrowright','⇒':r'\Rightarrow',
 '∈':r'\in','∓':r'\mp','∝':r'\propto','∠':r'\angle','∩':r'\cap','≈':r'\approx',
 '≠':r'\ne','≡':r'\equiv','≤':r'\le','≥':r'\ge','⏹':r'\blacksquare',
 '■':r'\blacksquare','▲':r'\blacktriangle','★':r'\star','⟨':r'\langle',
 '⟩':r'\rangle','⟺':r'\Longleftrightarrow'})

def main():
    # Escape markers are deliberately absent from all source modules.
    start, end = '(*@', '@*)'
    parts=['% Generated display of complete source files; originals remain unchanged.\n',
           '\\begingroup\n',
           r'\lstset{commentstyle=\color[rgb]{0.12,0.34,0.24},stringstyle=\color[rgb]{0.15,0.30,0.35},keywordstyle=\color[rgb]{0.13,0.23,0.43}}'+'\n']
    for name in FILES:
        raw=(Q3/name).read_text()
        assert start not in raw and end not in raw
        text=''.join(start+r'\ensuremath{'+GLYPHS[c]+'}'+end if c in GLYPHS
             else start+r'\textcircled{'+str('①②③'.index(c)+1)+'}'+end if c in '①②③'
             else c for c in raw)
        label=name.replace('_',r'\_')
        parts += [r'\subsection{\texttt{'+label+'}}\n',
                  '% SHA256 '+hashlib.sha256((Q3/name).read_bytes()).hexdigest()+'\n',
                  r'\begin{lstlisting}[language=python,escapeinside={(*@}{@*)}]'+'\n',text,
                  '\n'+r'\end{lstlisting}'+'\n']
    parts.append('\\endgroup\n')
    (Q3.parent/'paper/sections/q3-source-listings.tex').write_text(''.join(parts))

if __name__=='__main__':main()
