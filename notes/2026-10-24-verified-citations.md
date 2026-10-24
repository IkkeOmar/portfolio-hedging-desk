# Verified literature citations

**Status:** every DOI/URL below was machine-checked. "Verified" means the page was actually
fetched in this session and its bibliographic metadata was confirmed against the
registry (Crossref API + `doi.org` content negotiation), the publisher's own
table of contents, or the PDF text itself. Items I could **not** verify are
marked **NO** with the gap stated explicitly.

Verification date: 2026-10-24. Method: `api.crossref.org/works/<doi>`,
`https://doi.org/<doi>` with `Accept: application/vnd.citationstyles.csl+json`
(registry-level proof), publisher issue TOCs (AFA `afajof.org`, Wiley, Cambridge
Core, `pubsonline.informs.org`), and PDF text extraction for claim checking.

---

## Section A — Core literature

| # | Authors (year) | Title | Venue | DOI / URL | Verified? | One-line honest contribution |
|---|---|---|---|---|---|---|
| 1 | Sharpe, W. F. (**1964**, *not* 1966) | Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk | The Journal of Finance 19(3), 425–442 | [10.1111/j.1540-6261.1964.tb02865.x](https://doi.org/10.1111/j.1540-6261.1964.tb02865.x) | **YES** — Crossref + doi.org CN resolve; AFA TOC for v19(3) confirms pages 425–442 and author | Derives the equilibrium (CAPM) pricing relation from mean-variance optimality, giving the security market line and the β-based expected-return formula. |
| 2 | Markowitz, H. (1952) | Portfolio Selection | The Journal of Finance 7(1), 77–91 | [10.1111/j.1540-6261.1952.tb01525.x](https://doi.org/10.1111/j.1540-6261.1952.tb01525.x) | **YES** — Crossref + doi.org CN resolve | Introduces mean–variance portfolio theory: expected return and variance of a portfolio as weighted combinations of asset means/covariances, and the efficient frontier concept. |
| 3 | Faber, M. T. (2007) | A Quantitative Approach to Tactical Asset Allocation | The Journal of Wealth Management 9(4), 69–79 | [10.3905/jwm.2007.674809](https://doi.org/10.3905/jwm.2007.674809) · SSRN version: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461> | **YES** — Crossref + doi.org CN resolve; SSRN abstract page fetched; PDF fetched (mebfaber.com) and text-confirmed | Tests a simple monthly rule using a **10-month simple moving average** (the paper also discusses the 200-day MA as the most-cited long-term trend measure) and reports lower drawdown/volatility than buy-and-hold across several asset classes. |
| 4 | Brock, W., Lakonishok, J., & LeBaron, B. (1992) | Simple Technical Trading Rules and the Stochastic Properties of Stock Returns | The Journal of Finance 47(5), 1731–1764 | [10.1111/j.1540-6261.1992.tb04681.x](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x) | **YES** — Crossref + doi.org CN resolve | Applies moving-average and trading-range-break rules to DJIA data 1897–1986 and uses bootstrap-based tests to show several simple rules have statistically significant predictive power (i.e., reject the random-walk benchmark). |
| 5 | **NO MATCHING RECORD** — see note below | "Support and Resistance Breaks: Stock Price Futures and the Effectiveness of Technical Analysis" attributed to Brock, Lakonishok & LeBaron (1996) | Claimed: The Journal of Finance | **NO** — could not verify in any venue | **NO** | **GAP.** This title is not in the Journal of Finance. JF v51(1) (Mar 1996) TOC (publisher's own site) lists Andersen pp. 169–204 there; the complete Crossref/OpenAlex enumeration of all JF 1996 items (140 works) contains no Brock/Lakonishok/LeBaron article, and Crossref/OpenAlex title searches for the exact title return nothing. The support-and-resistance (trading-range-break) content the user wants **is already in item 4 (BLL 1992)**, which tests trading-range breaks explicitly. **Cite BLL 1992; do not cite a non-existent 1996 JF paper.** |
| 6 | Hurst, B., Ooi, Y. H., & Pedersen, L. H. (2017) | A Century of Evidence on Trend-Following Investing | The Journal of Portfolio Management 44(1), 15–29 | [10.3905/jpm.2017.44.1.015](https://doi.org/10.3905/jpm.2017.44.1.015) · SSRN: [10.2139/ssrn.2993026](https://doi.org/10.2139/ssrn.2993026) · AQR white-paper PDF (**mirror**, aqr.com's own PDF paths now 404): <https://jkgcapital.com/wp-content/uploads/2017/02/AQR-A-Century-of-Trend-Following-Investing.pdf> | **YES** — both DOIs resolve via Crossref + doi.org CN; SSRN landing page fetched (26 pp., posted 28 Jun 2017); AQR white-paper PDF fetched (16 pp., 4.59 MB, dated "Fall 2014") and text-confirmed. Note the PDF is the **AQR white-paper version (Fall 2014 update)**, not the 2017 JPM article | Studies trend-following across global markets since 1880 and reports strong positive returns with low correlation to traditional asset classes over more than a century, including diversification in equity bear markets. |
| 7 | Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012) | Time Series Momentum | Journal of Financial Economics 104(2), 228–250 | [10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003) | **YES** — Crossref + doi.org CN resolve | Documents that an asset's own past 12-month return predicts its next-month return across 58 liquid futures/forward instruments, with the effect roughly 4× stronger in extreme (high-vol) markets and consistent with time-series momentum. |
| 8 | Bailey, D. H., & López de Prado, M. (2014) | The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality | The Journal of Portfolio Management 40(5), 94–107 | [10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094) · SSRN: [10.2139/ssrn.2460551](https://doi.org/10.2139/ssrn.2460551) | **YES** — both DOIs resolve via Crossref + doi.org CN | Defines a probability that an observed Sharpe ratio exceeds a benchmark after correcting for (i) non-normal returns via skewness/kurtosis, (ii) the number of trials in the selection process, and (iii) the sample length; the DSR is the corresponding Sharpe-ratio threshold. |
| 9a | Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014) | Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance | Notices of the American Mathematical Society 61(5), 458–471 | [10.1090/noti1105](https://doi.org/10.1090/noti1105) | **YES** — Crossref + doi.org CN resolve; DOI redirects to a working AMS PDF (189 KB) which was downloaded | Uses CSCV (combinatorially symmetric cross-validation) to estimate the Probability of Backtest Overfitting, showing how much apparent in-sample edge evaporates out-of-sample when many strategy configurations are tried. |
| 9b | Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017) | The Probability of Backtest Overfitting | The Journal of Computational Finance 20(4), 39–69 | [10.21314/jcf.2016.322](https://doi.org/10.21314/jcf.2016.322) · earlier SSRN version: [10.2139/ssrn.2326253](https://doi.org/10.2139/ssrn.2326253) | **YES** — both DOIs resolve; doi.org redirects to the risk.net landing page, which I fetched and which states **Volume 20, Number 4 (April 2017), pages 39–69** | Formalizes the CSCV-based PBO estimator plus overfit-performance and stochastic-dominance statistics for comparing many candidate configurations on the same data. |
| 10 | López de Prado, M. (2018) | Advances in Financial Machine Learning | Wiley (book) | ISBN **978-1-119-48208-6** · Publisher page: <https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086> · Companion code: <https://github.com/BlackArbsCEO/Adv_Fin_ML_Exercises> | **YES (as ISBN + publisher URL)** — Wiley product page fetched (200, title "Advances in Financial Machine Learning \| Wiley"); companion exercises repo fetched (200). **NO DOI:** `10.1002/9781119482086` returns HTTP 404, and no `10.1002/9781119482…` variant resolves, so **cite by ISBN + Wiley URL, not by DOI** | Introduces purged k-fold cross-validation with an embargo to stop overlapping/forward-looking label information from leaking across folds in financial ML (Chapter 7). |
| 11 | White, H. (2000) | A Reality Check for Data Snooping | Econometrica 68(5), 1097–1126 | [10.1111/1468-0262.00152](https://doi.org/10.1111/1468-0262.00152) | **YES** — Crossref + doi.org CN resolve | Provides a bootstrap "reality check" test for whether the best of many candidate trading rules beats a benchmark, with the null being that no rule has superior predictive power. |
| 12 | Hansen, P. R. (2005) | A Test for Superior Predictive Ability | Journal of Business & Economic Statistics 23(4), 365–380 | [10.1198/073500105000000063](https://doi.org/10.1198/073500105000000063) | **YES** — Crossref + doi.org CN resolve | Proposes the studentized Superior Predictive Ability (SPA) test, which corrects for data snooping while remaining valid under non-stationarity and heteroskedasticity of estimated losses. |
| 13 | Harvey, C. R., Liu, Y., & Zhu, H. (2016) | … and the Cross-Section of Expected Returns | The Review of Financial Studies 29(1), 5–68 | [10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059) | **YES** — Crossref + doi.org CN resolve (Crossref's `issued` date is 2015-10-09 = online-first; the **journal issue is 2016, 29(1)** — cite 2016) | Argues that most published return factors fail to survive multiple-testing correction, and proposes a **new-factor t-statistic hurdle of ≈3.0** (rather than the traditional 2.0) to account for the number of factors tried. |
| 14a | Ledoit, O., & Wolf, M. (2004) | A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices | Journal of Multivariate Analysis 88(2), 365–411 | [10.1016/s0047-259x(03)00096-4](https://doi.org/10.1016/s0047-259x(03)00096-4) | **YES** — Crossref + doi.org CN resolve | Derives a shrinkage ("Ledoit–Wolf") estimator of the covariance matrix that is well-conditioned and consistent as the number of assets grows relative to sample size. |
| 14b | Ledoit, O., & Wolf, M. (**2004**; working-paper version 2003) | Honey, I Shrunk the Sample Covariance Matrix | The Journal of Portfolio Management 30(4), 110–119 | [10.3905/jpm.2004.110](https://doi.org/10.3905/jpm.2004.110) · 2003 working paper: [10.2139/ssrn.433840](https://doi.org/10.2139/ssrn.433840) | **YES** — both DOIs resolve. Note the user's stated "2003" is the SSRN working paper; the **journal article is 2004, JPM 30(4)** | Gives an intuitive, practically usable shrinkage covariance estimator that beats the sample covariance matrix when the asset count is large relative to the number of observations. |
| 15 | Vasicek, O. A. (1973) | **A Note on Using Cross-Sectional Information in Bayesian Estimation of Security Betas** (verified substitute — see note) | The Journal of Finance 28(5), 1233–1239 | [10.1111/j.1540-6261.1973.tb01452.x](https://doi.org/10.1111/j.1540-6261.1973.tb01452.x) · RePEc landing: <https://ideas.repec.org/a/bla/jfinan/v28y1973i5p1233-39.html> | **YES** — Crossref + doi.org CN resolve; AFA TOC for JF v28(5) confirms Vasicek at pp. 1233–1239; RePEc page fetched. **The title you gave ("Portfolio Selection with a Minimum Variance Constraint", JFQA 1973) could not be verified — see Section C.** | Shows that shrinking each stock's estimated β toward the **cross-sectional mean** β (a Bayesian/James–Stein-style shrinkage of betas) produces more efficient β estimates — the canonical citation for a shrunk hedge ratio. |
| 16 | Michaud, R. O. (1989) | **The Markowitz Optimization Enigma: Is 'Optimized' Optimal?** (verified substitute) | Financial Analysts Journal 45(1), 31–42 | [10.2469/faj.v45.n1.31](https://doi.org/10.2469/faj.v45.n1.31) · CFA Institute landing: <https://rpc.cfainstitute.org/research/financial-analysts-journal/1989/the-markowitz-optimization-enigma-is-optimized-optimal> | **YES** — Crossref + doi.org CN resolve; CFA Institute landing page fetched (Jan 1989, FAJ 45(1)); also cited as `[Mic89]` in Boyd et al., *Markowitz Portfolio Construction at Seventy* | Documents that unconstrained mean–variance optimization tends to **maximize the effect of estimation error** in expected returns and covariances, producing poor out-of-sample performance. |
| 17 | Litterman, R. B., & Scheinkman, J. (1991) | Common Factors Affecting Bond Returns | The Journal of Fixed Income 1(1), 54–61 | [10.3905/jfi.1991.692347](https://doi.org/10.3905/jfi.1991.692347) | **YES** — Crossref + doi.org CN resolve (Crossref `issued` 1991-06-30; vol 1, issue 1, pp. 54–61) | Identifies two common factors driving bond returns — changes in the **level** and **slope** of the yield curve — explaining most of the variation in bond returns over time. |
| 18a | Spearman, C. (1904) | The Proof and Measurement of Association between Two Things | The American Journal of Psychology 15(1), 72–101 | [10.2307/1412159](https://doi.org/10.2307/1412159) | **YES** — Crossref + doi.org CN resolve (JSTOR stable ID) | Introduces the rank correlation coefficient ρ (Spearman's rho), defined as the Pearson correlation of the ranks of two variables. |
| 18b | Kendall, M. G. (1938) | A New Measure of Rank Correlation | Biometrika 30(1–2), 81–93 | [10.1093/biomet/30.1-2.81](https://doi.org/10.1093/biomet/30.1-2.81) · JSTOR: [10.2307/2332226](https://doi.org/10.2307/2332226) | **YES** — both DOIs resolve. Also verified: the tie-handling companion, Kendall (1945), *The Treatment of Ties in Ranking Problems*, Biometrika 33(3), 239–251, [10.1093/biomet/33.3.239](https://doi.org/10.1093/biomet/33.3.239) | Introduces Kendall's τ as a concordance-based rank correlation coefficient (counting concordant minus discordant pairs), an alternative to Spearman's ρ that is interpretable as a probability of correct pairwise ordering. |
| 18c | Newey, W. K., & West, K. D. (1987) | A Simple, Positive Semi-definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix | Econometrica 55(3), 703–708 | [10.2307/1913610](https://doi.org/10.2307/1913610) · NBER working-paper PDF (verified, 191 KB): [10.3386/t0055](https://doi.org/10.3386/t0055) | **YES** — both DOIs resolve; the NBER DOI redirects to a working PDF I downloaded | Proposes the Bartlett-kernel HAC ("sandwich") covariance estimator that is consistent under both heteroskedasticity and autocorrelation of unknown form. |
| 19 | Politis, D. N., & Romano, J. P. (1994) | The Stationary Bootstrap | Journal of the American Statistical Association 89(428), 1303–1313 | [10.1080/01621459.1994.10476870](https://doi.org/10.1080/01621459.1994.10476870) | **YES** — Crossref + doi.org CN resolve | Gives the stationary bootstrap, a resampling scheme that preserves local dependence and is the practical ingredient for implementing White's Reality Check and Hansen's SPA test on serially dependent data. |

### The hedging framework (added 2026-10-24 — verified separately)

This entry was added after the first pass of this file was written, because
the citation agent had not seen it. It was verified against the primary
source, not recalled.

| Authors (year) | Title | Venue | DOI / URL | Verified? | One-line honest contribution |
|---|---|---|---|---|---|
| Healy, A. D., & Lo, A. W. (**2010**) | Jumping the Gates: Using Beta-Overlay Strategies to Hedge Liquidity Constraints | In *Hedge Funds*, Ch. 11, pp. 303–322, Princeton University Press | [10.1515/9781400835812.303](https://doi.org/10.1515/9781400835812.303) · free PDF: <https://web.mit.edu/Alo/www/Papers/gates.pdf> | **YES** — resolved via doi.org content negotiation AND `api.crossref.org` (type: book-chapter, container *Hedge Funds*, pages 303–322, issued 2010-12-31). **Crossref lists no chapter authors**, so authorship was confirmed from the MIT-hosted PDF's title page: *Alexander D. Healy and Andrew W. Lo*. Both quotes below were matched verbatim against the PDF text (whitespace-normalised). | Provides the beta-overlay framework this repository's gates 1 and 3 are built on: condition (B) on the minimum R² needed for an overlay to be worth running, condition (A2) on accepting the forgone risk premium, equation (6) on residual variance, and equation (7) on the volatility reduction an R² implies. |

**Verbatim quotes used in `docs/METHODOLOGY.md`, matched against the PDF:**

- *"implementing a beta-hedging overlay can actually increase the overall risk
  to the investor while simultaneously reducing the expected return because of
  transactions costs and forgone potential risk premia"*
- *"A very rough guideline for the minimum R² needed to implement an effective
  hedging-overlay strategy is 25%—any value lower than this threshold raises
  the possibility that the hedge will do more harm than good."*
- *"(A2) The investor believes that the risk reduction from hedging the risk
  factors is worth the price of forgoing the normally positive expected
  returns of the risk factors to be hedged during the hedging period."*

**Equation (7) table, read from the paper's Table 1** (R² → volatility
reduction δ): 5%→3%, 10%→5%, 20%→11%, 30%→16%, 40%→23%, 50%→29%, 60%→37%,
70%→45%, 80%→55%, 90%→68%, 95%→78%.

**Correction made during this verification.** An earlier draft of this
project cited Table 1 as "R² 25%→δ 13%, 50%→29%, 75%→50%". The paper's actual
table is the one above. The 25% threshold and equation (7) itself were
correct; only the tabulated values were wrong.

**Also corrected in the same pass:** the Ledoit & Wolf well-conditioned
estimator is **JMVA 88(2), 365–411 (2004), DOI
`10.1016/s0047-259x(03)00096-4`**. The DOI
`10.1016/j.jmva.2003.10.005`, which appeared in an earlier version of this
file, resolves to Boshnakov (2005), *"On the asymptotic properties of
multivariate sample autocovariances"* — a different paper entirely.

### Supporting references (verified, for implementation)

| Ref | Use | DOI / URL | Verified? |
|---|---|---|---|
| Efron, B., & Tibshirani, R. J. (1993), *An Introduction to the Bootstrap* | Standard textbook for the resampling machinery used by White (2000) / Hansen (2005) | [10.1007/978-1-4899-4541-9](https://doi.org/10.1007/978-1-4899-4541-9) (also [10.1201/9780429246593](https://doi.org/10.1201/9780429246593)) | **YES** — both resolve |
| Michaud, R. O., & Michaud, R. O. (2008), *Efficient Asset Management* (OUP) + chapter "The Resampled Efficient Frontier", pp. 42–59 | Canonical home of the resampled-efficiency (bootstrap) portfolio-selection method | Book: [10.1093/oso/9780195331912.001.0001](https://doi.org/10.1093/oso/9780195331912.001.0001) · Chapter: [10.1093/oso/9780195331912.003.0006](https://doi.org/10.1093/oso/9780195331912.003.0006) · Intro SSRN: [10.2139/ssrn.2405555](https://doi.org/10.2139/ssrn.2405555) | **YES** — all three resolve |
| `statsmodels.stats.sandwich_covariance.cov_hac` | Python implementation of Newey–West HAC SEs (numpy/scipy stack) | <https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html> | **YES** — page fetched (200) |
| `scipy.stats.spearmanr` / `scipy.stats.kendalltau` | Python implementations of the two rank correlations | <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html> · <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html> | **YES** — both fetched (200) |
| `arch` package docs (`bootstrap/bootstrap.html`) | Python stationary/block bootstrap for the RC/SPA resampling step | <https://arch.readthedocs.io/en/latest/bootstrap/bootstrap.html> · PyPI: <https://pypi.org/project/arch/> | **YES** — index fetched (200, links to `bootstrap/bootstrap.html`); PyPI fetched (200). Note: the old `.../bootstrap.html` and `.../api/arch.bootstrap.html` URLs now 404 |
| CRAN package `pbo` | Reference implementation of the CSCV / PBO procedure (R, not Python) | <https://cran.r-project.org/web/packages/pbo/index.html> | **YES** — page fetched (200; v1.3.5, published 2022-05-26) |
| Aparicio, D., & López de Prado, M. (2018), "How hard is it to pick the right model? MCS and backtest overfitting", *Algorithmic Finance* 7(1–2), 53–61 | Practical Model Confidence Set / data-snooping companion paper | [10.3233/af-180231](https://doi.org/10.3233/af-180231) | **YES** — resolves |
| Bailey, D. H., & López de Prado, M. (2021), "How 'Backtest Overfitting' in Finance Leads to False Discoveries", *Significance* 18(6), 22–25 | Short, readable companion to the AMS Notices article | [10.1111/1740-9713.01588](https://doi.org/10.1111/1740-9713.01588) | **YES** — resolves |

---

## Section B — Answers to your specific questions

**Item 17 (hedge ratio as regression beta with shrinkage).** The canonical citation is
**Vasicek (1973), "A Note on Using Cross-Sectional Information in Bayesian Estimation of
Security Betas," JF 28(5), 1233–1239, DOI 10.1111/j.1540-6261.1973.tb01452.x** — verified
above. Vasicek shrinks each stock's OLS β toward the cross-sectional mean β; this is exactly
the "James–Stein-like shrinkage of hedge ratios" you wanted. For the *minimum-variance*
framing, pair it with Ledoit–Wolf (item 14) on covariance shrinkage and Michaud (item 16)
on estimation error. **Litterman & Scheinkman (item 17 in your list) is about bond-return
factors (level/slope), not about hedge-ratio shrinkage** — cite it only for the factor
claim, not for shrinkage.

**Item 18 (Kendall's τ vs Spearman ρ + Newey–West).** Fully covered by items 18a–18c above.
Spearman (1904) for ρ, Kendall (1938) for τ (plus Kendall 1945 for ties), Newey & West (1987)
for HAC SEs — all three verified with resolvable DOIs. Python: `scipy.stats.spearmanr`,
`scipy.stats.kendalltau`, `statsmodels...cov_hac`.

**Item 19 (reality check / bootstrap multiple-comparison correction).** **Yes — items 11 and
12 are sufficient as the statistical references.** White (2000) is the nonparametric Reality
Check; Hansen (2005) is the studentized SPA test, which is the one to prefer because it is
more powerful and robust to non-stationarity. Add **Politis & Romano (1994)** (item 19 above)
because both tests require a bootstrap that respects serial dependence — cite it so the
resampling scheme is defensible. For a small number of strategies, White's RC and Hansen's
SPA are straightforward to implement directly from the papers in numpy/scipy, using the
stationary bootstrap from Politis & Romano for the resampling step; `arch` provides a
ready-made stationary/block bootstrap. If you want a *reference implementation* of the
PBO/CSCV part specifically, the CRAN package `pbo` is the canonical one (R, not Python).
**Do not** claim that White's RC or Hansen's SPA "correct for multiple testing" in the
Harvey–Liu–Zhu t-statistic sense — they are different devices (see below).

---

## Section C — Three gaps: stated citations that could NOT be verified

These are the items where **your list named a specific paper that does not appear to
exist as described**. I verified each of them by enumerating the complete journal
year from the registry (not a keyword search), by reading the publisher's own issue
table of contents, and by sweeping the DOI namespace the publisher uses.

| Your item | What you asked for | What I found | What to cite instead |
|---|---|---|---|
| **5** | Brock, Lakonishok & LeBaron (1996), "Support and Resistance Breaks: Stock Price Futures and the Effectiveness of Technical Analysis", *Journal of Finance* | **Does not exist.** JF v51(1) (Mar 1996) TOC read from the publisher's own site (`afajof.org`) lists Andersen at pp. 169–204 — not a Brock paper. Full enumeration of JF 1996 via Crossref (112 items) and OpenAlex (140 works) contains **no** Brock/Lakonishok/LeBaron article. Crossref and OpenAlex exact-title searches return nothing. | **BLL (1992), JF 47(5)** — item 4 above. It is the paper that actually tests trading-range-break (support/resistance) rules, and it is a real, DOI-resolvable article. |
| **15** | Vasicek (1973), "Portfolio Selection with a Minimum Variance Constraint", *Journal of Financial and Quantitative Analysis* | **Not found.** JFQA's 1973 volume 8 deposit (85 items via Crossref ISSN-level enumeration, plus the Cambridge/JSTOR issue listings for v8 issues 3, 4 and 5) contains no such title. JSTOR ID sweeps across the v8 ID space and Cambridge DOI sweeps across the `10.1017/S0022109000…` range did not surface it. The real Vasicek 1973 paper is a *different* one, in a *different* journal (JF). | **Vasicek (1973), "A Note on Using Cross-Sectional Information in Bayesian Estimation of Security Betas", JF 28(5), 1233–1239** — item 15 above, DOI verified. This is also the *better* citation for your stated purpose (β shrinkage): it shrinks betas toward the cross-sectional mean. |
| **16** | Michaud (1989), "The Markowitz Portfolio Optimization Problem: A Nonsmooth Optimization Perspective", *Operations Research*; or the 1998 "Resampled Efficiency" working paper | The *nonsmooth* title could not be found in OR: the DOI you might infer (`10.1287/opre.37.5.753`, where the numeric suffix encodes the first page) **404s**, and a sweep of every `10.1287/opre.37.5.{680…865}` DOI shows that pp. 753–763 of that issue are occupied by *A Fast and Simple Algorithm for the Maximum Flow Problem* (748–759) and *An Exact Algorithm for the Quadratic Assignment Problem on a Tree* (760–768). The 1998 "Resampled Efficiency" item likewise has no DOI in Crossref (IMFI's 1998 deposit is empty). | **Michaud (1989), "The Markowitz Optimization Enigma: Is 'Optimized' Optimal?", FAJ 45(1), 31–42** (item 16) for the estimation-error argument; **Michaud & Michaud (2008), *Efficient Asset Management*** and its chapter "The Resampled Efficient Frontier" (supporting-refs table) for resampled efficiency; **Michaud (2014), "An Introduction to Resampled Efficiency", SSRN 2405555** as the closest thing to the 1998 working paper you wanted. |

**Bottom line for the repo:** of the DOI/URL pairs listed as citations in this file,
**36 DOIs resolve and their metadata was confirmed against the registry** (re-checked
in a final pass after the file was written). The only two that do not resolve
(`10.1002/9781119482086` for the AFML book and `10.1287/opre.37.5.753` for the Michaud
OR article) are **documented in place as non-resolving, with working alternatives
given** — do not let either leak into a citation. The remaining entries are stable
non-DOI URLs (Wiley product page, GitHub repo, RePEc landing pages, package docs),
each fetched successfully in this session.

---

## Section D — Claims you should NOT make

**Brock, Lakonishok & LeBaron**
- ❌ Do **not** cite a 1996 *Journal of Finance* paper titled "Support and Resistance Breaks:
  Stock Price Futures and the Effectiveness of Technical Analysis." It does not appear in
  JF v51(1) (whose TOC I read from the publisher), in the full Crossref/OpenAlex enumeration
  of JF 1996, or in any title search. Cite **BLL (1992), JF 47(5)** — it is the paper that
  actually tests trading-range-break (support/resistance) rules on DJIA data.
- ❌ Do not say BLL 1992 "proves" technical analysis works, or that the bootstrap result
  implies profit. BLL show statistically significant predictive power of several rules
  relative to a random-walk benchmark on DJIA data; they explicitly note transaction costs
  are not modelled and recommend using futures data, and they caution about the
  data-snooping/multiple-comparison issue across their 26 rules. Their own later work and
  the Sullivan–Timmermann–White (1999) replication with a reality check are the appropriate
  follow-up citations for cost/data-snooping caveats.
- ❌ Do not generalise BLL's DJIA-sample result to any asset class, sample period, or
  post-publication period without saying so.

**Faber (2007)**
- ❌ Do not say Faber "proves" the 200-day/10-month MA rule is profitable. The paper reports
  historical backtest results for a *simple, mechanical, price-based* rule across a small set
  of asset classes and explicitly frames the goal as improving **risk-adjusted** returns and
  drawdown, not maximizing raw return.
- ❌ Do not describe Faber's rule as "the 200-day moving average" without qualification: the
  paper's own example and headline rule use a **10-month SMA** on monthly data (it also
  discusses the 200-day MA as the most-cited long-term measure). State which one you implement.
- ❌ Do not claim the paper includes transaction costs, live trading, or out-of-sample
  validation unless you re-check; it is a backtest study, and the later 2018 "Revisited
  10 Years Later" JPM article ([10.3905/jpm.2018.44.2.156](https://doi.org/10.3905/jpm.2018.44.2.156),
  verified) is the better source if you want the update.

**Deflated Sharpe Ratio (Bailey & López de Prado 2014)**
- ❌ Do not say the DSR "corrects for backtest overfitting" in the same sense as the PBO/CSCV
  paper. The DSR corrects the **selection-bias problem in a single reported Sharpe ratio**
  for non-normality, the *number of trials* (via an expected-maximum Sharpe statistic), and
  sample length; it does **not** estimate a probability that your specific strategy is
  overfit, and it does not perform out-of-sample validation.
- ❌ Do not claim DSR corrects for "multiple testing" without qualification — it adjusts for
  the *number of trials* via an expected maximum Sharpe ratio under a specified number of
  trials; it is not the same object as White's Reality Check, Hansen's SPA, or Harvey–Liu–Zhu's
  factor-haircut.
- ❌ Do not present a DSR threshold as a guarantee or as a frequentist p-value.

**PBO / AMS Notices (Bailey et al.)**
- ❌ Do not say PBO "removes" overfitting — it *estimates* the probability that the
  backtest-optimal configuration has non-positive out-of-sample performance, under CSCV
  assumptions (and it inherits the assumptions of the base data and the partition scheme).
- ❌ Do not cite the Notices AMS and the JCF paper as if they were two independent
  confirmations — they are the same research line by the same authors; the Notices piece
  is the expository version (2014) and the JCF paper (2017) the fuller treatment.

**Harvey, Liu & Zhu (2016)**
- ❌ **Do not present the t > 3.0 hurdle as a universal law.** It is derived for the
  **cross-section of equity factor returns** (a very large multiple-testing family of
  long-short equity factors), and is a *recommended* threshold for new factors in that
  specific setting. It is not a validated cutoff for trend rules, for a single strategy, for
  non-equity assets, or for a gate applied to a handful of signals.
- ❌ Do not cite "… and the Cross-Section of Expected Returns" as though the title were
  "and the Cross-Section of Expected Returns" — the published title begins with an ellipsis
  because it continues Sharpe (1964): "… and the Cross-Section of Expected Returns".
- ❌ Do not say their multiple-testing haircut "proves" that factor strategies don't work;
  they argue most published factors fail to replicate after correcting for the number tested.

**Sharpe (1964)**
- ❌ Do not cite "Sharpe (1966)" for this article. The JF article is **1964**, JF 19(3),
  425–442. There is no 1966 JF reprint of it (I checked JF v21(3)'s publisher TOC).
  (1966 is the year of a *book* by Sharpe on the same theory — not this paper.)
- ❌ Do not describe the CAPM as an empirically validated model; it is an equilibrium
  derivation whose empirical implementation (the *proxy* for expected return, e.g. the
  risk-free asset) is a separate, heavily contested question.

**Vasicek / hedge-ratio shrinkage**
- ❌ Do not cite Vasicek (1973) as a *Journal of Financial and Quantitative Analysis* paper
  titled "Portfolio Selection with a Minimum Variance Constraint." I could not locate that
  title in JFQA's 1973 v8 issues (Crossref ISSN-level enumeration of all 85 JFQA 1973 items,
  plus the Cambridge/JSTOR issue listings). The verified 1973 Vasicek paper is the JF beta
  note (item 15), which is the one that actually supports β shrinkage. (See Section C.)
- ❌ Do not say Vasicek "shrinks betas toward 1" or "toward the market." He shrinks toward
  the **cross-sectional mean** of the betas, which is not 1 and not necessarily the market's.

**Michaud**
- ❌ Do not cite "The Markowitz Portfolio Optimization Problem: A Nonsmooth Optimization
  Perspective" as *Operations Research* 37(5), 753–763 with DOI 10.1287/opre.37.5.753 —
  that DOI does not resolve (HTTP 404), and a page-by-page sweep of every `10.1287/opre.37.5.*`
  DOI (680–865, which encodes the starting page) shows pages 753–763 in that issue are
  occupied by *A Fast and Simple Algorithm for the Maximum Flow Problem* (748–759) and *An
  Exact Algorithm for the Quadratic Assignment Problem on a Tree* (760–768). The verified
  1989 Michaud paper is the **FAJ** one (item 16). Use the book/chapter (item 16 supporting
  refs) for resampled efficiency.
- ❌ Do not say "resampled efficiency" is a *bootstrap over the parameter estimates* only —
  it is a Monte-Carlo simulation of the sampling distribution of the optimal portfolio,
  used to select portfolios that are statistically equivalent rather than the single
  error-maximizing optimizer.

**Litterman & Scheinkman (1991)**
- ❌ Do not cite it for hedge-ratio shrinkage or for "regression beta" methodology. It is a
  bond-return factor paper (level/slope of the yield curve).
- ❌ Do not describe it as identifying a "term-premium model" with a single risk premium; its
  contribution is the empirical finding that level and slope shocks explain most common
  variation in bond returns.

**Kendall's τ vs Spearman's ρ**
- ❌ Do not imply τ is "better" than ρ without saying why — τ is a concordance probability
  and is more interpretable and more robust to heavy tails/monotone nonlinearities; ρ is the
  Pearson correlation of ranks and is more efficient under bivariate normality.
- ❌ Do not cite Kendall (1935) "The Problem of m Methods" as if you had verified it: I could
  not confirm that exact 1935 Biometrika record (Crossref's Biometrika volume-22 deposit
  contains only 3 items for v22). The verified, citable rank-correlation primaries are
  Spearman (1904) and Kendall (1938), plus Kendall (1945) for ties.

**Newey–West (1987)**
- ❌ Do not say HAC SEs fix autocorrelation generally — they are consistent under
  heteroskedasticity and autocorrelation of unknown form, **provided the bandwidth/lag
  truncation is adequate**; state your lag choice and note the estimator is not
  nuisance-parameter-free in finite samples.
- ❌ Do not cite "Newey & West (1987)" for a specific default lag; the paper does not
  prescribe one for your data.

**White (2000) / Hansen (2005)**
- ❌ Do not say either "proves" a strategy works; they test the null of no superior
  predictive ability, and failure to reject is not evidence of edge.
- ❌ Do not describe White's Reality Check as "a Bonferroni correction" — it is a
  bootstrap max-statistic test over the whole set of models, and it can have very low power
  when many poor models are included.
- ❌ Do not describe Hansen's SPA as "just White's test with studentization" without noting
  its variance-reduction (the studentized/detrended terms), which is the practical reason
  to prefer it.

**Faber / general**
- ❌ Do not cite a **DOI for AFML that does not resolve** (`10.1002/9781119482086` → 404).
  Cite ISBN 978-1-119-48208-6 + the Wiley product URL.
- ❌ Do not attribute the purged k-fold/embargo scheme to a journal article — it comes from
  the AFML book (Chapter 7) and should be cited as such.
