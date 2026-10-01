from fractions import Fraction

import numpy as np

from scripts.phase2_audit_rt031_conditional_new_stop_access_v3 import weighted_ratio


def test_weighted_ratio_keeps_exact_population_mass():
    mask = np.array([True, False, True, True])
    core = np.array([True, True, True, False])
    assert weighted_ratio(mask, [1, 2, 3, 9], core) == Fraction(2, 3)
