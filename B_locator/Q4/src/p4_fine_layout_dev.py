"""Development search of sparse ring layouts with a continuous certificate."""
import json
from pathlib import Path
from p4_certificate import DirectionalCertificate,ring_layout
from p4_grid import tour_len

if __name__=='__main__':
    cert=DirectionalCertificate(20,48)
    rows=[]
    for ri in [925,950,970]:
        for ro in [1840,1860,1880,1900]:
            for ni in [7,8,9,10]:
                for no in [12,14,16]:
                    if ni+no>26:continue
                    for phase in [0,90/no,180/no]:
                        rings=((ri,ni,0),(ro,no,phase));points=ring_layout(rings)
                        if cert.continuous_complete(points):
                            length,_=tour_len(points)
                            row={'rings':rings,'stations':len(points),'length_m':length}
                            rows.append(row);print(json.dumps(row),flush=True)
    rows.sort(key=lambda r:r['length_m'])
    Path('B_locator/Q4/out/p4_search_dev/fine_layouts.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
