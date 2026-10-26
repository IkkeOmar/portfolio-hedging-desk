# portfolio-hedging-desk

A small, self-hosted **portfolio hedging desk**. You name your holdings, it
decides how much market risk to neutralise, it writes down every decision
before it knows the outcome, and exactly one seat is allowed to say no.

It is free, it runs on your machine, it needs no API keys and no broker
account, and it ships with its own traps documented: the bugs that were in
this code, why each one produced a plausible-looking wrong answer, and how
they were caught. See [`notes/KNOWN-TRAPS.md`](notes/KNOWN-TRAPS.md).

---

## Read this before you go further

Four things, up front, so nothing later surprises you.

1. **The data that ships with this repo is synthetic.** It is a test fixture
   with market-like structure (regimes, volatility clustering, stress
   windows, fat tails). It exists so you can run the machinery offline and
   watch it behave. **It is not evidence about real markets, and this repo
   makes no claim about real markets.** Point it at real data and it will
   tell you what it finds, including if the answer is "nothing".
2. **There is no live trading.** The execution layer is a paper broker. It
   refuses to trade live unless you explicitly set an environment flag that
   this repository never sets for you.
3. **The bundled backtest fails one of its own gates.** That is the honest
   result and we did not tune it away. Section "The honest result" below
   shows exactly which gate, and why failing it is the correct behaviour.
4. **This is not investment advice.** It is a piece of auditable engineering
   that happens to be about finance.

---

## What this is

You own some stocks. Some of your risk comes from the whole market moving
up or down, and some of it comes from that one company. This tool works out
the first part, decides whether reducing it is worth the cost, and refuses to
act when it is not.

That is the whole idea. The rest is the machinery that makes the decision
falsifiable: you can read every decision it made, you can re-run it, and you
can change any part of it without learning a new framework.

## What this repo is

Five seats around a table, and one rule: **only the Risk seat can approve an
order, and nothing trades without its signature.**

```
        price data
             |
             v
     +---------------+     decides how much of your risk is market risk
     |  Scan seat    |     and which part is company-specific
     +---------------+
             |
             v
     +---------------+     reads the trailing window, estimates betas,
     |  Quant seat   |     sets the regime dial
     +---------------+
             |
             v
     +---------------+     sizes the hedge: minimum-variance ratio,
     |  Hedger seat  |     shrunk betas, scaled by the dial
     +---------------+
             |
             v
     +---------------+     three opinions, then a majority
     |  Judge seat   |
     +---------------+
             |
             v
     +---------------+     the only signature that matters
     |  Risk seat    |     ------> VETO
     +---------------+
             |
             v
      paper broker  ->  append-only journal
```

**Everything above the decision layer is deliberately boring, inspectable,
and free of model calls.** The only model call in the entire repository is
the Judge seat's verdict, and the Judge is **deterministic by default**. When
it is backed by a language model, the model's entire output is one opinion:
approve or reject, a score, and reasons. It never chooses a hedge ratio,
never sizes a position, never relaxes a risk limit, and never decides
whether the strategy worked. That last question belongs to the gate stack,
which is arithmetic. A model is good at forming an opinion and bad at being
trusted with a number that compounds, so it gets the opinion and nothing
else.

**The journal.** Every decision, proposal, verdict, order intent and fill is
written to a JSONL file as it happens, before the outcome is known. If the
desk is wrong, you can read exactly what it thought and why. This is the
part that separates a system from a story about a system.

**The veto.** The Risk seat enforces hard limits (gross hedge size, risk per
leg, minimum reward-to-risk, maximum number of legs) and it has the final
word. In the bundled backtest it refuses **51 of 172 proposals, a 29.7%
veto rate**. A desk that never says no is not managing risk, it is trading.

**The kill switch.** A sentinel file on disk. Touch it and the desk stops.
It survives a crash, a reboot, and a human who needs it stopped right now.

## Quick start

No API key. No network. No broker account. Three commands:

```bash
git clone https://github.com/IkkeOmar/portfolio-hedging-desk.git
cd portfolio-hedging-desk
pip install -r requirements.txt

python scripts/run_desk.py      # one trading day, five seats, a journal
python scripts/backtest.py      # 15 years, walk-forward, the four gates
python -m pytest tests/ -q      # 115 tests
```

**New here?** [`GUIDE.md`](GUIDE.md) is the map: the architecture in one
paragraph, the five seats, and eight things to try, each one changing
something you can see. [`examples/holdings.csv.example.yaml`](examples/holdings.csv.example.yaml)
is the same configuration pointed at your own price file instead of the
bundled fixture.

`scripts/run_desk.py` prints something like this:

```
=== desk run 2026-10-16 (information cutoff 2026-10-15) ===
  quant : regime=defensive vol=16.07% pct=0.48 trend=below dial=0.74
  scan  : MSFT w=27.8% beta=0.65 hedgeable=90%, NVDA w=26.7% beta=1.02 hedgeable=0%
  hedger: SPY -31,637 vol +25.51% rrr=10.63
  judge : approve (3/3 approvals)
  fill  : sell 128.21 SPY @ 246.75 cost 11.07
```

Read that line by line. `hedgeable=90%` for MSFT means that 90% of MSFT's
contribution to your portfolio risk moves with the market, so it is worth
hedging. `hedgeable=0%` for NVDA means the opposite: **none** of NVDA's risk
contribution is market risk. It is all company-specific, and a market hedge
against it would cost money and remove nothing. That distinction is the
entire reason the Scan seat exists.

`scripts/backtest.py` writes `reports/evaluation.json` and `reports/evaluation.md`.

## The dashboard

There is a local web dashboard, if you would rather look at the desk than
read its output. It shows the same report the CLI writes. It does not
compute anything of its own.

```bash
pip install -r requirements-dashboard.txt
streamlit run dashboard/app.py
```

**Run it from the repository root.** Streamlit reads `.streamlit/config.toml`
from the current working directory, so the theme is silently ignored if you
launch it from anywhere else. The URL is printed in the terminal
(`http://localhost:8501`).

**The Streamlit version matters, and here is why.** The dashboard needs
Streamlit **1.55.0** or newer, and that floor is measured rather than
guessed. Streamlit's `width` parameter arrived in three different releases
for the three widgets this app uses (`st.button` and `st.dataframe` in
1.49.0, `st.plotly_chart` in 1.51.0), and the theme key
`metricValueFontSize` is only accepted from 1.55.0. On an older Streamlit
the widget calls raise `TypeError` and the config parser rejects keys it
does not recognise.

You do not have to care, though. `dashboard/compat.py` inspects the
Streamlit you actually have, at runtime, and uses the modern spelling when
it is available and the older one when it is not. So on an older
Streamlit you get the app, not a crash. The floor still matters, because
that is the version CI tests against: a CI job that installs `latest`
cannot catch a floor that is too low, since the newest Streamlit accepts
everything.

Six tabs:

| Tab | What is in it |
|---|---|
| **Overview** | The verdict banner, the four headline numbers against the unhedged portfolio, the equity curve, and all four gates, including the two that never ran, marked *not reached* |
| **Risk** | The equity curve on a log scale, the underwater drawdown plot, and the dial over time |
| **Desk** | One trading day replayed seat by seat, with the judge's votes |
| **Vetoes & trades** | Every refusal with its reason, and what the hedging cost |
| **Walk-forward** | Sharpe by out-of-sample window |
| **Settings** | Where the API key goes, and what it is used for |

### The API key, and what it is for

**You do not need one.** The dashboard, the desk, the backtest and the
gates all run with no key, no network and no broker account. The default
Judge seat is deterministic: three identical votes, aggregated by majority.

A key is only needed if you want to swap in an LLM-backed judge on the
**Desk** tab and watch a model's opinion differ from the rule-based one.
You can set it in the sidebar, or write it into `.env` yourself:

```bash
DEEPSEEK_API_KEY=sk-...
```

`.env` is in `.gitignore`, so it cannot be committed by accident. The
dashboard never renders a key, never writes one into the evaluation
report, and never puts one in the journal.

**What a key buys you is exactly one thing: the Judge's opinion.** The
other four seats are arithmetic. The hedge ratio, the position size and
the risk limits are never chosen by a model, and whether the strategy
worked is decided by the gates, which are arithmetic too.

### The dashboard is tested like a product

Two layers, because one cannot cover the other:

- `tests/test_dashboard.py` drives the app with Streamlit's own harness
  and *interacts with it*: clicks the buttons, flips the switches,
  changes the trading day, types a key, and checks that the key never
  reaches the rendered page.
- `tests/test_dashboard_browser.py` starts a real Streamlit server and
  drives it with a real browser: it clicks every tab, every switch, the
  provider dropdown and the connection-test button.

Streamlit's harness cannot click a tab. A tab is a container, not a
widget, so tab navigation is only testable in a browser. Both layers run
in CI.

## The honest result

The bundled synthetic market, 3915 days, 121 trades, 172 proposals, 51
vetoes, 1 strategy variant tried.

**Gate 1, hedgeability: PASS.** The R² of the hedging equation (how much of
your portfolio's variance the market explains) is **0.585**, against a 25%
floor. Healy and Lo (2010) call 25% "a very rough guideline" for the
minimum R² needed for an overlay to be worth running. We clear it.

**Gate 2, regime information: FAIL.** The dial is supposed to anticipate
future volatility. Its rank correlation with forward realised volatility is
0.0394, which passes the 0.02 floor and has the right sign. But the
Newey-West HAC t-statistic is **0.51**, and we need 1.96 to rule out noise.
**We cannot rule out that the dial is guessing.**

The gate stack stops there, on purpose. A hedge that fails the information
gate does not need to be tested on the compensation gate, and pretending
otherwise manufactures evidence.

Here is the rest of the numbers, so you can see the whole picture rather
than the flattering part:

| | Hedged | Unhedged |
|---|---|---|
| CAGR | +6.49% | +6.38% |
| Sharpe ratio | 0.378 | 0.370 |
| Annualised volatility | 24.70% | 25.39% |
| Max drawdown | **-47.15%** | **-62.03%** |

The drawdown improved by 15 points and the volatility came down, and the
Sharpe ratio moved by 0.008. The R² says a *full* hedge could deliver a 35.6%
volatility reduction. We realised **2.73 points** of volatility against that
35.6-point ceiling, about 8% of the theoretical maximum, because the desk
hedges selectively and only when its own limits allow. Costs are charged on
every side: 557.03 in total.

**Read those two statements together.** The risk reduction is real and
measurable. The timing of it is not yet distinguishable from noise. A repo
that showed you only the first half would be a sales pitch; a repo that
showed you only the second half would be hiding a working system. Here is
both.

The walk-forward windows, consecutive out-of-sample slices of the same
sample: Sharpe **+0.465, +0.637, +0.048, +0.716, +0.403, -0.034**. Five of
six positive, and the negative one is in the final window. A result that only
works in the first half of the sample has learned the sample.

## How to make it yours

**Change your portfolio.** One file:
[`examples/holdings.example.yaml`](examples/holdings.example.yaml). Change
the tickers and share counts and run it. The config is validated loudly: a
misspelled key raises an error naming the key and the file, because silent
defaults in a risk system are a bug, not a convenience.

**Change the hedge instrument.** One line, same file. It defaults to `SPY`.
Pick something with different risk characteristics and the numbers will move.

**Change the risk limits.** `max_gross_hedge_pct`, `risk_per_trade_pct`,
`min_reward_to_risk`, `max_legs`. The Risk seat enforces them and nothing
else may relax them.

**Change the judge.** `src/policy/judge.py` has a deterministic rule-based
judge, which is the default so the repo needs no API key. Swap in an LLM
judge if you want one, and keep the three-vote majority: one sample of a
noisy opinion is not evidence.

**Change the broker.** `src/execution/paper.py` charges fee, slippage and
spread per side and settles on the next close. Replace it with your own
adapter and the rest of the desk does not change, because the only thing an
adapter is ever allowed to execute is a signed `OrderIntent`.

**Change the gates.** `src/evaluation/gates.py`. The thresholds are named
constants at the top of the file. If you disagree with 25%, change it there
and say so in a commit message.

To add a seat, a data source or a metric, see
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Limitations

Everything below is a real limitation, not a disclaimer paragraph.

- **The data is synthetic.** It exercises the machinery honestly. It says
  nothing about real markets, and the numbers above are properties of the
  fixture, not of the strategy.
- **Survivorship bias, stated plainly.** The bundled fixture names four
  tickers that all exist today and all worked. Nothing in this repository
  can tell you what the result looks like on a universe that included the
  failures: a delisting, a near-collapse, a business that stopped being a
  good idea. So R² 58.5% is a fact about **this portfolio**, not about
  hedges in general, and the gates would be re-run on the same survivors and
  would look just as good.
  This does not invalidate the system: it invalidates a *generalisation*,
  and the two are different claims. The apparatus here is what lets you
  test a different universe and see the answer move. The honest version of
  the question is never "does hedging work?" but "does this hedge work on
  this portfolio, measured this way, against which alternative?" See
  [`GUIDE.md`](GUIDE.md) §5.
- **One portfolio, one seed, one market.** The gates have been run on a
  single synthetic fixture. There is no out-of-sample *portfolio* here, only
  out-of-sample *time*. The walk-forward windows are six slices of the same
  universe.
- **Gate 2 fails.** The timing signal is not distinguishable from noise at
  the sample size and horizon we ran. Until it passes, this is a system that
  reduces risk on average and cannot yet say when.
- **One strategy variant was tried.** `--trials 1`. That number is declared
  in the report and it is the number that matters: a Sharpe ratio without a
  trial count is the best of N, not a result. If you sweep parameters, raise
  it and watch the number move.
- **The R² threshold is a guideline**, in the authors' words. It is not
  validated for any particular portfolio, including this one.
- **The gate thresholds for volatility information (0.02 and 1.96) are
  ours.** They are not borrowed from a paper and are not presented as if they
  were.
- **The beta shrinkage is a deliberate deviation.** Textbook beta estimators
  shrink toward one (Blume) or toward the cross-sectional mean (Vasicek). We
  shrink toward **zero**, because for a hedge the conservative claim is "this
  holding does not move with the market". Lally (1998) examines both
  alternatives and notes that Blume's forecast of regression toward one "may
  not be desirable". See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §4.1.
- **The judge is deterministic by default.** Three identical votes is
  agreement, not consensus. It is the default so the repo runs offline.
- **No live trading, no broker integration, no tax modelling.** Costs are
  modelled as basis points per side. Real costs are worse and vary.
- **Position sizing is not modelled.** The backtest assumes the portfolio
  weights you give it, and does not size you.

## How to check our work

The point of publishing the numbers is that you can check them.

- Every figure in this README comes from `reports/evaluation.json`, produced
  by `python scripts/backtest.py`. Re-run it and compare.
- **115 tests** (78 run on the base install; 37 more need the optional
  dashboard extra and skip without it), each cross-validated against an
  *independent* library or
  solver rather than a second implementation of our own code: Deflated
  Sharpe against `skfolio`, probability of backtest overfitting against
  `purgedcv`, Newey-West t-statistics against `statsmodels`, covariance
  shrinkage against `scikit-learn`, and the one formula we derive ourselves
  (the minimum-variance hedge ratio) against `cvxpy` with three different
  solvers.
- The look-ahead rules are pinned by tests, not by comments. A decision on
  day *t* uses only data strictly before *t*, and no fill is ever priced
  from before its own decision. (The backtest fills the previous day's
  intent at today's close; the live desk decides on day *t* using data
  strictly before *t* and fills at the close of *t*. Both satisfy the same
  rule, and the broker refuses a fill dated before its intent.)
- Every DOI in the methodology resolves and matches the paper it is cited
  for. We checked all 15 programmatically. **Four of them were wrong when
  first written from memory** (three did not resolve, and one resolved to an
  entirely different paper in the same journal), and all four were replaced.
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) has the derivations, the
  thresholds, the citations, and an explicit list of claims this project
  does **not** make.
- **A script checks our claims against a live run**, and it runs in CI on
  every push:

  ```
  python scripts/audit_claims.py   # every number in these docs vs a live desk run
  ```

  It re-runs the desk, checks every documented figure against the output,
  and checks every referenced path against the filesystem. A number that
  drifts out of the documentation fails the build instead of shipping.
- **The mistakes are published too**, in
  [`notes/KNOWN-TRAPS.md`](notes/KNOWN-TRAPS.md): every defect that was in
  this code, each with its mechanism, why the wrong answer looked
  plausible, and how it was caught. The mistakes are the credibility: a
  system that cannot show its work has no business auditing anyone else's.

## Further reading

- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md): how the desk decides, and how
  we know whether it is right.
- [`notes/KNOWN-TRAPS.md`](notes/KNOWN-TRAPS.md): the bugs that were in this
  code, and how each one was caught.
- [`notes/2026-10-24-verified-citations.md`](notes/2026-10-24-verified-citations.md)
  Every citation, resolved, with the ones we found that do not exist.

---

## The other half of this project

This repository is the **risk side** of a two-part project: is there
anything to hedge, does the timing signal exist, did the reduction pay for
itself, and does it hold up out of sample?

The **research side** lives in
[`hedging-agent`](https://github.com/IkkeOmar/hedging-agent-public): it drafts
candidate hedge strategies, searches for the best of many, and refuses to
promote any of them that does not clear a fail-closed gate. Right now it
rejects every universe it tests, and it publishes which checks failed.

Together they answer the two questions a hedging claim needs: *is there
something to hedge* (this repo) and *did we find a strategy that actually
works* (the other one).

## Where to take this next

This is a **starting point**, not a finished product. The desk is finished
as an *instrument*: five seats, a journal, one veto, four gates. And it
is not finished as a research programme. There is one data source, one
universe, and one family of thresholds. The seams are real, and each one
is a place to change the code:

| Seam | Where | What you would do |
|---|---|---|
| **The seat protocol** | `src/desk.py` | Add a seat, or replace one. The protocol is: propose, then a single Risk signature, or nothing trades. |
| **The gate thresholds** | `src/evaluation/gates.py` | Change what counts as a hedge worth holding. Every threshold is a measured quantity, not a round number. |
| **The data source** | `src/data/` | Point it at your own prices. `src/data/csv_source.py` reads a CSV; `src/data/synthetic.py` makes the fixture. |
| **The benchmark set** | `src/evaluation/metrics.py` | Add the simple alternative your strategy has to beat. |

What you may **not** do with it: turn it into a signal generator, weaken a
gate threshold to make something pass, or present any number here as
advice about what to hold. The output is a research result, not a
position.

## Licence

MIT. See [`LICENSE`](LICENSE).

Built by the [TextToQuant](https://texttoquant.com) team.

The bundled synthetic market data is generated by this repository's own code
and is covered by the same licence.
