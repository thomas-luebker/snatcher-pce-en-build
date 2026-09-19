#!/usr/bin/env python3
"""OKI MSM5205 ADPCM encoder (matching okidec.py) + round-trip SNR test on a clean speech sample.
  okienc.py test   -> takes 12 s of Track 01 (CD-DA 'this is a CD-ROM' warning voice), resamples to 16 kHz,
                      simulates the Sega CD source (8-bit sign-magnitude ~ 8-bit linear), encodes to PCE ADPCM,
                      decodes, reports SNR; writes work/audio/roundtrip_*.wav"""
import sys, struct, math, os
sys.path.insert(0, os.path.dirname(__file__))
from okidec import STEPS, IDX, decode, write_wav
def encode(samples16):
    """samples16: signed 16-bit ints at the target rate. Returns bytes (high nibble first), padded with 0x88 to 2048."""
    val, si, nibs = 0x800, 0, []
    for s in samples16:
        tgt=(s>>4)+0x800; step=STEPS[si]; d=tgt-val; sign=8 if d<0 else 0; d=abs(d)
        code=min(7,(d*4)//step)
        # a +/-1 code search keeps the reconstruction closest (cheap improvement over plain quantising)
        best=None
        for c in {max(0,code-1),code,min(7,code+1)}:
            delta=(step*((c<<1)|1))>>3; v=val-delta if sign else val+delta; v=max(0,min(0xFFF,v))
            e=abs(v-tgt)
            if best is None or e<best[0]: best=(e,c,v)
        _,code,val=best; nibs.append(sign|code); si=max(0,min(48,si+IDX[code]))
    if len(nibs)&1: nibs.append(8)
    out=bytearray((nibs[i]<<4)|nibs[i+1] for i in range(0,len(nibs),2))
    out+=b'\x88'*((-len(out))%2048)
    return bytes(out)
def snr(ref,test):
    n=min(len(ref),len(test)); sig=sum(r*r for r in ref[:n]); err=sum((r-t)**2 for r,t in zip(ref[:n],test[:n]))
    return 10*math.log10(sig/err) if err else 99
if __name__=='__main__' and sys.argv[1:]==['test']:
    root=os.path.join(os.path.dirname(__file__),'..','..')
    f=open(os.path.join(root,'disc','Snatcher CD-ROMantic (Japan) (Track 01).bin'),'rb'); f.seek(int(2.0*44100)*4); raw=f.read(12*44100*4)
    st=struct.unpack('<%dh'%(len(raw)//2),raw); mono=[(st[i]+st[i+1])//2 for i in range(0,len(st),2)]
    lp=[(mono[max(0,i-1)]+mono[i]+mono[min(len(mono)-1,i+1)])//3 for i in range(len(mono))]
    src=[]
    for k in range(int(len(lp)*16000/44100)-1):
        t=k*44100/16000; i=int(t); fr=t-i; src.append(int(lp[i]*(1-fr)+lp[i+1]*fr))
    pk=max(map(abs,src)); src=[int(s*28000/pk) for s in src]            # normalise like a mastered clip
    src8=[((s>>8)<<8)+128 for s in src]                                   # 8-bit source as on the Sega CD
    ad=encode(src); dec=decode(ad)[:len(src)]
    ad8=encode(src8); dec8=decode(ad8)[:len(src)]
    print(f'{len(src)/16000:.1f} s speech @16 kHz; ADPCM size {len(ad)} bytes = {len(ad)//2048} sectors')
    print(f'SNR 8-bit PCM vs 16-bit original      : {snr(src,src8):5.1f} dB   (what the Sega CD source already lost)')
    print(f'SNR ADPCM(16-bit src) vs original     : {snr(src,dec):5.1f} dB')
    print(f'SNR ADPCM(8-bit src)  vs 8-bit source : {snr(src8,dec8):5.1f} dB   (loss added by the PCE re-encode)')
    print(f'SNR ADPCM(8-bit src)  vs original     : {snr(src,dec8):5.1f} dB')
    d=os.path.dirname(__file__)
    write_wav(os.path.join(d,'roundtrip_src16k.wav'),src,16000); write_wav(os.path.join(d,'roundtrip_src8bit.wav'),src8,16000)
    write_wav(os.path.join(d,'roundtrip_adpcm.wav'),dec8,16000)
