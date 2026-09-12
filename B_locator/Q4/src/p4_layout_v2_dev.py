"""Independent static layout search; certificates use replies only at runtime."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
from p4_certificate import DirectionalCertificate, ring_layout
from p4_grid import tour_len
from p4_layout_v2 import adaptive_complete


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',default='outer');args=ap.parse_args()
    cert=DirectionalCertificate(50,48)
    # A deterministic subset is used to screen candidates; finalists receive
    # the complete continuous certificate below.
    full=cert.centers.copy()
    cert.centers=cert.centers[::2]
    best=[];seen=0
    if args.mode=='outer':
        candidates=(((a,6,0),(b,6,30),(ro,no,phase))
                    for a in [900,940,970,990]
                    for b in [1450,1550,1650,1750]
                    for ro in [1930,1970,2010,2050]
                    for no in [9,10,11,12]
                    for phase in [0,90/no,180/no])
    elif args.mode=='two':
        candidates=(((ri,ni,0),(ro,no,phase))
                    for ni in range(7,13)
                    for no in range(9,17)
                    if ni+no<=24
                    for ri in [900,970,1030,1100]
                    for ro in [1880,1930,1980,2030]
                    for phase in [0,90/no,180/no])
    elif args.mode=='adaptive':
        candidates=(((ri,ni,0),(1800/math.cos(math.pi/no)+dr,no,phase))
                    for ni in range(6,11)
                    for no in range(10,15)
                    if ni+no<=22
                    for ri in [975,985,995,999]
                    for dr in [2,5,10,20]
                    for phase in [0,90/no,180/no])
    else: raise ValueError(args.mode)
    for rings in candidates:
        points=ring_layout(rings)
        if args.mode=='adaptive':
            good,details=adaptive_complete(points,30,1.875,detail=True)
            unproved=0 if good else details[-1][2]
        else:
            unproved=int(np.sum(~cert.all_orientation_cells(points)))
        seen+=1
        row={'rings':rings,'n':len(points),'unproved':unproved}
        if args.mode=='adaptive' and unproved==0:row['length_m']=tour_len(points)[0]
        best.append(row);best.sort(key=lambda r:(r['unproved'],r['n'],r.get('length_m',0)));best=best[:40]
        if unproved==0 or seen%300==0:print(json.dumps({'seen':seen,'best':best[:3]}),flush=True)
    final=[]
    for row in best:
        pts=ring_layout(row['rings']);fine=DirectionalCertificate(20,48)
        row['fine_unproved']=int(np.sum(~fine.all_orientation_cells(pts)))
        row['adaptive_complete'],row['refinement']=adaptive_complete(pts,detail=True)
        row['length_m']=tour_len(pts)[0]
        final.append(row)
    out=Path('B_locator/Q4/out/p4_layout_v2');out.mkdir(exist_ok=True,parents=True)
    (out/(args.mode+'.json')).write_text(json.dumps(final,indent=2),encoding='utf8')
    print(json.dumps(final[:10],indent=2),flush=True)

if __name__=='__main__':main()
