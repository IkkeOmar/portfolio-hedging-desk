# AGENTS.md: the contract for driving this repository

---

## 1. What this repository is

**An auditable desk for the risk side of hedging: is there anything worth
hedging, and does the hedge pay for itself?**

Five seats read a portfolio and one at a time decide what to do with it:
**Scan** ranks the holdings by how much market risk each contributes,
**Quant** estimates that risk, **Hedger** proposes an overlay, **Judge**
reviews the proposal, and **Risk** holds the single veto. Every decision
goes into an append-only journal that a human can read with `less`. Then
four fail-closed gates decide whether any of it means anything: is there
anything to hedge (R²), does the timing signal exist (a Newey-West HAC
t-statistic), did the reduction pay for itself, and does it hold up out
of sample.

The subject is the *risk* side. Which candidate strategies survive contact
with the data is the other repository's job --
[`hedging-agent-public`](https://github.com/IkkeOmar/hedging-agent-public),
the research side. The execution side lives here.

### The honest headline result

**The evaluation stops at gate 2.** Gate 1 (`hedgeability`) passes with
R² 0.585; gate 2 (`regime_information`) fails, because the volatility
rank information coefficient is 0.0394 and its Newey-West HAC
t-statistic is 0.51 against a 1.96 threshold. Gates 3 and 4 are never
reached, because the gates are fail-closed and stop at the first
failure. **The desk does not find an edge, and it says so.**

This is the point, not a defect. A tool whose headline is "we ran it and
it said no" cannot be mistaken for the thing it warns about.

### What this repository is NOT

- **Not a trading signal.** It never says what to hold. It produces the
  *method* and the *findings*. A reader's risk allocation is not known
  here, so no position is responsibly derivable.
- **Not live.** Research on historical bars. No loop, no broker, no
  orders.
- **Not finished.** It is a well-audited **starting point**: the seams
  below are named so the next person can extend it. There is one data
  source, one universe, and one family of thresholds.

---

## 2. How to run it

```bash
pip install -e ".[dev]"
```

That is the whole setup. **No API key. No account. No network.** The
default data source is the repository's own synthetic fixture.

| Job | Command | Writes | Exit |
|---|---|---|---|
| One trading day | `python scripts/run_desk.py` | `journal/*.jsonl` | 0 |
| One day, machine-readable | `python scripts/run_desk.py --json` | same, plus JSON on **stdout** | 0 |
| The full evaluation | `python scripts/backtest.py` | `reports/evaluation.json`, `reports/evaluation.md`, `reports/equity.csv` | **1** -- a gate failed |
| The full evaluation, machine-readable | `python scripts/backtest.py --json` | same, plus JSON on **stdout** | **1** |
| The test suite | `python -m pytest tests/ -q` | nothing | 0 if green |
| Audit the documented claims | `python scripts/audit_claims.py` | nothing | 0 if clean, 1 if not |
| The dashboard | `streamlit run dashboard/app.py` | nothing | serves on :8501 |

### Exit codes

| Code | Meaning |
|---|---|
| **0** | it ran, and the thing it was asked to do succeeded |
| **1** | a **gate failed**. This is a *result*, not an error: the backtest's exit 1 means the evaluation rejected the strategy, and the report is written anyway. The audit scripts' exit 1 means they found a problem. |
| **2** | usage error -- a bad flag, a missing file, a bad configuration |

**Read exit 1 before treating it as failure.** The backtest exits 1 on
the bundled fixture *by design*, because gate 2 fails there.

### The `--json` contract

`--json` puts the machine-readable payload on **stdout** and nothing
else. Every human-readable line goes to **stderr**. So a consumer
parses stdout and nothing else, and a person running the command still
sees what happened.

The backtest's payload has these top-level keys: `config`, `summary`,
`gates`, `verdict`, `short_circuited_at`, `trades`, `vetoes`,
`walkforward`, `seat_errors`, `signal_errors`.

`summary` is the flat block of headline numbers: `n_days`, `n_trades`,
`n_proposals`, `n_vetoes`, `n_seat_errors`, `n_signal_errors`,
`r_squared`, `hedged_cagr`, `unhedged_cagr`, `hedged_sharpe`,
`unhedged_sharpe`, `hedged_annualised_vol`, `unhedged_annualised_vol`,
`hedged_max_drawdown`, `unhedged_max_drawdown`, `total_cost`,
`trials_declared`.

`gates` is a list of `{"name", "passed", "metrics"}`, in order:
`hedgeability`, `regime_information`, `compensation`, `stability`.
`verdict` is `pass` or `fail`. `short_circuited_at` names the gate that
stopped the run, or is absent if none did.

The desk's one-day payload has `date`, `information_cutoff`, `seats`
(one entry per seat), `order` (the `intent`, the `signature`, the
`fill`), and `veto` (the veto, or `null`).

### Optional, and never required

The dashboard has an **optional** key field for an external LLM Judge
(DeepSeek, Kimi, OpenAI, or a custom endpoint). It is **off by default**,
it is **never required**, and a key entered there is stored only in a
local, git-ignored `.env`. Nothing on the documented path asks for a key,
and the public copy collects, transmits and logs a key in no other way.

---

## 3. What the output files contain

### The journal

Five JSON Lines files, append-only, one JSON object per line. They are
the real output; the printout is a convenience. A human can read them
with `less`.

| File | One row per |
|---|---|
| `decisions.jsonl` | seat decision, with its idempotency key |
| `proposals.jsonl` | a hedge proposal from the Hedger |
| `verdicts.jsonl` | the Judge's verdict on a proposal |
| `order_intents.jsonl` | an order intent, before it is sent |
| `fills.jsonl` | a fill |

**The idempotency key is the point.** Re-running a day must produce the
same journal, not a second copy of it, so a decision whose key is
already present is not written again.

### `reports/evaluation.json`

The published evaluation. Every number the README quotes comes from
here, and `scripts/audit_claims.py` checks each one against a fresh
run. `summary` holds the headline numbers; `gates` holds the four gate
results; `trades`, `vetoes` and `walkforward` hold the detail.

**`n_seat_errors` and `n_signal_errors` are the two fields to read
first.** A seat that raises is recorded and the run continues, so a
report can otherwise look healthy while the desk did nothing. Zero on
both, and `n_trades` above zero, is what proves the run actually did
something.

### `reports/evaluation.md` and `reports/equity.csv`

The same evaluation as a readable report, and the equity series behind
the dashboard's charts.

---

## 4. What you may and may not do

### The rule that matters most

**Nothing here is advice about what to hold.** The output is a research
result. A reader's risk allocation, tax position, liabilities and time
horizon are not known here, so no position is responsibly derivable from
any number in this repository.

### Never

- **Never turn this into a signal generator.** The desk measures
  whether a hedge is worth holding. It does not say what to hold, and it
  must not be wired to anything that does.
- **Never weaken a gate threshold to make something pass.** Every
  threshold in `src/evaluation/gates.py` is a measured quantity with a
  cited source. Lowering one to turn a fail into a pass is the single
  fastest way to make this repository worthless.
- **Never present the output as advice.** Not in a README, not in a
  commit message, not in a reply.
- **Never delete the gate failure.** The evaluation stops at gate 2 and
  that is the honest headline. A repository that only ever shows its
  passes is not an auditable one.
- **Never add a required key, an account, or a network call to the
  default path.** The promise is "no key, no account, no network", and
  the CI job that proves it is named *the documented path needs no key
  and no network*.

### Always

- **Always publish a defect.** The ledger is `notes/KNOWN-TRAPS.md`, and
  the format is mechanism, why the wrong answer looked plausible, how it
  was caught, and the rule. Entry 36 is a good example: a seat that
  failed on every call produced the same gates and the same verdict as a
  healthy run.
- **Always re-read the published report.** `scripts/audit_claims.py`
  re-runs the backtest and fails if the committed
  `reports/evaluation.json` disagrees with it. A stale report silently
  supplies numbers the code no longer produces.
- **Always break a new check to prove it.** A check that has never
  failed has not been proved. Reintroduce the stale value, watch it
  fail, restore it.
- **Always regenerate the artefacts you changed.** The report, the
  equity series, and the dashboard's view of them are all generated
  from the same run.

### The seams, named on purpose

This repository is finished as an **instrument**, not as a research
programme. Four seams are real, and each is a place to change the code:

| Seam | Where | What you would do |
|---|---|---|
| **The seat protocol** | `src/desk.py` | Add a seat, or replace one. The protocol is: propose, then a single Risk signature, or nothing trades. |
| **The gate thresholds** | `src/evaluation/gates.py` | Change what counts as a hedge worth holding. |
| **The data source** | `src/data/` | Point it at your own prices. `src/data/csv_source.py` reads a CSV; `src/data/synthetic.py` makes the fixture. |
| **The benchmark set** | `src/evaluation/metrics.py` | Add the simple alternative your strategy has to beat. |

These are the same four the README names under **"Where to take this
next"**, and the claim audit checks that the two lists agree.

**If you change X, update Y:**

| If you change | Then also |
|---|---|
| A threshold in `src/evaluation/gates.py` | Re-run the backtest, commit the new `reports/evaluation.json`, and update the README's numbers. The audit will fail otherwise. |
| The seat protocol or a seat | Update `src/desk.py`, the tests for it, and the README's seat list. |
| A documented number | Re-run the command that produces it. A number no command produces rots in silence. |
| The test suite | Update every "N tests" claim. `scripts/audit_claims.py` counts what pytest collects and fails on a mismatch. |
| The defect ledger | Update the count in the documents. The audit counts the ledger's entries, in digits **and** in words. |

---

## 5. Where to read more

| File | What it holds |
|---|---|
| [`README.md`](README.md) | The entry document. The architecture, the honest result, and **"Where to take this next"**. |
| [`GUIDE.md`](GUIDE.md) | The map: the five seats, and eight things to try, each one changing something you can see. |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | Every method, with its primary source. Start here for *why* a number is what it is. |
| [`notes/KNOWN-TRAPS.md`](notes/KNOWN-TRAPS.md) | The defect ledger. What was wrong, why it was plausible, how it was caught. |
| [`notes/2026-10-24-verified-citations.md`](notes/2026-10-24-verified-citations.md) | Every citation, with its DOI and what it was checked against. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute without breaking the promises above. |
| [`SECURITY.md`](SECURITY.md) | What a key entered in the dashboard is and is not used for. |
| The other repository | [`hedging-agent-public`](https://github.com/IkkeOmar/hedging-agent-public) -- the research side: candidate strategies, a fail-closed promotion gate, a decision layer you can swap. |
