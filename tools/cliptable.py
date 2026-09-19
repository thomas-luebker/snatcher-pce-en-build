#!/usr/bin/env python3
"""Parse the Snatcher PCE ADPCM clip tables (6 banks at ISO sectors 86,90,..,106; 8-byte entries).
A entry: [prio, cmd(1=load,2=load+play,3=AD_CPLAY stream), lbaH, lbaL, lbaM, secL, secH, rate]
B entry: [prio, 0?, addrL?, ...] -> see AUDIO.md"""
import sys, hashlib, collections
SECT=2048
TABLE_SECTORS=[86,90,94,98,102,106]
def tables(iso):
    out=[]
    for ts in TABLE_SECTORS:
        b=iso[ts*SECT:ts*SECT+0x2000]
        A=[];B=[]
        for i in range(0,0x800,8):
            e=b[i:i+8]
            if e==b'\xff'*8: break
            A.append(dict(idx=i//8+1,prio=e[0],cmd=e[1],lba=(e[2]<<16)|(e[4]<<8)|e[3],n=e[5]|(e[6]<<8),rate=e[7]))
        for i in range(0x800,0x1000,8):
            e=b[i:i+8]
            if e==b'\xff'*8: break
            B.append(dict(idx=(i-0x800)//8+1,prio=e[0],addr=e[1]|(e[2]<<8),len=e[3]|(e[4]<<8),rate=e[5],mode=e[6]))
        out.append((ts,A,B))
    return out
if __name__=='__main__':
    iso=open(sys.argv[1],'rb').read()
    other=open(sys.argv[2],'rb').read() if len(sys.argv)>2 else None
    seen={}
    tot=collections.Counter(); uniq=collections.Counter(); cnt=collections.Counter(); ucnt=collections.Counter()
    for ts,A,B in tables(iso):
        c=collections.Counter(e['cmd'] for e in A)
        rates=collections.Counter(e['rate'] for e in A)
        lo=min(e['lba'] for e in A); hi=max(e['lba']+e['n'] for e in A)
        gaps=0; pos=A[0]['lba']
        contiguous=all(A[i]['lba']+A[i]['n']==A[i+1]['lba'] for i in range(len(A)-1))
        same = other is not None and iso[lo*SECT:hi*SECT]==other[lo*SECT:hi*SECT]
        print(f"table@{ts}: A={len(A)} B={len(B)} cmds={dict(c)} rates={dict(rates)} LBA {lo}-{hi} ({hi-lo} sect) contiguous={contiguous} max_n={max(e['n'] for e in A)} same_in_other_track={same}")
        for e in A:
            d=iso[e['lba']*SECT:(e['lba']+e['n'])*SECT]
            h=hashlib.md5(d).hexdigest()
            tot[e['cmd']]+=e['n']; cnt[e['cmd']]+=1
            if h not in seen:
                seen[h]=(ts,e['idx']); uniq[e['cmd']]+=e['n']; ucnt[e['cmd']]+=1
    print('entries by cmd',dict(cnt),'sectors',dict(tot))
    print('unique-content entries by cmd',dict(ucnt),'sectors',dict(uniq))
    for k in uniq: print(f" cmd{k}: unique {uniq[k]} sectors = {uniq[k]*SECT/1e6:.1f} MB = {uniq[k]*SECT*2/16000/60:.1f} min @16kHz")
