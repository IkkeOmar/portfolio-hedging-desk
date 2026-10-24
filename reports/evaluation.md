# Evaluation report

**Verdict: FAIL**

> Short-circuited at gate regime_information. Later gates were not evaluated, on purpose: a strategy that fails an earlier gate does not need to be tested on the later ones.

## Headline numbers

| Quantity | Value |
|---|---|
| n_days | 3915 |
| n_trades | 121 |
| n_proposals | 172 |
| n_vetoes | 51 |
| n_seat_errors | 0 |
| n_signal_errors | 0 |
| r_squared | 0.5850 |
| hedged_cagr | 0.0649 |
| unhedged_cagr | 0.0638 |
| hedged_sharpe | 0.3782 |
| unhedged_sharpe | 0.3705 |
| hedged_annualised_vol | 0.2470 |
| unhedged_annualised_vol | 0.2539 |
| hedged_max_drawdown | -0.4715 |
| unhedged_max_drawdown | -0.6203 |
| total_cost | 557.0272 |
| trials_declared | 1 |

## The four gates

### Gate hedgeability — PASS

*R^2 58.5%*

| Metric | Value |
|---|---|
| r_squared | 0.5850 |
| threshold | 0.2500 |
| implied_max_vol_reduction_pct | 35.5798 |
| source | Healy and Lo (2010), condition (B) and equation (7) |

- R^2 = 58.5% clears the 25% threshold, so SPY explains enough of the portfolio's variance to be worth hedging.

### Gate regime_information — FAIL

*vol IC 0.0394, HAC t 0.51*

| Metric | Value |
|---|---|
| n_obs | 171 |
| ic_dial_vs_forward_vol | 0.0394 |
| ic_threshold | 0.0200 |
| hac_tstat | 0.5118 |
| tstat_threshold | 1.9600 |
| expected_sign | positive |

- HAC t-statistic is 0.51, below 1.96; we cannot rule out that this is noise.

## What the Risk seat refused

The Risk seat is the only seat that can approve an order, and it declines more often than it approves. A desk that never vetoes is not managing risk, it is trading.

| Date | Stage | Reason |
|---|---|---|
| 2013-06-25 | gross_cap | gross hedge 101.2% exceeds cap 100.0% |
| 2013-09-20 | gross_cap | gross hedge 104.1% exceeds cap 100.0% |
| 2015-03-04 | gross_cap | gross hedge 103.3% exceeds cap 100.0% |
| 2015-04-02 | gross_cap | gross hedge 103.4% exceeds cap 100.0% |
| 2015-05-01 | gross_cap | gross hedge 101.5% exceeds cap 100.0% |
| 2015-06-01 | gross_cap | gross hedge 103.9% exceeds cap 100.0% |
| 2015-06-30 | gross_cap | gross hedge 104.6% exceeds cap 100.0% |
| 2015-07-29 | gross_cap | gross hedge 106.6% exceeds cap 100.0% |
| 2015-08-27 | gross_cap | gross hedge 104.7% exceeds cap 100.0% |
| 2016-06-16 | gross_cap | gross hedge 110.0% exceeds cap 100.0% |
| 2016-07-15 | gross_cap | gross hedge 106.8% exceeds cap 100.0% |
| 2016-08-15 | gross_cap | gross hedge 105.8% exceeds cap 100.0% |
| 2016-09-13 | gross_cap | gross hedge 106.3% exceeds cap 100.0% |
| 2017-06-05 | gross_cap | gross hedge 103.3% exceeds cap 100.0% |
| 2017-07-04 | gross_cap | gross hedge 105.9% exceeds cap 100.0% |
| 2017-08-02 | gross_cap | gross hedge 104.7% exceeds cap 100.0% |
| 2017-08-31 | gross_cap | gross hedge 102.7% exceeds cap 100.0% |
| 2017-09-29 | gross_cap | gross hedge 108.0% exceeds cap 100.0% |
| 2017-10-30 | gross_cap | gross hedge 110.0% exceeds cap 100.0% |
| 2017-11-28 | gross_cap | gross hedge 111.1% exceeds cap 100.0% |
| 2017-12-27 | gross_cap | gross hedge 107.1% exceeds cap 100.0% |
| 2018-01-25 | gross_cap | gross hedge 106.5% exceeds cap 100.0% |
| 2020-05-27 | gross_cap | gross hedge 102.3% exceeds cap 100.0% |
| 2020-06-25 | gross_cap | gross hedge 101.3% exceeds cap 100.0% |
| 2022-07-29 | gross_cap | gross hedge 103.7% exceeds cap 100.0% |
| 2022-08-29 | gross_cap | gross hedge 102.4% exceeds cap 100.0% |
| 2022-09-27 | gross_cap | gross hedge 101.4% exceeds cap 100.0% |
| 2024-03-08 | gross_cap | gross hedge 110.9% exceeds cap 100.0% |
| 2024-04-08 | gross_cap | gross hedge 114.5% exceeds cap 100.0% |
| 2024-05-07 | gross_cap | gross hedge 113.5% exceeds cap 100.0% |
| 2024-06-05 | gross_cap | gross hedge 109.6% exceeds cap 100.0% |
| 2024-07-04 | gross_cap | gross hedge 106.9% exceeds cap 100.0% |
| 2024-08-02 | gross_cap | gross hedge 110.1% exceeds cap 100.0% |
| 2024-09-02 | gross_cap | gross hedge 111.5% exceeds cap 100.0% |
| 2024-10-01 | gross_cap | gross hedge 111.2% exceeds cap 100.0% |
| 2024-10-30 | gross_cap | gross hedge 112.9% exceeds cap 100.0% |
| 2024-11-28 | gross_cap | gross hedge 116.1% exceeds cap 100.0% |
| 2024-12-27 | gross_cap | gross hedge 120.0% exceeds cap 100.0% |
| 2025-01-27 | gross_cap | gross hedge 123.5% exceeds cap 100.0% |
| 2025-02-25 | gross_cap | gross hedge 121.6% exceeds cap 100.0% |
| 2025-03-26 | gross_cap | gross hedge 123.0% exceeds cap 100.0% |
| 2025-04-24 | gross_cap | gross hedge 124.4% exceeds cap 100.0% |
| 2025-05-23 | gross_cap | gross hedge 123.2% exceeds cap 100.0% |
| 2025-06-23 | gross_cap | gross hedge 120.7% exceeds cap 100.0% |
| 2025-07-22 | gross_cap | gross hedge 126.6% exceeds cap 100.0% |
| 2025-08-20 | gross_cap | gross hedge 128.3% exceeds cap 100.0% |
| 2025-09-18 | gross_cap | gross hedge 125.5% exceeds cap 100.0% |
| 2025-10-17 | gross_cap | gross hedge 123.4% exceeds cap 100.0% |
| 2025-11-17 | gross_cap | gross hedge 106.4% exceeds cap 100.0% |
| 2025-12-16 | gross_cap | gross hedge 100.1% exceeds cap 100.0% |
| 2026-10-06 | gross_cap | gross hedge 107.9% exceeds cap 100.0% |

## Trades

| Date | Symbol | Side | Notional | Cost |
|---|---|---|---|---|
| 2013-01-01 | SPY | sell | 7,490 | 2.62 |
| 2013-01-30 | SPY | sell | 4,548 | 1.59 |
| 2013-02-28 | SPY | sell | 6,698 | 2.34 |
| 2013-03-29 | SPY | sell | 5,589 | 1.96 |
| 2013-04-29 | SPY | sell | 5,668 | 1.98 |
| 2013-05-28 | SPY | sell | 7,730 | 2.71 |
| 2013-07-25 | SPY | sell | 5,718 | 2.00 |
| 2013-08-23 | SPY | sell | 8,295 | 2.90 |
| 2013-10-22 | SPY | sell | 3,779 | 1.32 |
| 2013-11-20 | SPY | sell | 5,489 | 1.92 |
| 2013-12-19 | SPY | sell | 5,832 | 2.04 |
| 2014-01-17 | SPY | sell | 5,488 | 1.92 |
| 2014-02-17 | SPY | sell | 7,228 | 2.53 |
| 2014-03-18 | SPY | sell | 5,658 | 1.98 |
| 2014-04-16 | SPY | sell | 5,890 | 2.06 |
| 2014-05-15 | SPY | sell | 6,361 | 2.23 |
| 2014-06-13 | SPY | sell | 6,696 | 2.34 |
| 2014-07-14 | SPY | sell | 6,264 | 2.19 |
| 2014-08-12 | SPY | sell | 5,480 | 1.92 |
| 2014-09-10 | SPY | sell | 5,195 | 1.82 |
| 2014-10-09 | SPY | sell | 5,779 | 2.02 |
| 2014-11-07 | SPY | sell | 5,362 | 1.88 |
| 2014-12-08 | SPY | sell | 5,703 | 2.00 |
| 2015-01-06 | SPY | sell | 6,586 | 2.30 |
| 2015-02-04 | SPY | sell | 10,650 | 3.73 |
| 2015-09-28 | SPY | sell | 6,087 | 2.13 |
| 2015-10-27 | SPY | sell | 10,079 | 3.53 |
| 2015-11-25 | SPY | sell | 8,276 | 2.90 |
| 2015-12-24 | SPY | sell | 7,289 | 2.55 |
| 2016-01-22 | SPY | sell | 6,524 | 2.28 |
| 2016-02-22 | SPY | sell | 6,717 | 2.35 |
| 2016-03-22 | SPY | sell | 7,138 | 2.50 |
| 2016-04-20 | SPY | sell | 7,298 | 2.55 |
| 2016-05-19 | SPY | sell | 16,710 | 5.85 |
| 2016-10-13 | SPY | sell | 7,006 | 2.45 |
| 2016-11-11 | SPY | sell | 10,943 | 3.83 |
| 2016-12-12 | SPY | sell | 10,009 | 3.50 |
| 2017-01-10 | SPY | sell | 12,283 | 4.30 |
| 2017-02-08 | SPY | sell | 10,088 | 3.53 |
| 2017-03-09 | SPY | sell | 10,450 | 3.66 |
| 2017-04-07 | SPY | sell | 12,726 | 4.45 |
| 2017-05-08 | SPY | sell | 16,124 | 5.64 |
| 2018-02-26 | SPY | sell | 4,986 | 1.75 |
| 2018-03-27 | SPY | sell | 8,456 | 2.96 |
| 2018-04-25 | SPY | sell | 7,263 | 2.54 |
| 2018-05-24 | SPY | sell | 8,535 | 2.99 |
| 2018-06-22 | SPY | sell | 9,709 | 3.40 |
| 2018-07-23 | SPY | sell | 13,379 | 4.68 |
| 2018-08-21 | SPY | sell | 14,799 | 5.18 |
| 2018-09-19 | SPY | sell | 13,982 | 4.89 |
| 2018-10-18 | SPY | sell | 14,426 | 5.05 |
| 2018-11-16 | SPY | sell | 11,478 | 4.02 |
| 2018-12-17 | SPY | sell | 13,660 | 4.78 |
| 2019-01-15 | SPY | sell | 13,324 | 4.66 |
| 2019-02-13 | SPY | sell | 15,566 | 5.45 |
| 2019-03-14 | SPY | sell | 15,592 | 5.46 |
| 2019-04-12 | SPY | sell | 13,920 | 4.87 |
| 2019-05-13 | SPY | sell | 13,595 | 4.76 |
| 2019-06-11 | SPY | sell | 13,801 | 4.83 |
| 2019-07-10 | SPY | sell | 8,072 | 2.83 |
| 2019-08-08 | SPY | sell | 8,918 | 3.12 |
| 2019-09-06 | SPY | sell | 8,244 | 2.89 |
| 2019-10-07 | SPY | sell | 17,894 | 6.26 |
| 2019-11-05 | SPY | sell | 5,945 | 2.08 |
| 2019-12-04 | SPY | sell | 11,804 | 4.13 |
| 2020-01-02 | SPY | sell | 11,133 | 3.90 |
| 2020-01-31 | SPY | sell | 12,140 | 4.25 |
| 2020-03-02 | SPY | sell | 12,243 | 4.29 |
| 2020-03-31 | SPY | sell | 11,678 | 4.09 |
| 2020-04-29 | SPY | sell | 16,662 | 5.83 |
| 2020-07-27 | SPY | sell | 10,006 | 3.50 |
| 2020-08-25 | SPY | sell | 13,411 | 4.69 |
| 2020-09-23 | SPY | sell | 11,138 | 3.90 |
| 2020-10-22 | SPY | sell | 15,160 | 5.31 |
| 2020-11-20 | SPY | sell | 9,861 | 3.45 |
| 2020-12-21 | SPY | sell | 10,629 | 3.72 |
| 2021-01-19 | SPY | sell | 21,119 | 7.39 |
| 2021-02-17 | SPY | sell | 16,519 | 5.78 |
| 2021-03-18 | SPY | sell | 15,170 | 5.31 |
| 2021-04-16 | SPY | sell | 17,088 | 5.98 |
| 2021-05-17 | SPY | sell | 17,904 | 6.27 |
| 2021-06-15 | SPY | sell | 21,781 | 7.62 |
| 2021-07-14 | SPY | sell | 19,431 | 6.80 |
| 2021-08-12 | SPY | sell | 24,442 | 8.55 |
| 2021-09-10 | SPY | sell | 19,434 | 6.80 |
| 2021-10-11 | SPY | sell | 23,017 | 8.06 |
| 2021-11-09 | SPY | sell | 21,173 | 7.41 |
| 2021-12-08 | SPY | sell | 17,045 | 5.97 |
| 2022-01-06 | SPY | sell | 22,453 | 7.86 |
| 2022-02-04 | SPY | sell | 10,583 | 3.70 |
| 2022-03-07 | SPY | sell | 16,881 | 5.91 |
| 2022-04-05 | SPY | sell | 11,028 | 3.86 |
| 2022-05-04 | SPY | sell | 14,417 | 5.05 |
| 2022-06-02 | SPY | sell | 12,261 | 4.29 |
| 2022-07-01 | SPY | sell | 27,065 | 9.47 |
| 2022-10-27 | SPY | sell | 21,571 | 7.55 |
| 2022-11-25 | SPY | sell | 21,271 | 7.44 |
| 2022-12-26 | SPY | sell | 22,848 | 8.00 |
| 2023-01-24 | SPY | sell | 19,118 | 6.69 |
| 2023-02-22 | SPY | sell | 23,087 | 8.08 |
| 2023-03-23 | SPY | sell | 16,371 | 5.73 |
| 2023-04-21 | SPY | sell | 24,639 | 8.62 |
| 2023-05-22 | SPY | sell | 20,646 | 7.23 |
| 2023-06-20 | SPY | sell | 22,285 | 7.80 |
| 2023-07-19 | SPY | sell | 16,799 | 5.88 |
| 2023-08-17 | SPY | sell | 18,259 | 6.39 |
| 2023-09-15 | SPY | sell | 21,256 | 7.44 |
| 2023-10-16 | SPY | sell | 24,363 | 8.53 |
| 2023-11-14 | SPY | sell | 22,270 | 7.79 |
| 2023-12-13 | SPY | sell | 22,283 | 7.80 |
| 2024-01-11 | SPY | sell | 19,386 | 6.79 |
| 2024-02-09 | SPY | sell | 38,655 | 13.53 |
| 2026-01-15 | SPY | sell | 7,858 | 2.75 |
| 2026-02-13 | SPY | sell | 18,385 | 6.43 |
| 2026-03-16 | SPY | sell | 17,959 | 6.29 |
| 2026-04-14 | SPY | sell | 16,724 | 5.85 |
| 2026-05-13 | SPY | sell | 14,719 | 5.15 |
| 2026-06-11 | SPY | sell | 15,922 | 5.57 |
| 2026-07-10 | SPY | sell | 13,386 | 4.68 |
| 2026-08-10 | SPY | sell | 13,690 | 4.79 |
| 2026-09-08 | SPY | sell | 26,614 | 9.31 |

## How to read this

This is a HEDGING desk, so read the gates in the hedging sense, not the trading sense.

- **A hedge is a trade in risk, not a trade in profit.** Its job is to reduce the dispersion of outcomes. A hedge that does not lower volatility is a cost with no benefit.
- **Gate 1 (hedgeability, R^2) is the first gate and the most important.** If the hedge instrument explains less than 25% of the portfolio's variance, no overlay can be worth its cost. This threshold is Healy and Lo (2010), condition (B).
- **Gate 2 asks about volatility, not returns.** The dial is supposed to anticipate future volatility. A return-correlation gate would be structurally wrong: a perfect hedge has zero forward-return correlation by construction, so it would reject the best possible hedge.
- **A Sharpe ratio here is the real one:** mean excess return over standard deviation, annualised. It is not CAGR divided by volatility. Those differ, and the difference is the whole point of checking.
- **Every backtest in this repo charges the configured transaction costs on every trade.**
- **The walk-forward windows are consecutive out-of-sample slices.** A strategy that only works in one of them has learned the sample.
- **The gates short-circuit on purpose.** A hedge that fails gate 1 does not need to be tested on gate 3, and pretending otherwise manufactures evidence.
- **This data is synthetic.** It is a test fixture for the machinery, not evidence about real markets. No claim about real markets is made anywhere in this repository.
