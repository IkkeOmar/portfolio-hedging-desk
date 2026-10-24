# Guide — start here

This repository is a **portfolio hedging desk** you can run, read, break and
extend. It takes a portfolio of holdings, decides how much of a market index
to short against it, refuses the trades that are not worth their costs, and
then tells you honestly whether the result means anything.

It is a research and learning project. It does not trade for real, and it
ships a synthetic market so that everything runs offline with no API key, no
network and no broker account.

If you only read one other file, read
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md). If you want to change
something, read [`CONTRIBUTING.md`](CONTRIBUTING.md). This page is the map.

---

## The architecture, in one paragraph

Everything above the decision layer is deliberately boring, inspectable, and
free of model calls. **The only model call in the entire repository is the
Judge seat's verdict, and the Judge is deterministic by default.** When it
is backed by a language model, the model's entire output is one opinion:
approve or reject, a score between −1 and 1, and reasons. It never chooses a
hedge ratio, never sizes a position, never relaxes a risk limit, and never
decides whether the strategy worked. That last question belongs to the gate
stack, which is arithmetic.

The evidence, so you do not have to take it on trust:

| Claim | Where to check it |
|---|---|
| The Judge is the only thing that can call a model | `src/policy/judge.py` is the only file in `src/` that mentions a chat endpoint or an API key |
| The default judge is deterministic | `src/backtest.py` and `src/desk.py` both construct `RuleBasedJudge`, not `LLMJudge` |
| The model's output is an opinion | `LLMJudge._SYSTEM` asks for one JSON object: a verdict, a score and reasons |
| The hedge ratio and size are not the model's | `src/policy/hedger.py` — the Hedger seat, pure arithmetic |
| The risk limits are not the model's | `src/policy/risk.py` — the Risk seat, the only veto and the only signature |
| Whether the strategy worked is arithmetic | `src/evaluation/gates.py` — four gates, no model |

This split is the point of the project. A language model is good at forming
an opinion and bad at being trusted with a number that compounds. So it gets
the opinion, and everything that matters is a formula you can check.

---

## Five minutes

```bash
git clone https://github.com/IkkeOmar/portfolio-hedging-desk.git
cd portfolio-hedging-desk
python -m pip install -r requirements.txt

python scripts/run_desk.py --config examples/holdings.example.yaml --journal journal
python scripts/backtest.py --config examples/holdings.example.yaml --journal journal-backtest --out reports
python -m pytest tests/ -q
```

**What you should see.**

- The desk runs one trading day: five seats, a proposal, a judge verdict, a
  Risk signature, a fill, and a journal written to disk.
- The backtest prints a walk-forward run over **3915 days** with **121
  trades**, **172 proposals** and **51 vetoes**, and writes
  `reports/evaluation.json` and `reports/evaluation.md`.
- The tests print **54 passed**.

**The result you will not like.** Gate 1 passes (R² 58.5% against a 25%
threshold, implying at most a 35.6% volatility reduction). Gate 2 **fails**:
the timing signal's Newey-West HAC t-statistic is 0.51, well under the 1.96
needed to rule out noise. The gate stack short-circuits there, which is the
correct behaviour. A hedge that reduces risk on average but cannot say
*when* is a hedge with an honest label on it.

The backtest exits non-zero because of that failure. That is deliberate.

---

## The five seats

Each seat owns exactly one decision and writes one row to the journal.

| Seat | File | The question it answers |
|---|---|---|
| Scan | `src/policy/scan.py` | Which holdings are worth hedging at all? |
| Quant | `src/policy/quant.py` | What kind of market are we in right now? |
| Hedger | `src/policy/hedger.py` | What should the hedge be, and how big? |
| Judge | `src/policy/judge.py` | Is this proposal any good? |
| Risk | `src/policy/risk.py` | The only veto, the only signature. |

**One seat can veto and nothing trades without a signature.** A risk limit
that is never enforced is a comment. Here, an order with no Risk signature
is refused by the execution adapter itself (`src/execution/paper.py`), so
the veto does not depend on the caller remembering to honour it.

---

## The one idea

A hedge is a **trade in risk, not a trade in profit.**

That sounds obvious and it changes the design, because it makes the usual
backtest gates wrong. A perfect hedge has **zero forward-return correlation
by construction** — if the hedge removes exactly the risk you were worried
about, the hedged portfolio is uncorrelated with what you hedged, on
purpose. So a return-based information gate rejects the best possible hedge
and passes a useless one. The gates here were rebuilt around risk reduction
instead. See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §2.

---

## Play with it

Eight things to try, roughly in order of effort. Each one changes something
you can see.

### 1. Read the journal

```bash
python scripts/run_desk.py --config examples/holdings.example.yaml --journal my-journal
```

Then open `my-journal/decisions.jsonl`. Every seat's reasoning is there,
including the rejections and why they were rejected. A system that publishes
its veto reasons is auditable; one that quietly does nothing is not.

### 2. Break the desk on purpose

```bash
touch my-journal/risk.kill_switch
python scripts/run_desk.py --config examples/holdings.example.yaml --journal my-journal
rm my-journal/risk.kill_switch
```

The kill switch is a sentinel file. While it exists, the Risk seat refuses
everything and the desk trades nothing. Now you know the veto is real.

### 3. Move a threshold and watch a gate flip

The gate thresholds are constants at the top of `src/evaluation/gates.py`:

```python
MIN_R_SQUARED = 0.25
MIN_VOL_IC = 0.02
MIN_VOL_IC_TSTAT = 1.96
```

Set `MIN_R_SQUARED = 0.60` and re-run the backtest. Gate 1 now fails, the
stack short-circuits earlier, and the report says so. Thresholds are
policy, not physics — which is exactly why they live in one visible place.

### 4. Change what you hedge against

In `examples/holdings.example.yaml`, change `hedging.hedge_instrument` and
the benchmark, then re-run the backtest and compare R². This is the fastest
way to see that **the R² is a fact about a portfolio, not about hedges in
general** — which is the point of the next item.

### 5. Read the survivorship bias caveat

The bundled fixture names four tickers that all exist today and all worked.
Nothing in this repository can tell you what the result looks like on a
universe that included the failures. R² 58.5% is a fact about *this*
portfolio; the gates would be re-run on the same survivors and would look
equally good.

That is why step 6 matters, and why the answer to "does this hedge work?"
is always "on which portfolio, measured how, against which alternative?"

### 6. Point it at your own prices

There is a ready-made config for this:

```bash
python scripts/run_desk.py --config examples/holdings.csv.example.yaml --journal my-journal
```

It differs from the default config in two lines:

```yaml
data:
  source: csv
  path: examples/prices_sample.csv
```

The file's first column is a date, the rest are close prices, one column per
symbol. See `src/data/csv_source.py` for the exact shape, and
`examples/prices_sample.csv` for a working example (the bundled fixture's
last three years, so you can see the format without inventing data).

**This is the step that takes you off the synthetic fixture** — and it is
where you should start asking whether the universe you picked would have
survived. Put your own tickers in a CSV, point `data.path` at it, and run
the backtest. The gates will tell you what your portfolio looks like; they
will not tell you what a universe that included the failures would have
looked like, and nothing in this repository can.

### 7. Add a seat, a metric or a data source

[`CONTRIBUTING.md`](CONTRIBUTING.md) has all four extension points with real
code, and every interface in it was checked against the source.

### 8. Check our work

```bash
python scripts/audit_claims.py    # every number in the docs vs a live run
```

Both run in CI. They are how the claim "no number without a command that
produces it" is kept honest rather than merely stated.

---

## What to read next

| If you want to understand | Read |
|---|---|
| The reasoning, end to end | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) |
| The story, without the maths | [`README.md`](README.md) |
| The mistakes we made and fixed | [`notes/KNOWN-TRAPS.md`](notes/KNOWN-TRAPS.md) |
| How to extend it | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| What we will not claim | [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) §7 |
| The paper this is built on | Healy & Lo (2010), DOI `10.1515/9781400835812.303` — [free PDF](https://web.mit.edu/Alo/www/Papers/gates.pdf) |

## Licence

MIT. See [`LICENSE`](LICENSE). The synthetic data is a test fixture, not
evidence about real markets.
