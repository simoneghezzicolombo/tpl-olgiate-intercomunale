"""Explain five-minute losses without changing the confirmed coverage asset."""
import json
import sys
from pathlib import Path
from build_nodo8_coverage_comparison import build_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/nodo8-coverage-diagnostic.json'
if __name__ == '__main__':
    comparison,diagnostic=build_data(include_diagnostics=True)
    existing=json.loads((ROOT / 'assets/nodo8-coverage-comparison.json').read_text(encoding='utf-8'))
    if comparison != existing:
        raise SystemExit('Certified spatial comparison changed; diagnostic rejected')
    payload=json.dumps(diagnostic,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if '--check' in sys.argv:
        if OUT.read_text(encoding='utf-8') != payload:
            raise SystemExit('Coverage diagnostic does not reproduce')
    else:
        OUT.write_text(payload,encoding='utf-8')
    for code,detail in diagnostic['municipality_details'].items():
        print(code,'gross lost',round(detail['lost_pp'],3),'gained',round(detail['gained_pp'],3),
              [(r['name'],round(r['loss_share_pp'],3)) for r in detail['old_closest_groups_for_lost_units'][:4]])
