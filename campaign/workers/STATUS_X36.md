# STATUS X36

## 1. Changed lines in `fit_segmented`

Before [OBSERVED scripts/analysis/hj12_shape.py:189-190]:
```python
    ranked.sort(key=lambda t: (t[0], t[1]))
    rss, tau, beta = ranked[0]
```

After [OBSERVED scripts/analysis/hj12_shape.py:189-197]:
```python
    mean_q = sum(qs) / len(qs)
    tss = sum((float(q) - mean_q) ** 2 for q in qs)
    # 1e-12 * max(tss, 1.0) absorbs floating-point noise on a straight line
    # without bridging genuine RSS gaps, which are orders of magnitude larger.
    tol = 1e-12 * max(tss, 1.0)
    best_rss = min(t[0] for t in ranked)
    tied = [t for t in ranked if t[0] <= best_rss + tol]
    tied.sort(key=lambda t: (t[1], t[0]))
    rss, tau, beta = tied[0]
```

## 2. Other RSS-minimising sites

Audited every `sort`, `sorted`, `min`, and `max` site across `scripts/analysis/hj12_shape.py` [OBSERVED scripts/analysis/hj12_shape.py:115,265,275,319,321,355,357,528,529,620,632,965,967]. No other RSS-minimising site exists. All estimation paths—including point estimation, bootstrap resamples [OBSERVED scripts/analysis/hj12_shape.py:324,344], TGC segmented fits [OBSERVED scripts/analysis/hj12_shape.py:634], and percentile-remapped fits [OBSERVED scripts/analysis/hj12_shape.py:640]—call `fit_segmented` directly and inherit the tolerance tie-break.

## 3. Behaviour changes

No behaviour changed other than tie-breaking on tied/near-tied RSS within floating-point tolerance [INFERRED]. Return keys, candidate handling, and degenerate returns remain identical [OBSERVED scripts/analysis/hj12_shape.py:161-170,179-188,198-208].

## 4. Blockers / Incomplete items

None.
