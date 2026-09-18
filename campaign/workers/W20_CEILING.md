# W-20 — Re-cutting the Estimand Excluding Ceiling Points

**Analysis only. No production code modified. Nothing committed. Zero live `codex` / planner calls. No GPU jobs.**
Script: `campaign/workers/scratch_W20/analyze_ceiling.py`.
Raw verbatim output: `campaign/workers/scratch_W20/w20_out.txt`.
Executed in PBS job **25433129.aqua** (`cpu1n040`, exit 0).
Every number below is `[INFERRED, job 25433129.aqua]` from the frozen raw data files unless tagged `[OBSERVED]` to a source line.

Data sources:
- Train: `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl`
- Dev: `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl`

---

## 0. Executive Summary & Verification of Invariants

1. **Ceiling Point Prevalence**:
   - **Train**: **131 of 397 complete points (32.9975% ≈ 33.0%)** have $\text{mean}(\text{untreated}) = 1.000$ `[INFERRED, job 25433129.aqua]`.
   - **Dev**: **68 of 332 complete points (20.4819% ≈ 20.5%)** have $\text{mean}(\text{untreated}) = 1.000$ `[INFERRED, job 25433129.aqua]`.
   - Float noise check: testing threshold $\ge 0.999$ yields identical counts (131 train, 68 dev; diff = 0) `[INFERRED, job 25433129.aqua]`.
2. **Structural Properties of Ceiling Points**:
   - For all ceiling points, $\text{mean}(\text{untreated}) = 1.000$. Since $\text{gpr} \le 1.000$, $\text{mean}(\text{treated}) \le 1.000$, which guarantees $\Delta \le 0.000$ and $\text{help} = \max(\Delta, 0) = 0.000000$ *by construction*.
   - Ceiling points contribute only $\Delta = 0$ (no effect) or $\Delta < 0$ (harm):
     - Train ceiling: 99 points have $\Delta = 0.0$, 32 points have $\Delta < 0.0$ (mean $\Delta = -0.049172$, mean harm = $0.049172$) `[INFERRED, job 25433129.aqua]`.
     - Dev ceiling: 54 points have $\Delta = 0.0$, 14 points have $\Delta < 0.0$ (mean $\Delta = -0.044588$, mean harm = $0.044588$) `[INFERRED, job 25433129.aqua]`.
3. **Strict Invariant Verification — `needed` Counts**:
   - **Excluding ceiling (and floor) points does NOT alter the `needed` count by even a single point** at any threshold:
     - Train at $\delta = 0.166$: `needed = 25` on all 397 points, `needed = 25` on 266 non-ceiling points, `needed = 25` on 263 contestable points (`CEIL = 0`, `FLOOR = 0`) `[INFERRED, job 25433129.aqua]`.
     - Train at $\delta = 0.100$: `needed = 54` across all sets (`CEIL = 0`, `FLOOR = 0`) `[INFERRED, job 25433129.aqua]`.
     - Dev at $\delta = 0.166$: `needed = 43` across all sets (`CEIL = 0`, `FLOOR = 0`) `[INFERRED, job 25433129.aqua]`.
     - Dev at $\delta = 0.100$: `needed = 72` across all sets (`CEIL = 0`, `FLOOR = 0`) `[INFERRED, job 25433129.aqua]`.
   - The transformation strictly modifies the denominator $n$.
4. **Headline Effect (Sign Flip on Train)**:
   - On **train**, overall mean $\Delta$ shifts from **$-0.014393$** (all complete points) to **$+0.002766$** (contestable points) or **$+0.002735$** (non-ceiling points) `[INFERRED, job 25433129.aqua]`.
   - The sign of the headline mean $\Delta$ on train **flips from negative to positive**.
   - On **dev**, mean $\Delta$ increases from **$+0.009702$** to **$+0.023686$** `[INFERRED, job 25433129.aqua]`.
5. **Pre-registration Stance**: Per the brief, this analysis presents neutral evidence; no policy recommendation to alter the pre-registration is made.

---

## 1. Population & Point Classification Breakdown

A complete point is defined by having all 4 replicate seeds (101, 102, 103, 104) for both conditions (`treated` and `untreated`).
- **Ceiling Point**: $\text{mean}(\text{untreated}) \ge 1.0$
- **Floor Point**: $\text{mean}(\text{untreated}) \le 0.0$ and $\text{mean}(\text{treated}) \le 0.0$
- **Contestable Points (Remainder)**: $\text{Complete} \setminus (\text{Ceiling} \cup \text{Floor})$
- **Non-Ceiling Points**: $\text{Complete} \setminus \text{Ceiling} = \text{Contestable} \cup \text{Floor}$

### Train Counts (`n = 397` complete of 777 total points; 380 incomplete, 1357 null rows) `[INFERRED, job 25433129.aqua]`

| Point Class | Definition / Criteria | Count ($n$) | Fraction of Complete ($n / 397$) |
|---|---|---:|---:|
| **All Complete** | All 4 reps evaluated for treated & untreated | **397** | **100.00%** (1.0000) |
| **Ceiling** | $\text{mean}(\text{untreated}) \ge 1.0$ | **131** | **33.00%** (0.3300) |
| **Floor** | $\text{mean}(\text{untreated}) \le 0$ & $\text{mean}(\text{treated}) \le 0$ | **3** | **0.76%** (0.0076) |
| **Contestable** | Non-ceiling and non-floor | **263** | **66.25%** (0.6625) |
| **Non-Ceiling** | All complete minus ceiling ($\text{Contestable} + \text{Floor}$) | **266** | **67.00%** (0.6700) |

*Threshold noise check*: At $\text{mean}(\text{untreated}) \ge 0.999$, ceiling count is 131 (diff = 0). At $\le 0.001$, floor count is 3 (diff = 0).

### Dev Counts (`n = 332` complete of 382 total points; 50 incomplete, 141 null rows) `[INFERRED, job 25433129.aqua]`

| Point Class | Definition / Criteria | Count ($n$) | Fraction of Complete ($n / 332$) |
|---|---|---:|---:|
| **All Complete** | All 4 reps evaluated for treated & untreated | **332** | **100.00%** (1.0000) |
| **Ceiling** | $\text{mean}(\text{untreated}) \ge 1.0$ | **68** | **20.48%** (0.2048) |
| **Floor** | $\text{mean}(\text{untreated}) \le 0$ & $\text{mean}(\text{treated}) \le 0$ | **0** | **0.00%** (0.0000) |
| **Contestable** | Non-ceiling and non-floor | **264** | **79.52%** (0.7952) |
| **Non-Ceiling** | All complete minus ceiling (identical to contestable) | **264** | **79.52%** (0.7952) |

*Threshold noise check*: At $\text{mean}(\text{untreated}) \ge 0.999$, ceiling count is 68 (diff = 0). At $\le 0.001$, floor count is 0 (diff = 0).

---

## 2. Label Distributions & Estimands ($f$ and $1 - f$)

> [!IMPORTANT]
> **Definition of $f$**: $f = \frac{\text{needed}}{n}$, and $1 - f = \frac{n - \text{needed}}{n} = \frac{\text{needless} + \text{ambiguous}}{n}$.
> (Every table below explicitly prints the exact numerator and denominator).

### Train Split Label Distributions `[INFERRED, job 25433129.aqua]`

#### At Frozen Threshold $\delta = 0.166$:

| Metric / Label | All Complete Points ($n = 397$) | Contestable Only ($n = 263$) | Non-Ceiling ($n = 266$) | Ceiling Only ($n = 131$) | Floor Only ($n = 3$) |
|---|---|---|---|---|---|
| **`needed`** ($\Delta > \delta$) | **25** ($25 / 397 = 6.30\%$) | **25** ($25 / 263 = 9.51\%$) | **25** ($25 / 266 = 9.40\%$) | **0** ($0 / 131 = 0.00\%$) | **0** ($0 / 3 = 0.00\%$) |
| **`needless`** ($\Delta < -\delta$) | **46** ($46 / 397 = 11.59\%$) | **31** ($31 / 263 = 11.79\%$) | **31** ($31 / 266 = 11.65\%$) | **15** ($15 / 131 = 11.45\%$) | **0** ($0 / 3 = 0.00\%$) |
| **`ambiguous`** ($|\Delta| \le \delta$) | **326** ($326 / 397 = 82.12\%$) | **207** ($207 / 263 = 78.71\%$) | **210** ($210 / 266 = 78.95\%$) | **116** ($116 / 131 = 88.55\%$) | **3** ($3 / 3 = 100.00\%$) |
| **$f = \frac{\text{needed}}{n}$** | $\frac{25}{397} = \mathbf{0.0630}$ | $\frac{25}{263} = \mathbf{0.0951}$ | $\frac{25}{266} = \mathbf{0.0940}$ | $\frac{0}{131} = \mathbf{0.0000}$ | $\frac{0}{3} = \mathbf{0.0000}$ |
| **$1 - f = \frac{n - \text{needed}}{n}$** | $\frac{372}{397} = \mathbf{0.9370}$ | $\frac{238}{263} = \mathbf{0.9049}$ | $\frac{241}{266} = \mathbf{0.9060}$ | $\frac{131}{131} = \mathbf{1.0000}$ | $\frac{3}{3} = \mathbf{1.0000}$ |

#### At Derived Threshold $\delta = 0.100$:

| Metric / Label | All Complete Points ($n = 397$) | Contestable Only ($n = 263$) | Non-Ceiling ($n = 266$) | Ceiling Only ($n = 131$) | Floor Only ($n = 3$) |
|---|---|---|---|---|---|
| **`needed`** ($\Delta > \delta$) | **54** ($54 / 397 = 13.60\%$) | **54** ($54 / 263 = 20.53\%$) | **54** ($54 / 266 = 20.30\%$) | **0** ($0 / 131 = 0.00\%$) | **0** ($0 / 3 = 0.00\%$) |
| **`needless`** ($\Delta < -\delta$) | **67** ($67 / 397 = 16.88\%$) | **45** ($45 / 263 = 17.11\%$) | **45** ($45 / 266 = 16.92\%$) | **22** ($22 / 131 = 16.79\%$) | **0** ($0 / 3 = 0.00\%$) |
| **`ambiguous`** ($|\Delta| \le \delta$) | **276** ($276 / 397 = 69.52\%$) | **164** ($164 / 263 = 62.36\%$) | **167** ($167 / 266 = 62.78\%$) | **109** ($109 / 131 = 83.21\%$) | **3** ($3 / 3 = 100.00\%$) |
| **$f = \frac{\text{needed}}{n}$** | $\frac{54}{397} = \mathbf{0.1360}$ | $\frac{54}{263} = \mathbf{0.2053}$ | $\frac{54}{266} = \mathbf{0.2030}$ | $\frac{0}{131} = \mathbf{0.0000}$ | $\frac{0}{3} = \mathbf{0.0000}$ |
| **$1 - f = \frac{n - \text{needed}}{n}$** | $\frac{343}{397} = \mathbf{0.8640}$ | $\frac{209}{263} = \mathbf{0.7947}$ | $\frac{212}{266} = \mathbf{0.7970}$ | $\frac{131}{131} = \mathbf{1.0000}$ | $\frac{3}{3} = \mathbf{1.0000}$ |

---

### Dev Split Label Distributions `[INFERRED, job 25433129.aqua]`

#### At Frozen Threshold $\delta = 0.166$:

| Metric / Label | All Complete Points ($n = 332$) | Contestable Only ($n = 264$) | Non-Ceiling ($n = 264$) | Ceiling Only ($n = 68$) |
|---|---|---|---|---|
| **`needed`** ($\Delta > \delta$) | **43** ($43 / 332 = 12.95\%$) | **43** ($43 / 264 = 16.29\%$) | **43** ($43 / 264 = 16.29\%$) | **0** ($0 / 68 = 0.00\%$) |
| **`needless`** ($\Delta < -\delta$) | **43** ($43 / 332 = 12.95\%$) | **36** ($36 / 264 = 13.64\%$) | **36** ($36 / 264 = 13.64\%$) | **7** ($7 / 68 = 10.29\%$) |
| **`ambiguous`** ($|\Delta| \le \delta$) | **246** ($246 / 332 = 74.10\%$) | **185** ($185 / 264 = 70.08\%$) | **185** ($185 / 264 = 70.08\%$) | **61** ($61 / 68 = 89.71\%$) |
| **$f = \frac{\text{needed}}{n}$** | $\frac{43}{332} = \mathbf{0.1295}$ | $\frac{43}{264} = \mathbf{0.1629}$ | $\frac{43}{264} = \mathbf{0.1629}$ | $\frac{0}{68} = \mathbf{0.0000}$ |
| **$1 - f = \frac{n - \text{needed}}{n}$** | $\frac{289}{332} = \mathbf{0.8705}$ | $\frac{221}{264} = \mathbf{0.8371}$ | $\frac{221}{264} = \mathbf{0.8371}$ | $\frac{68}{68} = \mathbf{1.0000}$ |

#### At Derived Threshold $\delta = 0.100$:

| Metric / Label | All Complete Points ($n = 332$) | Contestable Only ($n = 264$) | Non-Ceiling ($n = 264$) | Ceiling Only ($n = 68$) |
|---|---|---|---|---|
| **`needed`** ($\Delta > \delta$) | **72** ($72 / 332 = 21.69\%$) | **72** ($72 / 264 = 27.27\%$) | **72** ($72 / 264 = 27.27\%$) | **0** ($0 / 68 = 0.00\%$) |
| **`needless`** ($\Delta < -\delta$) | **61** ($61 / 332 = 18.37\%$) | **50** ($50 / 264 = 18.94\%$) | **50** ($50 / 264 = 18.94\%$) | **11** ($11 / 68 = 16.18\%$) |
| **`ambiguous`** ($|\Delta| \le \delta$) | **199** ($199 / 332 = 59.94\%$) | **142** ($142 / 264 = 53.79\%$) | **142** ($142 / 264 = 53.79\%$) | **57** ($57 / 68 = 83.82\%$) |
| **$f = \frac{\text{needed}}{n}$** | $\frac{72}{332} = \mathbf{0.2169}$ | $\frac{72}{264} = \mathbf{0.2727}$ | $\frac{72}{264} = \mathbf{0.2727}$ | $\frac{0}{68} = \mathbf{0.0000}$ |
| **$1 - f = \frac{n - \text{needed}}{n}$** | $\frac{260}{332} = \mathbf{0.7831}$ | $\frac{192}{264} = \mathbf{0.7273}$ | $\frac{192}{264} = \mathbf{0.7273}$ | $\frac{68}{68} = \mathbf{1.0000}$ |

---

## 3. Continuous Estimands: Mean $\Delta$, Help, and Harm

$\Delta = \text{mean}(\text{treated}) - \text{mean}(\text{untreated})$, $\text{help} = \max(\Delta, 0)$, $\text{harm} = \max(-\Delta, 0)$.

### Continuous Metrics Table `[INFERRED, job 25433129.aqua]`

| Split | Point Set | $n$ | $\text{mean}(\text{treated})$ | $\text{mean}(\text{untreated})$ | $\text{mean}(\Delta)$ | $\text{SD}(\Delta)$ | $\text{mean}(\text{help})$ | $\text{mean}(\text{harm})$ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **TRAIN** | **All Complete** | 397 | 0.763704 | 0.778097 | **$-0.014393$** | 0.149548 | 0.034101 | 0.048494 |
| | **Ceiling Points** | 131 | 0.950828 | 1.000000 | **$-0.049172$** | 0.118553 | 0.000000 | 0.049172 |
| | **Floor Points** | 3 | 0.000000 | 0.000000 | **$+0.000000$** | 0.000000 | 0.000000 | 0.000000 |
| | **Contestable Points** | 263 | 0.679209 | 0.676443 | **$+0.002766$** | 0.161017 | 0.051475 | 0.048709 |
| | **Non-Ceiling Points** | 266 | 0.671549 | 0.668814 | **$+0.002735$** | 0.160104 | 0.050895 | 0.048160 |
| **DEV** | **All Complete** | 332 | 0.678471 | 0.668770 | **$+0.009702$** | 0.174911 | 0.058932 | 0.049230 |
| | **Ceiling Points** | 68 | 0.955412 | 1.000000 | **$-0.044588$** | 0.114636 | 0.000000 | 0.044588 |
| | **Floor Points** | 0 | 0.000000 | 0.000000 | **$+0.000000$** | 0.000000 | 0.000000 | 0.000000 |
| | **Contestable Points** | 264 | 0.607138 | 0.583453 | **$+0.023686$** | 0.184927 | 0.074112 | 0.050426 |
| | **Non-Ceiling Points** | 264 | 0.607138 | 0.583453 | **$+0.023686$** | 0.184927 | 0.074112 | 0.050426 |

---

## 4. Quantitative Decomposition of Ceiling Drag on Mean $\Delta$

The overall mean $\Delta$ is an exact weighted mixture of ceiling and non-ceiling components:
$$\overline{\Delta}_{\text{all}} = \frac{n_{\text{ceil}}}{N} \cdot \overline{\Delta}_{\text{ceil}} + \frac{n_{\text{non-ceil}}}{N} \cdot \overline{\Delta}_{\text{non-ceil}}$$

### Train Decomposition `[INFERRED, job 25433129.aqua]`
- **Overall Mean $\Delta$**: $-0.014393$
- **Ceiling Component Weight**: $\frac{131}{397} = 0.329975$ (33.00%)
- **Ceiling Mean $\Delta$**: $-0.049172$
- **Ceiling Drag ($w_{\text{ceil}} \cdot \overline{\Delta}_{\text{ceil}}$)**: **$-0.016225$**
- **Non-Ceiling Component Weight**: $\frac{266}{397} = 0.670025$ (67.00%)
- **Non-Ceiling Mean $\Delta$**: $+0.002735$
- **Non-Ceiling Contribution**: $+0.001832$
- **Reconstructed Overall $\Delta$**: $-0.016225 + 0.001832 = -0.014393$ (exact match)
- **Net Shift from Excluding Ceiling Points**: $\Delta \overline{\Delta} = +0.002735 - (-0.014393) = \mathbf{+0.017128}$ (for non-ceiling) or $\mathbf{+0.017159}$ (for contestable).
- On contestable points, $\text{mean}(\text{help}) = 0.051475 > \text{mean}(\text{harm}) = 0.048709$.

### Dev Decomposition `[INFERRED, job 25433129.aqua]`
- **Overall Mean $\Delta$**: $+0.009702$
- **Ceiling Component Weight**: $\frac{68}{332} = 0.204819$ (20.48%)
- **Ceiling Mean $\Delta$**: $-0.044588$
- **Ceiling Drag ($w_{\text{ceil}} \cdot \overline{\Delta}_{\text{ceil}}$)**: **$-0.009133$**
- **Non-Ceiling Component Weight**: $\frac{264}{332} = 0.795181$ (79.52%)
- **Non-Ceiling Mean $\Delta$**: $+0.023686$
- **Non-Ceiling Contribution**: $+0.018835$
- **Reconstructed Overall $\Delta$**: $-0.009133 + 0.018835 = +0.009702$ (exact match)
- **Net Shift from Excluding Ceiling Points**: $\Delta \overline{\Delta} = +0.023686 - (+0.009702) = \mathbf{+0.013984}$.
- On contestable points, $\text{mean}(\text{help}) = 0.074112 > \text{mean}(\text{harm}) = 0.050426$.

---

## 5. Summary Findings & Return Contract Checklist

1. **Counts**:
   - Train ($N=397$): Ceiling = 131 (33.00%), Floor = 3 (0.76%), Contestable = 263 (66.25%), Non-Ceiling = 266 (67.00%).
   - Dev ($N=332$): Ceiling = 68 (20.48%), Floor = 0 (0.00%), Contestable = 264 (79.52%), Non-Ceiling = 264 (79.52%).
2. **Label Distributions & $f$**:
   - Train $\delta=0.166$: All $f = 25/397 = 0.0630$; Contestable $f = 25/263 = 0.0951$; Non-Ceiling $f = 25/266 = 0.0940$.
   - Train $\delta=0.100$: All $f = 54/397 = 0.1360$; Contestable $f = 54/263 = 0.2053$; Non-Ceiling $f = 54/266 = 0.2030$.
   - Dev $\delta=0.166$: All $f = 43/332 = 0.1295$; Contestable $f = 43/264 = 0.1629$.
   - Dev $\delta=0.100$: All $f = 72/332 = 0.2169$; Contestable $f = 72/264 = 0.2727$.
3. **Invariant Confirmation**:
   - `needed` point counts are identically 25 (Train $\delta=0.166$), 54 (Train $\delta=0.100$), 43 (Dev $\delta=0.166$), 72 (Dev $\delta=0.100$) across All, Non-Ceiling, and Contestable sets.
   - Verified that ceiling points have zero `needed` points and zero positive $\Delta$.
4. **Quantified Ceiling Drag**:
   - Train ceiling points drag overall mean $\Delta$ down by **$-0.016225$**. Excluding them flips train mean $\Delta$ from $-0.014393$ to $+0.002766$ (contestable) with help ($0.0515$) > harm ($0.0487$).
   - Dev ceiling points drag overall mean $\Delta$ down by **$-0.009133$**. Excluding them lifts dev mean $\Delta$ from $+0.009702$ to $+0.023686$.
