#!/usr/bin/env python3
"""OKI MSM5205 4-bit ADPCM decoder for PC Engine CD ADPCM clips (pure Python).
  okidec.py ISO LBA NSECT out.wav [rate_code=14] [--low-first]
  okidec.py ISO --table TS IDX out.wav        (TS = table sector 86/90/../106, IDX = 1-based entry)
Sample rate = 32000/(16-rate_code) Hz. 12-bit output scaled to 16 bit. High nibble is played first."""
import sys, wave, struct
STEPS=[16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,
       253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552]
IDX=[-1,-1,-1,-1,2,4,6,8]
def decode(data, high_first=True):
    val, si, out = 0x800, 0, []
    for b in data:
        for nib in ((b>>4, b&15) if high_first else (b&15, b>>4)):
            step=STEPS[si]
            delta=(step*(((nib&7)<<1)|1))>>3
            val = val-delta if nib&8 else val+delta
            val = 0 if val<0 else 0xFFF if val>0xFFF else val
            si += IDX[nib&7]; si = 0 if si<0 else 48 if si>48 else si
            out.append((val-0x800)<<4)
    return out
def write_wav(path, samples, rate):
    w=wave.open(path,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(struct.pack('<%dh'%len(samples), *[max(-32768,min(32767,s)) for s in samples])); w.close()
if __name__=='__main__':
    a=sys.argv[1:]; hf='--low-first' not in a; a=[x for x in a if x!='--low-first']
    iso=open(a[0],'rb')
    if a[1]=='--table':
        sys.path.insert(0,__file__.rsplit('/',1)[0]); from cliptable import tables
        T={ts:A for ts,A,B in tables(open(a[0],'rb').read())}
        e=T[int(a[2])][int(a[3])-1]; lba,n,rc,out=e['lba'],e['n'],e['rate'] or 14,a[4]
    else:
        lba,n,out=int(a[1],0),int(a[2],0),a[3]; rc=int(a[4],0) if len(a)>4 else 14
    iso.seek(lba*2048); data=iso.read(n*2048)
    s=decode(data,hf); rate=32000//(16-rc)
    write_wav(out,s,rate)
    print(f"LBA {lba} n={n} rate_code={rc} -> {rate} Hz, {len(s)} samples = {len(s)/rate:.2f} s, peak {max(map(abs,s))}, clipped {sum(1 for x in s if abs(x)>=32752)} -> {out}")
