#!/usr/bin/env python3
"""Compare v31.6 host/guest CSV logs by verified/history state frame."""
from __future__ import annotations
import csv, sys
from pathlib import Path

def load(path: Path):
    rows=[]
    with path.open(newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try: frame=int(r.get('state_frame','-1'))
            except ValueError: continue
            if frame >= 0: rows.append((frame,r))
    return rows

def nearest(rows, frame, tolerance=70):
    best=None; dist=tolerance+1
    for f,r in rows:
        d=abs(f-frame)
        if d<dist: best=(f,r); dist=d
    return best if dist<=tolerance else None

def main():
    if len(sys.argv)!=3:
        print('Usage: python compare_sync_logs.py HOST.csv GUEST.csv'); return 2
    a=load(Path(sys.argv[1])); b=load(Path(sys.argv[2]))
    if not a or not b:
        print('No v31.6 state-trace rows found.'); return 1
    print(f'host rows={len(a)} guest rows={len(b)}')
    # Exact hashes at common sampled state frames, when timestamps happen to align.
    amap={f:r for f,r in a}; bmap={f:r for f,r in b}; common=sorted(set(amap)&set(bmap))
    mismatch=[]
    for f in common:
        if amap[f]['state_hash'] != bmap[f]['state_hash']: mismatch.append(f)
    print(f'exact common sampled frames={len(common)} hash mismatches={len(mismatch)}')
    if mismatch:
        f=mismatch[0]; print(f'FIRST EXACT SAMPLE MISMATCH frame={f}')
        for label,r in [('HOST',amap[f]),('GUEST',bmap[f])]:
            print(label, 'hash='+r['state_hash'], 'score='+r['score1']+'-'+r['score2'],
                  'p1x='+r['p1_x'], 'p2x='+r['p2_x'],
                  'ball=('+r['ball_x']+','+r['ball_y']+')',
                  'v=('+r['ball_vx']+','+r['ball_vy']+')')
    # The built-in two-way verification counters are more exact than 1Hz sampling.
    for label, rows in [('HOST',a),('GUEST',b)]:
        r=rows[-1][1]
        print(label, 'checks='+r.get('hash_checks','?'),
              'mismatches='+r.get('hash_mismatches','?'),
              'first_mismatch='+r.get('first_mismatch_frame','?'),
              'last_verified='+r.get('last_verified_frame','?'),
              'local='+r.get('last_local_verify_hash',''),
              'remote='+r.get('last_remote_verify_hash',''))
    return 0
if __name__=='__main__': raise SystemExit(main())
