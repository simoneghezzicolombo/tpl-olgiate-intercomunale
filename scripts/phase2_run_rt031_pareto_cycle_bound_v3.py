import argparse
import pandas as pd
from phase2_rt031_pareto_cycle_bound_v3 import write_outputs

p = argparse.ArgumentParser()
p.add_argument("--links", required=True)
p.add_argument("--patterns", required=True)
p.add_argument("--realizations", required=True)
p.add_argument("--outdir", required=True)
a = p.parse_args()
audit = write_outputs(pd.read_csv(a.links), pd.read_csv(a.patterns), pd.read_csv(a.realizations), a.outdir)
print(audit["status"])
