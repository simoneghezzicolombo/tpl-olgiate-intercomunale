from scripts.phase2_probe_rt031_arlate_retention_v3 import (
    ARLATE, probe_targets)


def test_each_inner_arlate_stop_gets_unfiltered_base_and_separate_retention_probes():
    targets = probe_targets(("FROZEN::L00407", "FROZEN::300063",
                             "FROZEN::300805", "FROZEN::300487",
                             "FROZEN::300879"))
    assert len(targets) == 6
    for arlate in ARLATE:
        assert (arlate, ()) in targets
        assert (arlate, ("FROZEN::300487",)) in targets
        assert (arlate, ("FROZEN::300879",)) in targets
        assert (arlate, ("FROZEN::300805",)) not in targets


def test_quadruple_probe_preserves_combination_not_discretionary_pick():
    current = ("FROZEN::L00407", "FROZEN::300063", "FROZEN::300805",
               "FROZEN::300086", "FROZEN::300398", "FROZEN::300487",
               "FROZEN::300634", "FROZEN::300879", "FROZEN::300956")
    targets = probe_targets(current, 4)
    assert len(targets) == 32
    assert all(len(stops) == 4 or not stops for _, stops in targets)
