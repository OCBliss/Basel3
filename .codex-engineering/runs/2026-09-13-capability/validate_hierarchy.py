"""Reproduce synthetic controls, actual-data held-out checks and step refinement."""
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.RWA.models.parameter_hierarchy import workflow as h

HERE = Path(__file__).resolve().parent
started = time.perf_counter()
results = {"synthetic": [], "held_out": [], "refinement": []}

# Identical rate shocks isolate the effect of changing the known diffusion
# coefficient. A periodic coefficient is a deliberate stress case, not a claim
# that a sinusoid is a CIR volatility process.
for seed in range(8):
    rng = np.random.default_rng(seed+150)
    noise = rng.normal(size=(383,2))
    for mode in ['constant','varying']:
        values = np.empty((384,2))
        values[0] = [3.,4.]
        for t in range(383):
            sigma = .4 if mode=='constant' else .4+.25*np.sin(2*np.pi*t/128)
            values[t+1] = values[t]+4*(np.array([3.,4.])-values[t])/252 + sigma*np.sqrt(values[t]/252)*noise[t]
        assert (values>0).all()
        panel = pd.DataFrame(values,index=pd.bdate_range('2020-01-01',periods=384),columns=[1,2])
        first = h.calibrate_panel(panel,64)
        second = h.calibrate_parameters(first,64)
        tail = second.loc[second.observation_date >= panel.index[-64]]
        for parameter in h.PARAMETERS:
            results['synthetic'].append({"seed":seed,"mode":mode,"parameter":parameter,
                "mean_diffusion":float(tail.loc[tail.parameter==parameter,'sigma'].mean())})
print('synthetic controls complete',time.perf_counter()-started,flush=True)

yields,sources = h.read_yield_panel('RWA/FRED')
for days_back in [60,40,20]:
    training = yields.iloc[:-days_back].iloc[-2792:]
    actual = yields.iloc[-days_back+19].to_numpy()
    first = h.calibrate_panel(training,2520)
    second = h.calibrate_parameters(first,252)
    initial,c,corr,factor,audit = h.forecast_inputs(training,first,second,252,1/252)
    for mode in ['stochastic_parameters','fixed_parameters']:
        coefficients = c.copy()
        if mode=='fixed_parameters': coefficients[:]=0
        samples,hits = h.simulate(initial,coefficients,factor,paths=2048,steps=20,seed=630,substeps=4)
        end = samples[:,-1,0]
        for j,tenor in enumerate(training.columns):
            low,median,high = np.quantile(end[:,j],[.05,.5,.95])
            results['held_out'].append({"origin":str(training.index[-1].date()),"mode":mode,
                "maturity":int(tenor),"actual":float(actual[j]),"mean":float(end[:,j].mean()),
                "q05":float(low),"q95":float(high),"covered90":bool(low<=actual[j]<=high),
                "squared_error":float((end[:,j].mean()-actual[j])**2),
                "interval_score90":float(high-low+20*max(low-actual[j],0)+20*max(actual[j]-high,0)),
                "boundary_projections":int(hits.sum())})
    print('held out origin',str(training.index[-1].date()),time.perf_counter()-started,flush=True)

# Standalone CIR has known moments. Keep the other three states constant and
# compare the evolving rate's distribution against the exact finite-horizon law.
initial = np.array([[4.],[3.],[6.],[.4]])
coefficients = np.zeros((3,3,1))
horizon = 20/252
decay = np.exp(-6*horizon)
exact_mean = 3+(4-3)*decay
exact_var = 4*.4**2*decay*(1-decay)/6 + 3*.4**2*(1-decay)**2/(2*6)
for substeps in [1,4,16]:
    sample,hits = h.simulate(initial,coefficients,np.eye(4),paths=20000,steps=20,
                             seed=820,substeps=substeps)
    x = sample[:,-1,0,0]
    results['refinement'].append({"substeps":substeps,"mean":float(x.mean()),"variance":float(x.var()),
        "exact_mean":float(exact_mean),"exact_variance":float(exact_var),
        "boundary_projections":int(hits.sum())})
results['elapsed_seconds'] = time.perf_counter()-started
results['source_files'] = sources
(HERE/'validation-results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
print('validation complete',results['elapsed_seconds'],flush=True)
