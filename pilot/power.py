import numpy as np
from scipy import stats
rng=np.random.default_rng(0)
z=stats.norm.ppf
# 1) Empirical: earlier replay, n=55, conditional logit OR 1.58 [0.80,3.11]
se55=np.log(3.11/0.80)/(2*1.96)
print(f"SE(logOR) at n=55: {se55:.3f}")
for a,lab in [(0.05,'alpha .05'),(0.01,'alpha .01 (5 detectors)')]:
    for OR in [1.5,1.58,2,2.5,3]:
        se_need=np.log(OR)/(z(1-a/2)+z(0.8))
        n=55*(se55/se_need)**2
        print(f"  {lab}: OR {OR}: n for 80% power ~ {n:.0f}")
# 2) rank test: percentile of involved vessel among k matched controls (AUC). Simulate.
def power_rank(n,auc,k=10,a=0.05,sims=4000):
    # binormal model: control scores N(0,1), involved N(d,1) with AUC=Phi(d/sqrt2)
    d=np.sqrt(2)*z(auc); hits=0
    for _ in range(sims):
        inv=rng.normal(d,1,n); ctl=rng.normal(0,1,(n,k))
        u=((ctl<inv[:,None]).sum(1)+0.5)/(k+1)
        # null: u uniform on {(j+.5)/(k+1)}, var=((k+1)^2-1)/(12(k+1)^2)
        v=((k+1)**2-1)/(12*(k+1)**2)
        t=(u.mean()-0.5)/np.sqrt(v/n)
        hits+= abs(t)>z(1-a/2)
    return hits/sims
print("rank test (k=10 matched controls), power:")
for auc in [0.55,0.60,0.65,0.70]:
    print(' AUC',auc,' '.join(f"n={n}:{power_rank(n,auc):.2f}" for n in [55,90,120,200,300]))
print("same, alpha .01:")
for auc in [0.55,0.60,0.65]:
    print(' AUC',auc,' '.join(f"n={n}:{power_rank(n,auc,a=0.01,sims=3000):.2f}" for n in [90,120,200,300]))
# 3) binary flag at fixed alarm budget p0, involved rate RR*p0, compare to known base (exact binomial)
print("binary flag at budget, power (two-sided .05, exact binomial vs known base):")
for p0 in [0.01,0.05,0.10]:
    for RR in [2,3,5]:
        row=[]
        for n in [90,120,200,300]:
            crit=stats.binom.isf(0.025,n,p0)  # reject if X>crit
            row.append(f"n={n}:{stats.binom.sf(crit,n,min(1,RR*p0)):.2f}")
        print(f" budget {p0:.0%} RR {RR}: "+' '.join(row))
