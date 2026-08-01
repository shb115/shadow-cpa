import numpy as np, sys, os
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
def hw(a): return np.array([bin(int(x)).count('1') for x in a],dtype=np.float64)
def mcorr(A,B):
    DA=A-A.mean(0); DB=B-B.mean(0)
    CV=DA.T@DB/np.double(len(A)); VA=np.mean(DA**2,0)[:,None]; VB=np.mean(DB**2,0)[None,:]
    r=CV/np.sqrt(VA@VB); r[np.isnan(r)]=0; return r
def welch(a,b):
    d=np.sqrt(a.var(0,ddof=1)/len(a)+b.var(0,ddof=1)/len(b)); d[d==0]=np.inf
    return (a.mean(0)-b.mean(0))/d
_HERE=os.path.dirname(os.path.abspath(__file__))
fn=sys.argv[1] if len(sys.argv)>1 else os.path.join(
       _HERE,'..','data','masked','masking_ISW_traces.npz')
W=int(sys.argv[2]) if len(sys.argv)>2 else 10000
d=np.load(fn); tr,pt,g=d['traces'],d['pt'],d['group']
fx=np.asarray(tr[g==0][:,:W],np.float64); rn=np.asarray(tr[g==1][:,:W],np.float64); P=pt[g==1]
def ROL8(v,r): return ((v<<r)|(v>>(8-r)))&0xFF
l0=P[:,0].astype(np.int64); l1=P[:,1].astype(np.int64); r0=P[:,2].astype(np.int64)
F=lambda x:(ROL8(x,1)&ROL8(x,7))^ROL8(x,2)
mods={'l0':hw(l0),'r0':hw(r0),'F(l0)':hw(F(l0)),'s0=F(l0)^l1^k0':hw(F(l0)^l1^0x0D),
      'x0=r_in0':hw(P[:,8].astype(np.int64)),'x1=l0^r_in0':hw(l0^P[:,8].astype(np.int64))}
H=np.stack(list(mods.values()),1); rho=np.abs(mcorr(rn,H))
ts=welch(fx,rn); t=np.abs(ts)
print('%s  window 0-%d,  traces %d/%d'%(fn,W,len(fx),len(rn)))
print('  TVLA max |t| = %.2f @sample %d,  samples above the 4.5 threshold %d'%(t.max(),int(t.argmax()),int((t>4.5).sum())))
print('  %-18s %9s %8s'%('model','max|rho|','@sample'))
for i,nm in enumerate(mods):
    a=rho[:,i]; print('  %-18s %9.4f %8d %s'%(nm,a.max(),int(a.argmax()),'<== leakage' if a.max()>0.2 else 'ok'))

# ---- save result visualization (PNG) ----
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
name=os.path.basename(fn)
name=name[:-4] if name.endswith('.npz') else name
name=name[:-7] if name.endswith('_traces') else name   # masking_ISW_traces -> masking_ISW
base=os.path.normpath(os.path.join(_HERE,'..','results',name))
LAB={'l0':'l0 (state secret)','r0':'r0 (state secret)','F(l0)':'F(l0)',
     's0=F(l0)^l1^k0':'s0=F(l0)^l1^k (key-dep)','x0=r_in0':'x0 (single share)',
     'x1=l0^r_in0':'x1 (single share)'}
fig,ax=plt.subplots(2,1,figsize=(12,7))
ax[0].plot(ts,lw=0.6,color='tab:blue')
ax[0].axhline(4.5,color='r',ls='--',lw=0.9); ax[0].axhline(-4.5,color='r',ls='--',lw=0.9)
ax[0].set_title('TVLA (Welch t)  %s   max|t|=%.1f,  #|t|>4.5 = %d'%(name,t.max(),int((t>4.5).sum())))
ax[0].set_xlabel('sample'); ax[0].set_ylabel('t-statistic'); ax[0].margins(x=0)
for i,nm in enumerate(mods):
    ax[1].plot(rho[:,i],lw=0.7,label=LAB.get(nm,nm))
ax[1].axhline(0.2,color='0.5',ls=':',lw=0.8)
ax[1].set_title('|correlation| with Hamming-weight models'); ax[1].set_xlabel('sample')
ax[1].set_ylabel('|corr|'); ax[1].margins(x=0); ax[1].legend(fontsize=7,ncol=3,loc='upper right')
fig.tight_layout(); png=base+'_tvla.png'; fig.savefig(png,dpi=120); plt.close(fig)
print('  PNG saved: %s'%png)
