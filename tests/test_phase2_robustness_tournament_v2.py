from decimal import Decimal

from src.phase2_robustness_tournament_v2 import (
    dominates,
    margin_gap_summary,
    nondominated_indices,
    weighted_cell_mean,
)


def test_fractional_connection_margin_is_respected():
    sources = (Decimal('10'), Decimal('20'))
    targets = (Decimal('11'), Decimal('12'), Decimal('22'))
    out = margin_gap_summary(sources, targets, margin_min=Decimal('1.5'))
    assert out.source_count == 2
    assert out.matched_count == 2
    assert out.unmatched_count == 0
    assert out.mean_gap_min == 2.0


def test_margin_gap_counts_end_of_span_unmatched():
    out = margin_gap_summary((Decimal('9'), Decimal('29')), (Decimal('10'), Decimal('20'), Decimal('30')), margin_min=Decimal('2'))
    assert out.matched_count == 1
    assert out.unmatched_count == 1
    assert out.mean_gap_min == 11.0


def test_weighted_cell_mean_does_not_invent_missing_cell():
    assert weighted_cell_mean([(2.0, 4.0), (1.0, None)]) == 4.0
    assert weighted_cell_mean([(1.0, None)]) is None


def test_dominance_requires_no_regression_and_one_strict_gain():
    a = {'coverage': 0.5, 'headway': 20, 'gap': 5}
    b = {'coverage': 0.4, 'headway': 30, 'gap': 6}
    c = {'coverage': 0.6, 'headway': 60, 'gap': 4}
    assert dominates(a, b, maximize=('coverage',), minimize=('headway', 'gap'))
    assert not dominates(a, c, maximize=('coverage',), minimize=('headway', 'gap'))
    assert not dominates(a, a, maximize=('coverage',), minimize=('headway', 'gap'))


def test_nondominated_indices_preserve_tradeoffs():
    rows = [
        {'coverage': 0.5, 'headway': 30},
        {'coverage': 0.6, 'headway': 60},
        {'coverage': 0.4, 'headway': 60},
    ]
    assert nondominated_indices(rows, maximize=('coverage',), minimize=('headway',)) == (0, 1)
