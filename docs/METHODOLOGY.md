# Methodology

How this desk decides, and how we know whether it is right.

This document is the intellectual core of the repository. If you read one
thing, read §1 and §2: they explain the single idea that makes the whole
design make sense, and the design decision that a return-based backtest would
have got wrong.

Every formula here is implemented in `src/` and pinned by a test. Every
threshold is a named constant in the file that uses it. Every citation
resolves.

---

## 1. The one idea: a hedge is a trade in risk, not a trade in profit

Most people meet "hedge" as a word and leave it there. Here is what it
actually means operationally.

A hedge is a position that **reduces the dispersion of outcomes**. Its job is
to make the range of things that can happen to you smaller. That is the whole
claim. A hedge that does not lower volatility is a cost with no benefit, and
no amount of backtest prettiness changes that.

Three corollaries that the rest of this document depends on:

1. **A perfect hedge has zero forward-return correlation.** If the hedge
   removes exactly the risk you were worried about, then the hedged portfolio
   is uncorrelated with what you hedged *by construction*. This is algebra,
   not opinion, and it invalidates the standard way of testing trading
   systems when you apply it to a hedging system. See §2.

2. **Risk that a market instrument cannot remove is risk you keep.** The Scan
   seat splits each holding's risk into the part a market hedge can offset
   (systematic) and the part it cannot (idiosyncratic). Only the first is
   worth hedging, and only the first is counted.

3. **A hedge costs money to put on and gives up a risk premium.** You pay
   fees and slippage, and you give up the expected return of the factor you
   hedged. So a hedge has to be judged on whether the risk reduction is
   worth the price. That is a *compensation* question, not an *accuracy*
   question.

The framework we use for (1) and (3) is Healy and Lo (2010) — see §3.

---

## 2. Why the usual backtest gates are wrong for a hedge

A trading-strategy backtest is usually judged with four gates: does the
signal predict forward returns (information), does it survive costs (cost),
does it compound (compounding), is it stable (stability).

The **information** gate is the one that breaks, and it breaks for a reason
that is worth understanding rather than working around.

Take a portfolio `P` and a hedge instrument `H`. Suppose you hedge perfectly:
the hedged portfolio `P + f·H` has variance that does not depend on the
market factor. Now ask: "does the hedged portfolio's return correlate with
future returns?" The answer is **no, and it is supposed to be no**. A perfect
hedge is uncorrelated with the market *because that is what it is for*.

So a gate of the form "reject the hedge if its forward-return information
coefficient is too low" does the opposite of what it is supposed to do:

- it **rejects the best possible hedge**, because a well-functioning hedge has
  near-zero return correlation;
- it **passes a useless one**, because a hedge that barely removes any risk
  leaves plenty of market exposure and therefore plenty of return correlation.

This is not a threshold to tune. It is the wrong question. We removed that
gate and replaced the stack with four questions that a hedge can actually
answer.

### The four gates

Implemented in `src/evaluation/gates.py`. They run in order and
**short-circuit on the first failure**: a hedge that fails gate 1 does not
need to be tested on gate 3, and pretending otherwise manufactures evidence.

| # | Gate | The question it asks | Pass criterion | Source |
|---|---|---|---|---|
| 1 | `hedgeability` | Is there anything to hedge? | R² of the hedging equation **≥ 25%** | Healy & Lo (2010), §2 and condition (B) |
| 2 | `regime_information` | Does the dial anticipate forward volatility? | Spearman rank IC **≥ 0.02** **and** Newey–West HAC **t ≥ 1.96**; expected sign **positive** | this repository |
| 3 | `compensation` | Did the risk reduction pay for itself? | Hedged Sharpe **>** unhedged Sharpe **and** volatility reduction > 0, costs already deducted | Healy & Lo (2010), condition (A2) |
| 4 | `stability` | Does it hold across regimes and across time? | **≥ 50%** of populated regimes improved; **≥ 70%** of walk-forward windows positive | this repository |

**Gate 1 — hedgeability.** R² here is the fraction of the portfolio's return
variance explained by the hedge instrument. If the hedge instrument explains
almost none of your risk, an overlay against it cannot help: it adds cost and
tracking error while removing almost nothing. The 25% threshold is
Healy and Lo's, and they are careful about its status — they call it "a very
rough guideline", not a law. We take it seriously because it is the only
number in the framework with a citation behind it, but we hold it as a
guideline rather than a law.

**Gate 2 — regime information.** The dial is the desk's decision variable:
how much hedging is worth doing right now. It is built from the volatility
percentile and the trend state. If the dial is uninformative, the desk is
hedge-sizing at random times. The test is a rank correlation between the
dial and *forward realised volatility*, plus a Newey–West HAC t-statistic,
because daily signals are autocorrelated and a naive t-statistic would
overstate the evidence.

The expected sign is **positive**: a high dial means "hedge more", and that
should mean "volatility is coming". A dial that is high when the market is
calm is backwards, and this gate is what catches that.

**Gate 3 — compensation.** Healy and Lo's condition (A2) is about whether the
risk reduction is worth what you give up. Our test is the Sharpe ratio,
hedged versus unhedged, with transaction costs already deducted from the
hedged series. We also report the realised volatility reduction against the
theoretical ceiling implied by R², so a reader can see whether the overlay is
delivering what the theory says it can.

**Gate 4 — stability.** Two tests, because they fail differently. Split by
market regime and check the per-regime change in Sharpe (a hedge that only
helps in crises is a crisis hedge, and the reader deserves to know that).
And split into consecutive out-of-sample windows (a hedge that only works in
the first half of the sample has learned the sample).

---

## 3. The framework: Healy and Lo (2010)

> Healy, A. D. and Lo, A. W. (2010), "Jumping the Gates: Using Beta-Overlay
> Strategies to Hedge Liquidity Constraints", in *Hedge Funds*, Chapter 11,
> pp. 303–322. Princeton University Press.
> DOI [10.1515/9781400835812.303](https://doi.org/10.1515/9781400835812.303)
> · free full text: <https://web.mit.edu/Alo/www/Papers/gates.pdf>

This is the canonical reference for hedging overlays, and it is the source of
gate 1 and gate 3.

**Condition (B) — is there anything to hedge?** Verbatim from §2 of the
paper:

> "implementing a beta-hedging overlay can actually increase the overall risk
> to the investor while simultaneously reducing the expected return because of
> transactions costs and forgone potential risk premia"

and, on the threshold:

> "A very rough guideline for the minimum R² needed to implement an effective
> hedging-overlay strategy is 25%—any value lower than this threshold raises
> the possibility that the hedge will do more harm than good."

**Condition (A2) — is the risk reduction worth the price?** The paper lists
four conditions under which a rational investor would run a beta-hedging
overlay. (A2) is the one that maps onto gate 3:

> "(A2) The investor believes that the risk reduction from hedging the risk
> factors is worth the price of forgoing the normally positive expected
> returns of the risk factors to be hedged during the hedging period."

The full list is (A1) the hedged factors' expected returns are temporarily
negative; (A2) the risk reduction is worth the forgone return; (A3) the
investor already has significant exposure and wants no more; (A4) the hedged
factors are significantly correlated with the investor's total risk.

**Equation (6) — how much risk is left.** For a portfolio `R_b` with a
hedge `R_i`, the ratio of the hedged variance to the original variance is

```
Var[R_b + R_i] / Var[R_i] = 1 − R²
```

**Equation (7) — how much volatility reduction R² buys.** The percentage
reduction in volatility from a full overlay is

```
δ = 1 − √(1 − R²)
```

Their Table 1 tabulates it (read from the PDF, not from memory):

| R² | δ | | R² | δ | | R² | δ |
|---|---|---|---|---|---|---|---|
| 5% | 3% | | 40% | 23% | | 80% | 55% |
| 10% | 5% | | 50% | 29% | | 90% | 68% |
| 20% | 11% | | 60% | 37% | | 95% | 78% |
| 30% | 16% | | 70% | 45% | | | |

**§5 — the dial.** The paper also shows that applying the overlay
*selectively*, by market condition, reduces the performance drag. That is
precisely what the regime dial does here.

---

## 4. Sizing the hedge

Implemented in `src/policy/hedger.py`.

### 4.1 Beta, and why we shrink it toward zero

Beta is estimated by ordinary least squares of a holding's daily returns on
the benchmark's daily returns, over a trailing window that ends *before* the
decision date. A raw beta from 252 noisy observations is unreliable, so we
shrink it toward zero by a factor that depends on how statistically
convincing the estimate is:

```
w     = t² / (t² + k)        t = t-statistic of the beta estimate
β*    = w · β
```

This is a precision-weighted shrinkage: the weight is the signal-to-noise
ratio of the estimate. When the estimate is precise (large `t`), `w` is near 1
and we trust it. When it is noise (small `t`), `w` is near 0 and we hedge
nothing. The constant `k` lives in the YAML config (`hedging.shrinkage_k`,
default 60), not in the code.

**What the literature says, and where we deviate.** There are three
established procedures for correcting a noisy OLS beta, and they shrink
toward *different* things:

- **Blume (1971)** shrinks toward **one** — an implicit forecast that true
  betas regress toward the market.
- **Vasicek (1973)** shrinks toward the **cross-sectional mean** of betas,
  which is not one and not necessarily the market's.
- **Lally (1998)** examines both procedures and reaches two conclusions that
  bear directly on our choice:

  > "typical applications of Vasicek's method seem to mistakenly equate the
  > prior distribution with the cross-sectional distribution of estimated
  > rather than true betas"

  > "Blume's implicit forecast of any tendency for true betas to regress
  > towards one may not be desirable"

**We shrink toward zero, deliberately.** For a hedge, the conservative claim
is "this holding does not move with the market", and we only hedge what we can
defend. Lally's second point is the direct support: a forecast of regression
*toward one* is a forecast we are choosing not to make. A professional
reviewing this should read it as a policy choice made for a hedge, stated in
advance, not as an error.

> **Verification note.** We use the precision-weighted form above, and we cite
> the three papers above for the procedures they actually describe. We could
> **not** verify from a primary source the specific origin of the exact
> `t²/(t²+k)` weighting, so we describe the estimator on its own terms rather
> than attributing that particular algebraic form to a paper we cannot
> confirm. The estimator is a two-line function of `t` and `k` in
> `src/policy/hedger.py`; nothing else in the system depends on it.

### 4.2 The minimum-variance hedge ratio

Given portfolio returns `r_p` and hedge-instrument returns `r_h`, the hedge
in dollars per dollar of portfolio that minimises portfolio variance is

```
f* = −cov(r_p, r_h) / var(r_h)
```

**Derivation.** Portfolio variance with a hedge of `f` dollars per dollar of
portfolio is

```
Var(r_p + f·r_h) = Var(r_p) + 2·f·cov(r_p, r_h) + f²·Var(r_h)
```

Differentiate with respect to `f` and set to zero:

```
2·cov + 2·f·Var(r_h) = 0    ⇒    f* = −cov(r_p, r_h) / Var(r_h)
```

For a long-equity portfolio hedged with a market instrument the covariance
is positive, so `f*` is negative: short the hedge. Correct.

**This is not the same as "hedge to beta zero".** Beta-neutral means "the
portfolio should not move with the market". Minimum variance means "the
portfolio should be as calm as possible". They differ whenever the hedge
instrument has its own specific risk. Minimum variance is the statistically
optimal answer; beta-neutral is the one you can explain in one sentence. We
compute both and record both.

**Cross-check.** Because this is the one formula in the repository we derive
rather than import, it is cross-checked against an independent convex
solver: the same objective is posed to `cvxpy` and solved with Clarabel, OSQP
and SCS. All agree with the closed form to **4e-13**. The test harness was
itself wrong twice before it was right — the first version minimised the sum
of squares around zero instead of the variance of the demeaned series — which
is why the cross-check is in the test suite rather than in a comment.

### 4.3 The dial, and what these numbers are not

The optimal ratio is multiplied by the regime dial, so the desk does the
full optimal hedge in a stress regime and a fraction of it in a calm one.
**That is a policy choice, not a statistical result**, and it is labelled as
such in the code.

The numbers this seat produces — volatility reduction, reward-to-risk — are
**screening estimates, not forecasts**. They answer "is this hedge big
enough to be worth its cost, and is it in the right direction". They do not
answer "will this make money". That answer comes from the four gates, run on
realised, walk-forward, cost-inclusive data. The analytic estimate is the
hypothesis; the backtest is the test.

---

## 5. Look-ahead discipline

Non-negotiable, and the single easiest thing to get wrong in a backtest.

| Rule | Where it is enforced |
|---|---|
| A decision at the close of day *t* uses data **strictly before** *t* | `Backtester._cutoff_panel` — one chokepoint; every seat receives the cut-off panel and never filters by date itself |
| The fill happens at the close of **t+1** | the pending-order mechanism in `src/backtest.py`: an intent decided on *t* becomes a fill on *t+1* |
| `forward_compound(t)` is the compounded return over **t+1 … t+H**, never including *t* | `src/evaluation/metrics.py`, pinned by `tests/test_backtest.py` |
| No signal bar is shifted after the fact | signals are computed from the cut-off panel only |

**The forward-window arithmetic, stated so it can be checked.** Using log
returns so compounding is a sum:

```
rev[i] = Σ_{j ≥ i} log_r[j]                (a suffix sum)
fwd[i] = Σ_{j = i+1}^{i+H} log_r[j]
       = rev[i+1] − rev[i+H+1]
```

which in pandas is `rev.shift(-1) - rev.shift(-(H+1))`.

An earlier version of this function used `shift(-(H-1)) - 1` offsets, which
summed the wrong window and produced a forward series correlated at **−0.79**
with the direct computation — and, because the information gate was reading
it, reported the **wrong sign** of the information coefficient. The test
`tests/test_backtest.py::test_forward_compound_matches_direct_computation`
now pins it against a naive loop, because a sign flip in a forward window
looks exactly like a strategy that does not work.

---

## 6. The statistics, and where they come from

**Never hand-roll a statistic that a maintained library already ships.** A
reader who wants to check our arithmetic should be able to check it against
the library everyone else uses.

| Statistic | Library | Licence | Note |
|---|---|---|---|
| Deflated Sharpe, Probabilistic Sharpe, expected-max Sharpe | [`skfolio`](https://skfolio.org) | BSD-3 | `skfolio` computes kurtosis as the **raw** (non-excess) moment, which is what Bailey & López de Prado's formula requires. Several hand-rolled versions get this wrong and silently shift the DSR. |
| PBO via CSCV, purged walk-forward + embargo, effective number of trials, minimum track record length | [`purgedcv`](https://github.com/eslazarev/purged-cross-validation) | MIT | PBO wants its matrix shaped `(n_configs, n_obs)`. Passing the transpose does not raise — it silently computes the PBO of the transpose. Also: `min_track_record_length` returns `inf` when the observed Sharpe is at or below target, and a *higher* observed Sharpe needs a *shorter* record. |
| Newey–West HAC standard errors | [`statsmodels`](https://www.statsmodels.org) | BSD-3 | `OLS(..., cov_type="HAC")`, so the autocorrelation correction matches the reference exactly. |
| Spearman rank correlation, t-distribution | [`scipy`](https://scipy.org) | BSD-3 | |
| Covariance shrinkage | [`scikit-learn`](https://scikit-learn.org) `LedoitWolf` | BSD-3 | A raw sample covariance matrix over a few hundred days is badly conditioned. Shrinkage is the standard fix. |
| Convex-solver cross-check | [`cvxpy`](https://www.cvxpy.org) | Apache-2.0 | Used only in tests, to check our one hand-derived formula. |
| Market data (optional) | [`yfinance`](https://github.com/ranaroussi/yfinance) | Apache-2.0 | Optional. The default data source is the bundled synthetic fixture. |

### Conventions used throughout

- `periods_per_year` defaults to **252** trading days.
- `risk_free` arguments are **per period**, never annual. Mixing the two is
  the single most common silent error in this kind of code.
- Sharpe-style ratios are computed from the **arithmetic mean of excess
  returns**, never from CAGR. Dividing CAGR by volatility and calling the
  result a Sharpe ratio is a mislabelled statistic, and it is the single most
  common error in retail backtests. On the data this repository was first
  written against, the two differed by 0.596 versus 0.420.

---

## 7. What this repository does NOT claim

Carried forward from `notes/2026-10-24-verified-citations.md`, which contains
the full list with resolutions. This is the short version, and it is the part
that matters most.

**About the data.**
- **Survivorship bias is not controlled for, and cannot be, here.** The
  bundled fixture names a small set of tickers that all exist today and all
  worked. Nothing in this repository can estimate what the result would
  have been on a universe that included the failures — a delisting, a
  near-collapse, a holding that stopped being a good idea. Consequences,
  stated plainly:
  - The measured **R² = 0.585 is a property of this portfolio**, not a
    property of hedges in general. A different universe would give a
    different R², and therefore a different answer at gate 1.
  - The walk-forward windows are six slices of the **same** universe in
    time. There is no out-of-sample *portfolio* in this repository, only
    out-of-sample *time*. A strategy that fails out-of-sample in time can
    still be a survivor-only artefact.
  - The benchmark and the hedge instrument are both survivors by
    construction, so the market risk being hedged away is market risk
    measured on a survivor.
  This does **not** invalidate the system. It invalidates a
  **generalisation**, and those are different claims. What this repository
  provides is the apparatus to run the same gates on a different universe
  and see which way the answer moves; what it cannot provide is the answer
  for a universe it has never seen. The honest form of the question is
  always *"does this hedge work on this portfolio, measured this way,
  against which alternative?"*
- The bundled market data is a **synthetic test fixture**. It has regime
  structure, volatility clustering, stress windows with correlation spikes and
  fat tails, so the machinery is exercised honestly — but **no claim about
  real markets is made anywhere in this repository**. Any such claim must be
  run on real data and must say so.
- The trading rules audited at the start of this project were reproduced
  **locally from cached data**. The T-bill leg was a flat 2.55% annual
  placeholder, not a real T-bill series. That materially affects the
  comparison and is stated rather than dropped.

**About the statistics.**
- The Deflated Sharpe Ratio corrects the **selection bias in a single
  reported Sharpe ratio** — for non-normality, for the *number of trials*,
  and for sample length. It does **not** estimate a probability that your
  strategy is overfit, it is **not** the same object as White's Reality
  Check, Hansen's SPA or the Harvey–Liu–Zhu haircut, and it is not a
  frequentist p-value.
- PBO *estimates* the probability that the backtest-optimal configuration has
  non-positive out-of-sample performance, under CSCV assumptions. It does not
  "remove" overfitting.
- The **t > 3.0** hurdle from Harvey, Liu & Zhu (2016) is derived for the
  **cross-section of equity factor returns** — a very large multiple-testing
  family. It is a recommended threshold in that specific setting, **not a
  universal law**, and not a validated cutoff for a trend rule, a single
  strategy, or a gate applied to a handful of signals.
- Sharpe's CAPM paper is **1964** (*Journal of Finance* 19(3), 425–442), not
  1966, and it is an equilibrium derivation, not an empirically validated
  model.
- The β-shrinkage paper is Vasicek (1973), *Journal of Finance* 28(5),
  1233–1239, "A Note on Using Cross-Sectional Information in Bayesian
  Estimation of Security Betas". He shrinks toward the **cross-sectional
  mean** of betas — which is not 1 and not necessarily the market's.
- **"Brock, Lakonishok & LeBaron (1996), Support and Resistance Breaks" does
  not exist.** The support/resistance content is in the 1992 paper,
  DOI [10.1111/j.1540-6261.1992.tb04681.x](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x).

**About the gates.**
- The **25% R² threshold is a guideline**, in the authors' words. It is not a
  law, and it is not validated for this desk's specific portfolio.
- Gate 2's IC floor (0.02) and t-threshold (1.96) are **this repository's**
  choices. They are not borrowed from a paper, and they are not presented as
  if they were.
- The realised volatility reduction is compared against the R²-implied
  ceiling; **a ratio below 100% is normal**, because the desk hedges
  selectively rather than continuously. It is not a failure.

**About what this code does.**
- **No live trading.** The execution adapter is a paper broker that refuses
  live mode without an explicit environment flag. There is no broker
  integration in this repository.
- Nothing here is investment advice.

---

## 8. Where to look in the code

### The architecture boundary

Everything above the decision layer is deliberately boring, inspectable, and
free of model calls. **The only model call in the repository is the Judge
seat's verdict**, and the Judge is deterministic by default. When it is
backed by a language model, the model's entire output is one opinion —
approve or reject, a score in [−1, 1], and reasons. It never chooses a
hedge ratio, never sizes a position, never relaxes a risk limit, and never
decides whether the strategy worked. That last question belongs to the gate
stack, which is arithmetic.

The boundary is checkable, and it is worth checking:

| Boundary | Evidence |
|---|---|
| No model call outside the Judge | `src/policy/judge.py` is the only module in `src/` that mentions a chat endpoint or an API key |
| The default judge makes no model call | `src/backtest.py` and `src/desk.py` both construct `RuleBasedJudge` |
| The model's output is an opinion only | `LLMJudge._SYSTEM` asks for one JSON object: a verdict, a score and reasons |
| Hedge ratio and size are arithmetic | `src/policy/hedger.py` |
| Risk limits and the veto are not negotiable by a model | `src/policy/risk.py` — the only veto, the only signature |
| The strategy verdict is arithmetic | `src/evaluation/gates.py` — four gates, no model |

The reasoning: a language model is good at forming an opinion and bad at
being trusted with a number that compounds over a walk-forward. So it gets
the opinion, the opinion is aggregated over three runs by majority, and
everything that moves money is a formula you can check by hand.

### The map

| Topic | File |
|---|---|
| The four gates and their thresholds | `src/evaluation/gates.py` |
| The statistics and their library sources | `src/evaluation/metrics.py` |
| Beta, shrinkage, minimum-variance hedge ratio | `src/policy/hedger.py` |
| The Risk seat, the veto, the kill switch | `src/policy/risk.py` |
| The judge (and why booleans, never strings) | `src/policy/judge.py` |
| The append-only journal | `src/ledger/journal.py` |
| One trading day, end to end | `src/desk.py` |
| The walk-forward engine and the look-ahead chokepoint | `src/backtest.py` |
| The configuration surface | `src/config.py`, `examples/holdings.example.yaml` |
| The cross-validation tests | `tests/` |
| A short map for a newcomer | `GUIDE.md` |

---

## References

Every DOI below was resolved against `doi.org` content negotiation and
checked against the returned title, authors, venue and pages. Where a paper
has no resolvable DOI, that is stated rather than faked.

- Healy, A. D. and Lo, A. W. (2010), "Jumping the Gates: Using Beta-Overlay
  Strategies to Hedge Liquidity Constraints", in *Hedge Funds*, Ch. 11,
  pp. 303–322. Princeton University Press.
  [10.1515/9781400835812.303](https://doi.org/10.1515/9781400835812.303) ·
  [free PDF](https://web.mit.edu/Alo/www/Papers/gates.pdf)
- Healy, A. D. and Lo, A. W. (2013), *The Evolution of Mechanical Trading*,
  2nd ed. ISBN 978-0-9994654-0-6.
- Blume, M. (1971), "On the Assessment of Risk", *Journal of Finance* 26(1),
  1–10.
  [10.1111/j.1540-6261.1971.tb00584.x](https://doi.org/10.1111/j.1540-6261.1971.tb00584.x)
- Blume, M. (1975), "Betas and Their Regression Tendencies", *Journal of
  Finance* 30(3), 785–795.
  [10.1111/j.1540-6261.1975.tb01850.x](https://doi.org/10.1111/j.1540-6261.1975.tb01850.x)
- Lally, M. (1998), "An Examination of Blume and Vasicek Betas", *Financial
  Review* 33(3), 183–198.
  [10.1111/j.1540-6288.1998.tb01390.x](https://doi.org/10.1111/j.1540-6288.1998.tb01390.x)
- Vasicek, O. A. (1973), "A Note on Using Cross-Sectional Information in
  Bayesian Estimation of Security Betas", *Journal of Finance* 28(5),
  1233–1239.
  [10.1111/j.1540-6261.1973.tb01452.x](https://doi.org/10.1111/j.1540-6261.1973.tb01452.x)
- Ledoit, O. and Wolf, M. (2004), "A Well-Conditioned Estimator for
  Large-Dimensional Covariance Matrices", *Journal of Multivariate Analysis*
  88(2), 365–411.
  [10.1016/s0047-259x(03)00096-4](<https://doi.org/10.1016/s0047-259x(03)00096-4>)
- Ledoit, O. and Wolf, M. (2004), "Honey, I Shrunk the Sample Covariance
  Matrix", *Journal of Portfolio Management* 30(4), 110–119.
  [10.3905/jpm.2004.110](https://doi.org/10.3905/jpm.2004.110)
- Bailey, D. H. and López de Prado, M. (2014), "The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting, and Non-Normality",
  *Journal of Portfolio Management* 40(5), 94–107.
  [10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094)
- Bailey, D. H., Borwein, J., López de Prado, M. and Zhu, Q. (2014),
  "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest
  Overfitting on Out-of-Sample Performance", *Notices of the AMS* 61(5),
  458–471. [10.1090/noti1105](https://doi.org/10.1090/noti1105)
- Bailey, D. H., Borwein, J., López de Prado, M. and Zhu, Q. (2017), "The
  Probability of Backtest Overfitting", *Journal of Computational Finance*
  20(4), 39–69.
  [10.21314/jcf.2016.322](https://doi.org/10.21314/jcf.2016.322) ·
  earlier SSRN version:
  [10.2139/ssrn.2326253](https://doi.org/10.2139/ssrn.2326253)
- López de Prado, M. (2018), *Advances in Financial Machine Learning*,
  ISBN 978-1-119-48208-6. No DOI — the book is not DOI-deposited.
- Newey, W. K. and West, K. D. (1987), "A Simple, Positive Semi-Definite,
  Heteroskedasticity and Autocorrelation Consistent Covariance Matrix",
  *Econometrica* 55(3), 703–708.
  [10.2307/1913610](https://doi.org/10.2307/1913610)
- Sharpe, W. (1964), "Capital Asset Prices: A Theory of Market Equilibrium
  under Conditions of Risk", *Journal of Finance* 19(3), 425–442.
  [10.1111/j.1540-6261.1964.tb02865.x](https://doi.org/10.1111/j.1540-6261.1964.tb02865.x)
- Brock, W., Lakonishok, J. and LeBaron, B. (1992), "Simple Technical Trading
  Rules and the Stochastic Properties of Stock Returns", *Journal of Finance*
  47(5), 1731–1764.
  [10.1111/j.1540-6261.1992.tb04681.x](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x)
- Harvey, C. R., Liu, Y. and Zhu, H. (2016), "… and the Cross-Section of
  Expected Returns", *Review of Financial Studies* 29(1), 5–68.
  [10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059)

Full resolution notes, including the three phantom citations that were found
and removed, are in `notes/2026-10-24-verified-citations.md`.
