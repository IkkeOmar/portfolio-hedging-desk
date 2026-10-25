# Known traps

Every entry below is a defect that was in this code at some point, was
caught, and was fixed. They are here because **the mistakes are the
credibility**: a reader who knows which traps are real can judge the ones
that are still in the code, and a reader who does not know about them will
rediscover them the expensive way.

Each entry gives the mechanism, why the wrong answer looked plausible, and
how it was caught. Several of these produced numbers that looked entirely
reasonable, which is what made them dangerous.

---

## 1. A boolean predicate used with a containment test

`prices_available()` returns a **bool**. It was used as
`if symbol not in prices_available():` — a containment test against a
boolean. That raises `TypeError`, on every decision day.

**Why it was plausible:** the name reads like a collection, and the whole
function is about availability. A reader skims the name, not the return
type.

**How it was caught:** the backtest runs. `AttributeError` and `TypeError`
on every day is not subtle.

**The rule:** check the return type of a predicate before you use it in a
membership test. `inspect.signature` and the docstring, not the name.

---

## 2. An attribute that was never assigned

The backtester referenced `self.hedge_instrument` but never set it, so
every decision day raised `AttributeError`.

**The rule:** an attribute that a constructor does not assign, and that
only fails at run time, is a design smell. If it is needed, it belongs in
`__init__` with a default.

---

## 3. The exception that made the desk look alive while it was dead

This is the worst one, and it is the reason the rest of this file exists.

The seat loop was wrapped in a bare `except Exception`. Every failure
inside it — including the `AttributeError` above and the `TypeError` above
— was converted into a **veto**. So the desk reported "51 vetoes, 0 seat
errors" and looked like a system making careful decisions, while in fact
**it had never traded a single day**.

**Why it was plausible:** vetoes are a legitimate outcome. A report that
said "51 vetoes" is not obviously wrong. Nothing distinguished "the Risk
seat said no" from "the code crashed".

**How it was caught:** the numbers. The desk produced a proposal and a
verdict but **zero fills**. A desk that never fills is not being careful.

**The rule, and it is a project rule now:** *never swallow an exception
into a `pass`.* Failures are counted separately (`seat_errors`,
`signal_errors`) and surfaced in the report and the console output. If the
documentation's example output cannot be verified, that is a **failure**,
not a warning.

---

## 4. A unit conversion applied to the wrong quantity

The synthetic market generator converted annual figures to daily ones with
`/√252`. That conversion was applied to **volatility as well as drift**,
which made daily volatility wrong by roughly 16× and sent the simulated
prices to `1e16`.

**Why it was plausible:** both quantities want annualising, and the helper
that did it looked correct.

**How it was caught:** the price series was absurd. But note the general
danger: the same class of bug at a smaller scale is invisible.

**The rule:** convert units in exactly one place, and give each conversion
its own named function so a second caller cannot apply the wrong one.

---

## 5. A correction that cancelled itself

Removing the sample-mean bias from the shocks **and adding it back** into
the drift does nothing. The code looked like a deliberate drift correction
and was not one; the realised drift was still dominated by sampling noise.

**Why it was plausible:** it is exactly what a drift correction looks like.

**The rule:** a "correction" that cancels itself is worse than none,
because it looks intentional. When you remove a bias from one place, check
where it was supposed to go.

---

## 6. Index arithmetic that flipped the sign of the result

`forward_compound(t)` — the compounded return over `t+1 … t+H` — was built
with an off-by-one in the suffix-sum index. The forward series correlated
**−0.79** with a direct computation, and the information gate reported the
**wrong sign** of the information coefficient.

**Why it was plausible:** the output was a plausible-looking number in a
plausible-looking range.

**How it was caught:** pinned against a naive loop in a test. That test is
the only reason the sign was ever right.

**The rule:** a derived series gets a test against the obvious
implementation, written before you trust the derived one.

---

## 7. A boolean derived from a human-readable string

The judge decided approve/reject by inspecting the *reason* string. A
passing criterion produced the text `"reward-to-risk 12.59"`, which shares
a prefix with the failing criterion `"... is below the 1.00 floor"`, so
**every proposal was rejected**, forever.

**Why it was plausible:** string matching on a reason is a compact way to
write a rule, and it "worked" — it just always produced the same answer.

**How it was caught:** a proposal count of zero and a fill count of zero.

**The rule:** never derive a boolean from human-readable text. Return a
boolean, and carry the text alongside it for the reader.

---

## 8. Two cash-accounting sign errors, in opposite directions

The walk-forward equity path omitted the cash from a short sale, so each
rebalance booked a fake loss equal to the traded notional. Then the sign of
the close-short cash was reversed, so the buy-back was credited instead —
adding roughly twice the notional per rebalance.

The second version produced a **hedged CAGR of +38% against +6% unhedged**.
No hedging strategy has ever earned that.

**Why it was plausible:** both numbers looked like results. The first was
merely wrong; the second was wrong *and* absurd.

**How it was caught:** two independent checks — a naive cash ledger
compared against the equity path in a test, and the question *"is this
number plausible for this strategy?"* before *"is the code correct?"*

**The rule:** the plausibility question is not a substitute for the test,
and the test is not a substitute for the plausibility question. Use both.

---

## 9. A time scaling mixed between numerator and denominator

The reward-to-risk ratio used `√(h/252)` in the numerator and `√h` in the
denominator. The ratio was understated by roughly 16×.

**Why it was plausible:** both terms were "a square root of a horizon", and
the horizon did appear in both.

**The rule:** when two terms of a ratio are scaled, scale them the same
way, or derive the ratio from first principles and check the units.

---

## 10. The risk term that was identically zero

The hedge's risk contribution was computed from the **OLS residual** of the
hedge instrument against the portfolio. When the hedge instrument *is* the
benchmark, that residual is exactly zero — so the hedge appeared to carry
no risk at all, and the sizing was wrong in a way that flattered it.

**Why it was plausible:** "the residual is what the hedge leaves behind" is
a reasonable-sounding sentence, and it is wrong for the risk of a short
leg.

**The rule:** the risk of a short leg is its **total** volatility. Residual
variance is a diagnostic, not the risk.

---

## 11. A matrix transposed, which does not raise

`purgedcv` computes the probability of backtest overfitting from a matrix
shaped `(n_configs, n_obs)`. Passing the transpose does not raise — it
silently computes the PBO of the transposed data, and returns a plausible
number. We got a PBO of 0.557 before catching it.

**Why it was plausible:** it returned a number in [0, 1], like the right
answer.

**How it was caught:** reading the library's source, because the number
looked fine and the docstring was ambiguous.

**The rule:** when a library's expected array shape is not enforced, read
the source. Docs describe intent; source describes behaviour.

---

## 12. A docstring that promised a guarantee the code did not make

`src/execution/paper.py` opened with: *"It will not fill on the decision
date, and it will not fill earlier."*

Both halves were false. The live desk fills **on** the decision date,
correctly, because its information cutoff is the previous close. And
nothing enforced the second half at all: the broker did
`fill_date = fill_date or intent.date` and used whatever it was given.

It was not live, because both callers happened to pass the right date. But
the safety was a property of two call sites rather than of the code, and a
third caller would have inherited it silently.

**How it was caught:** a documentation review asked whether the two callers
use the same convention. They do not, and the difference exposed the
unsupported claim.

**The fix:** the broker now enforces the floor itself and raises. Reverting
only the guard makes the test fail with `DID NOT RAISE ValueError`, so the
fix is load-bearing rather than decorative, and the evaluation report is
identical across all 1,192 scalar fields.

**The rule:** a docstring that states a safety property is a *claim about
the code*, and it needs the same treatment as any other claim. Where two
callers implement the same rule with different conventions, state the
**invariant both satisfy** and put the per-caller detail where a reader
will act on it.

---

## 13. An advertised option that could not be selected

`DataConfig.VALID_SOURCES` contained `"csv"`, and the CSV adapter existed
and worked. But `DataConfig` had no `path` field, so no config file could
name the file to read, and `source: csv` always raised.

**Why it was plausible:** the adapter was there, the constant was there,
and the error message even told you what to set.

**The rule:** an option the configuration accepts and the code cannot
honour is worse than one it rejects — it makes the project look more
capable than it is. Wire it in the same change that advertises it, or
remove it from the advertised set.

---

## 14. Limits that accepted nonsense silently

`RiskLimits` had no `__post_init__` validation, unlike its neighbours. A
config with `risk_per_trade_pct: -0.02` loaded without complaint and then
misbehaved later, in the Risk seat, where the cause was no longer visible.

**The rule:** a limit that cannot be honoured should stop the process at
load time, not produce a plausible-looking wrong answer later.

---

## 15. The checker that could not see what it was checking

The claim audit screens every documented number against what the code
produces. It could not see a **test count**, because nothing in the code
produces one — so the README's "33 tests" survived after six tests were
added, and the audit passed every single time.

The same blind spot applied to the **dependency table**: a row claiming a
library was "used only in tests" survived, for a library that was imported
nowhere and was not in `requirements.txt` at all.

**The rule:** *a screen is only as good as the set of numbers it can
see.* For every documented number, ask **what produces this value?** If
nothing does, your screen is blind to it and it will rot silently. Then go
and ask the producer directly — `pytest --collect-only -q` for the test
count, the package manager plus an import scan for the dependency list.

And: a new check earns its place by **failing on the stale value it was
written for**. A check that passes on first run is probably checking
nothing.

---

## 16. A correction that was also wrong

The upstream-vendor claim "zero occurrences of `hedg`, `delta`, `beta`,
`exposure`, `drawdown`, `cVaR`" was false for four of the six tokens. It
was corrected — to a claim that was *also* false: that all 33 `delta`
hits were `datetime.timedelta`, when they were 18 `timedelta`, 12
`relativedelta`, and 3 a standalone local variable named `delta`.

The correction had been written from a summary rather than by re-running
the measurement.

**The rule:** **a correction is a new claim and needs its own
measurement.** Re-measure *after* you correct, not before — the correction
is the last thing anyone will re-verify, so it is the thing that most
needs checking.

---

## 17. A widget key and an application key that were the same string

The dashboard gave a selectbox the key `desk_day` and also stored its own
output in `st.session_state["desk_day"]`. Streamlit's rule is that
**every widget with a key is added to Session State**, and the widget's
value wins on the next run. So the app's stored tuple was overwritten by
the widget's date string, and the line that read it back raised

```
ValueError: too many values to unpack (expected 2)
```

on **every** render — eleven of the seventeen dashboard tests failed from
this one cause, and the traceback pointed at a line two hundred lines
away from the mistake.

**The rule:** a widget key and an application-state key must never be the
same string. Keep them in separate namespaces — the convention is to
prefix widget keys (`w_`), and to name application state for what it is
(`app_desk_output`).

## 18. A test that asserted the impossible

The browser suite asserted that a typed API key must not appear in
`page.content()`. It does appear, exactly once, as the `value` attribute
of its own `<input type="password">`. That is how HTML stores a field's
value; there is no way around it. The test could only ever fail, or be
weakened until it asserted nothing.

**The rule:** assert what is true, not what is convenient. The honest
version is three assertions: the secret is not in the *rendered* text,
it occurs exactly once in the source, and that one occurrence is its own
input's value.

## 19. A test that passed for the wrong reason

The connection test filled in a custom base URL and then asserted that a
network error was reported. It passed — because the *model name* was
still empty, and the function refuses early with "No model name." before
it ever opens a socket. The test proved that the validation worked. It
proved nothing about the network path it was written for.

**The rule:** a test that passes on the first run is a test to distrust.
Break the thing it claims to check, confirm it fails, then restore it.
And when an assertion is about a *path*, make sure the code actually
reaches that path — otherwise the assertion is about the guard in front
of it.

## 20. Selectors written from memory instead of measured

Four selectors were guessed, and every one of them found nothing:

| Guessed | Reality | Why it failed |
|---|---|---|
| `button[role=tab]` | `<div data-testid="stTab" role="tab">` | a tab is a *div* |
| `get_by_role("checkbox")` | `<input role="switch">` | the explicit role wins |
| `get_by_role("switch").click()` | the input is 13x13 inside a `<label>` | the click stalls; click the container |
| `page.inner_text("body")` for panel content | returns **rendered** text | `text-transform: uppercase` changes it, and only the selected tab is in it |

**The rule:** read the selector out of the live DOM before writing the
assertion. Dump the test ids, the roles, the input types and the bounding
boxes once, and write the test against that dump.

## 21. An API used from memory three times in a row

Three library calls were written from recollection and all three were
wrong: `plotly` template `.copy()` (which does not exist),
`st.dataframe(..., use_container_width=True)` (deprecated, removed after
2025-12-31), and a `pandas` frame with a list column (Arrow cannot
convert it). Each was a five-minute fix *after* the failure, and each was
avoidable by reading the installed package first.

**The rule:** the installed source beats the documentation when they
disagree, and both beat memory. `python -c "import streamlit, pathlib;
print(pathlib.Path(streamlit.__file__).parent)"` then read the file.

## 22. A name that matched two different things

`get_by_role("button", name="Test")` matched **two** buttons, because
Playwright matches `name` as a case-insensitive *substring* and
"back**test**" contains "test". The test then failed with a strict-mode
violation rather than with anything resembling the real problem.

**The rule:** use `exact=True` whenever the name is a word that could
occur inside another word. A strict-mode violation is a locator bug, not
a product bug — read it as such.

## 23. A framework's chrome, in a screenshot of a product

Streamlit's Deploy button and main menu sit in the top-right of every
app. A screenshot with them in it reads as "a Streamlit demo" no matter
how the rest of the page is styled.

**The rule:** if a picture of the app will ever be shown to anyone, hide
the framework's chrome with CSS (`[data-testid="stAppDeployButton"]`).
Note that `st.set_page_config(menu_items=...)` accepts exactly three
keys — `"Get help"`, `"Report a Bug"` and `"About"` — and **no** deploy
key, so the Deploy button can only be hidden, not configured away.

---

## 24. A function defined twice, and the good one was dead

`scripts/audit_claims.py` defined `collect_test_count()` **twice**, 148
lines apart. The second definition shadowed the first, and the second was
the weaker one: the first tried `sys.executable` and then `python` on
`PATH`, because the interpreter on `PATH` is not always the one the
project runs under. The second tried only `sys.executable`.

Python does not warn about this. The module imports, every function is
"defined", the tests pass, and the more robust implementation is simply
never called.

**The rule:** when two definitions of the same name exist in a file, the
later one wins silently, and the earlier one is dead code that still
looks alive. `grep -n "^def " file.py | awk '{print $2}' | sort | uniq -d`
finds it in one command. A function that is defined but never called is
not a safety net.

## 25. A number that meant one thing locally and another in CI

The documentation claimed 85 tests. The claim audit checked that number
against `pytest --collect-only`. The dashboard tests imported Streamlit
at **module** level with `pytest.importorskip`, so when Streamlit was
missing, pytest skipped the whole *file* — and a skipped file contributes
nothing to the collected count. The same repository therefore had 85 tests
where the extra was installed and 54 where it was not.

The CI job that was supposed to enforce the number was the core job, which
does not install the extra. So the audit was comparing 85 against 54 and
failing, in the one place the number mattered.

The fix was not to weaken the check. It was to stop the count from
depending on the environment: the optional imports moved **inside the
fixtures**, so the file is always collected and the tests skip at run
time. The collection is now 85 with Streamlit, Playwright and Plotly
all blocked, which is how it was verified.

**The rule:** a number in the documentation must have exactly one
meaning in every environment the reader might be in. If a check's result
depends on which optional packages happen to be installed, the check is
measuring the environment, not the repository — and the fix is to make the
measurement independent, not to loosen the assertion.

---

## 26. A report that recorded a path with the platform's separator

The evaluation report records the configuration file it was run with. On
Windows that was `examples\holdings.example.yaml`; on Linux it is
`examples/holdings.example.yaml`. The committed report was generated on
Windows, so on CI the regenerated report did not match it -- and the
dashboard's own reproducibility test failed on a field that has nothing to
do with the desk.

The failure was invisible in the assertion: pytest prints a truncated
dictionary diff, so all it showed was `{'verdict': '...51, ...}, ...} !=
{'verdict': '...51, ...}, ...}`. The actual difference was a backslash.

**The rule:** a published artefact must be identical on every platform.
Paths recorded in a report are normalised to forward slashes, which
Windows accepts. And a reproducibility test must compare *structurally* --
exactly for strings, counts and verdicts, with a stated relative tolerance
for floats -- and must name the field and the size of the gap when it
fails. A truncated dictionary diff is not a diagnosis.

Why floats need a tolerance: numpy's pairwise summation blocks differently
across platforms and versions, so a sum of 3915 doubles is not
bit-identical everywhere. "Reproducible" has to mean reproducible, not
reproducible on one machine.

## 27. A fixture that raised instead of skipping

The dashboard tests are optional: the core install has no Streamlit. The
browser test's `server` fixture started `streamlit run` as a subprocess,
and when the module was missing the subprocess exited 1, so the fixture
raised `RuntimeError`. A fixture that raises produces a pytest **ERROR**,
and an ERROR fails the build -- so the core CI job failed on a missing
optional dependency, which is not a failure of anything.

**The rule:** an optional dependency that is not installed must produce a
*skip*, never an error. The distinction that matters is between "the
extra is not here" (skip) and "the extra is here and the server still
died" (raise) -- the second is a real defect and must fail the build.

## 28. A floor that was below the feature, and a CI job that could not see it

A reader installed the dashboard, ran it, and got a hard crash:
`TypeError` on `st.button(width=...)`, plus six "not a valid config
option" warnings. The declared floor was `streamlit>=1.40`, and the
reader happened to have an older Streamlit on their global interpreter.

**Why it was plausible:** the floor was written from a feeling ("1.40 is
recent enough") and the CI job installed `streamlit>=1.40`, which is the
*same* claim as the floor, so the two agreed with each other and nobody
learned anything. And a CI job that installs `latest` would have agreed
too, because the newest Streamlit accepts everything.

**How it was caught:** by measuring instead of assuming. Thirteen
Streamlit versions were installed, each in its own virtual environment,
and each was asked two questions: does this widget have a `width`
parameter, and does the version's own config parser reject any key in
this repository's `.streamlit/config.toml`? The answers were not what the
floor said:

| version | `st.button(width=)` | `st.plotly_chart(width=)` | config keys rejected |
|---|---|---|---|
| 1.40.0 | no | no | **6** |
| 1.49.0 | yes | no | 3 |
| 1.51.0 | yes | yes | 1 (`metricValueFontSize`) |
| 1.54.0 | yes | yes | 1 (`metricValueFontSize`) |
| **1.55.0** | yes | yes | **none** |

Two independent constraints bind, and the higher one wins: the floor is
**1.55.0**, not 1.51.0.

**The fix has two halves, and the second half matters more.** The floor is
raised, and CI installs **that floor** rather than `latest`. But the app
also feature-detects the parameter at runtime (`dashboard/compat.py`),
because the reader's environment is not the repository's environment: a
reader with an older Streamlit already in the same interpreter gets the
app, not a crash. The check asks the installed package what it accepts,
which cannot go stale the way a version comparison can.

**Two probes lied on the way, and both are worth remembering:**

- `config.get_option("theme.light")` raises on **every** version,
  including the newest. `theme.light` is a TOML *table*, not a config
  option, so this probe reports a defect that does not exist. The valid
  probe is the version's own `_update_config_with_toml`, which is what a
  reader's Streamlit actually runs.
- A probe that string-matched a module's source reported that no version
  accepted `width="stretch"` -- including 1.61.1, which demonstrably
  does. The truth is in `streamlit.elements.lib.layout_utils.Width`,
  which is `Union[int, Literal["stretch", "content"]]` from 1.49.0.

**The rule:** a probe that returns the same answer for every input is not
a measurement, and a probe that contradicts a fact you have already
observed directly should be assumed wrong until it has been re-derived
from the installed source. And a CI job that installs `latest` cannot
test a floor -- it can only test the newest version, which is the one
version guaranteed to work.

## 29. A test that imported an optional dependency at module level

The first version of the compat test imported Streamlit at the top of the
file. On the core install -- which has no Streamlit, because it is an
optional extra -- pytest raised `ModuleNotFoundError` **during
collection**, which is an ERROR, and an ERROR fails the build.

**Why it was plausible:** the import looked like a harmless convenience,
and the file was new, so nothing had yet run it in the environment it
would live in.

**How it was caught:** the suite was run in a clean virtual environment
built from `requirements.txt` alone, which is the base install the
README promises. Collection failed with
`ModuleNotFoundError: No module named 'streamlit'`.

**The rule:** an optional dependency is imported **inside a fixture**,
never at module level, and the skip happens there. A module-level
`pytest.importorskip` is the other trap: it makes the whole file vanish
from the collected count, so "how many tests does this repository have"
depends on which extras are installed -- which is trap 15 in this file,
already paid for once. The count is now the same in every environment:
**92 collected, on the base install and on the full one.**

---

## 30. A number labelled "Sharpe" that was not a Sharpe

Our own audit of somebody else's post computed:

```python
sharpe = (cagr - 0.0) / vol
```

That is **CAGR divided by volatility** — a return-to-risk ratio, sometimes
called a MAR ratio. It is *not* the Sharpe ratio, which is the mean excess
return over the standard deviation of returns.

| Quantity | Script reported | Correct value |
|---|---|---|
| Strategy "Sharpe" | **0.596** | **0.420** |
| Buy & hold "Sharpe" | 0.355 | 0.309 |

Both numbers were wrong, and the headline comparison ("Sharpe 0.596 vs
buy-and-hold 0.355") was a comparison of two CAGR/volatility ratios
dressed up as Sharpe ratios.

**Why it was plausible:** this is the single most common mislabelled
statistic in retail backtesting. The formula is short, the name is
familiar, and the output looks like a Sharpe. Nobody compares it to the
definition unless they are checking it.

**How it was caught:** by writing down the definition and computing it the
definition's way. The gap was far too large to be an annualisation
convention.

**Why it matters here specifically:** we were auditing a post that claimed
a Sharpe number. Our own audit of that post used the wrong definition. A
professional reader would have caught it in the first five minutes and
used it to dismiss the whole repository.

**The rule:** a Sharpe is `mean(excess) / std(excess, ddof=1)`, annualised
by `sqrt(252)`. Never `CAGR / volatility`. `tests/test_metrics.py` now
asserts that the two are *different numbers*, so the mislabelling cannot
come back quietly.

## 31. A trade count that counted legs and called them round trips

An earlier note explained the gap between our 20 trades and a post's 42 by
attributing it to the post using leveraged QLD:

> "Trade count differs because the post uses 8% leveraged QLD and
> continuous-entry threshold that triggers more round-trips"

That explanation was invented. Re-derived from the data, the strategy
produces **21 entries and 20 exits = 41 individual legs = 21 round trips**.
The post's "42 trades" was legs, not round trips: the two numbers were the
same measurement counted two ways.

And our script's own count was wrong too:

```python
n_trades = int((position.diff().abs() == 1).sum() // 2 + ((position.iloc[0] == 1) * 1))
```

`41 // 2 = 20`. **Integer division of an odd count.** The true round-trip
count is 21.

**Why it was plausible:** the note explained a discrepancy smoothly and
plausibly, and nobody recomputed the count from the data. A discrepancy
with a good story attached is harder to challenge than one without.

**How it was caught:** by counting the legs out of the position series
rather than trusting the note that explained them.

**The rule:** when a number disagrees with another number, the first
question is not "why might they differ" but "are they the same
measurement counted two ways". And an odd count divided by two needs a
ceiling, not a floor.

## 32. A risk-free rate that was a placeholder and was never replaced

```python
RF_RATE_DAILY = 0.0001    # placeholder cash return, ~3.6% annual
                          # — we will overlay real FRED TB3MS later
```

Two problems:

1. **The comment is wrong about its own number.** `0.0001 * 252 = 2.55%`
   annualised, not the ~3.6% the comment claims.
2. **The "later" never came.** The strategy holds cash **26.5% of the
   time**, so the cash rate is not a rounding detail — it is a first-order
   driver of the result. And the claim being tested was specifically
   "cash earns the 3-month T-bill", which was never actually modelled.

**Why it was plausible:** the placeholder was clearly marked as a
placeholder, in a comment that promised to replace it. A promise in a
comment is the easiest kind of debt to forget, and nobody reads the
comment of a constant.

**How it was caught:** by asking what the constant actually was, rather
than what it was supposed to be.

**The rule:** a placeholder that is load-bearing is a defect, not a
convenience. Either replace it, or state the assumption in the report and
say plainly what it does and does not model. It is now an explicit,
documented config value, and the reports state the cash assumption
instead of burying it.

## 33. A ratio of two different scales, with the market's variance missing

```
systematic     = (portfolio_beta - beta) * beta    <- dimensionless
idiosyncratic = beta * idio**2                     <- a variance
hedgeable      = systematic / total
```

**Impact:** high. The metric is the Scan seat's entire reason to exist --
it decides which holdings are worth hedging -- and it was measuring the
wrong thing for the holdings that matter most.

**Status:** fixed.

**Symptom:** for any holding whose beta is ABOVE the portfolio's beta, the
systematic term comes out **negative**. The share is then clipped to zero,
so the desk reported "0% hedgeable" about exactly the holdings most
exposed to the market, and therefore the ones a market hedge helps most.

Measured on the bundled fixture (portfolio beta 0.9315):

| holding | beta | old share | corrected share |
|---|---|---|---|
| MSFT | 0.692 | 0.910 | 0.336 |
| AAPL | 1.008 | **0.000** | 0.369 |
| NVDA | 1.024 | **0.000** | 0.129 |

**Mechanism:** three separate faults in one line.

1. **Scale.** The two terms are added, and one is dimensionless while the
   other is a variance. Their sum has no units.
2. **A missing input.** The market's variance never appears, so a
   holding's "hedgeable share" could not change when market volatility
   changed -- and it must: in a calm market most of a holding's risk is
   its own, and in a violent market most of it is the market's. With the
   old formula the share was **constant** across a 625x range of market
   variance.
3. **A sign inversion.** `(portfolio_beta - beta)` is negative exactly
   when the holding is more market-exposed than the portfolio. The metric
   measured the *opposite* of its own name.

**Why it was plausible:** the formula was documented in the module
docstring, it produced plausible-looking numbers in [0, 1], and it had
**no test at all**. Nothing was pinned, so nothing could break. The
docstring even said the first term was "the risk that comes from moving
with the market", which is true of `beta**2 * var_m` and false of a beta
difference.

**How it was caught:** by asking what the metric would do when the market
got more volatile -- a question the code had no answer to, because the
market's variance was not in it.

**Fix:** the metric is now the one-factor variance decomposition, the same
model the data generator itself uses:

```
systematic     = (beta * sigma_m)**2     -- sigma_m from the panel
idiosyncratic = idio**2
total         = systematic + idiosyncratic
hedgeable     = systematic / total
```

`sigma_m` is read from the benchmark's own returns over the cut-off
window, so the metric sees the market as it is at the decision date. The
now-dead `portfolio_beta` accumulation was removed with it.

**`tests/test_scan_metric.py` pins it**, and each test was proved by
reinstating the old formula and watching it fail: 6 of the 7 fail against
the old code, and the seventh (the fail-closed missing-benchmark check)
correctly still passes.

**The published numbers did not move.** R^2 0.5850, 121 trades, 172
proposals, 51 vetoes, cost 557.03, gates unchanged -- all identical
before and after. The reason is that the Hedger weights the candidates by
their portfolio weights, which are order-invariant; the seat's *ranking*
changed, but the set of candidates it passed on did not.

**The rule:** a ratio of two quantities is only meaningful if they are on
the same scale, and a metric that claims to describe how exposed
something is to a market must contain the market's volatility. Ask what
the number does when the world changes; if the answer is "nothing", the
number is missing its input.

## 34. A CI job that installed ">= the floor", and so could not see it

```
python -m pip install "streamlit>=1.55.0" "plotly>=5.20" playwright
```

The dashboard job's job is to answer one question: **does the app work on
the oldest Streamlit this repository claims to support?** A `>=` bound
installs the NEWEST Streamlit, so the job answered a different question
-- does the app work on the newest Streamlit -- which the job was always
going to pass.

The bug this was written for is exactly the one a `>=` bound cannot see.
The declared floor was `>=1.40`, and `st.button(width=...)` first exists
in 1.49.0. On any version below that the dashboard raised `TypeError`, and
the six theme options `baseFontSize`, `baseFontWeight`,
`metricValueFontSize`, `showSidebarBorder`, `theme.light` and `theme.dark`
were rejected by the config parser. A CI job installing the newest
Streamlit sees a working dashboard every single time, and says nothing
about the readers who are actually broken.

**Impact:** high, and invisible. The class of bug is a floor that is
below the feature, which is precisely what a floor is supposed to
prevent.

**Status:** fixed.

**Fix:** the job installs the floor exactly.

```
python -m pip install "streamlit==1.55.0" "plotly>=5.20" playwright
```

1.55.0 is the floor because it is the first version that accepts
`theme.metricValueFontSize` (rejected through 1.54.0), and it has
`st.button(width=...)` (1.49.0) and `st.plotly_chart(width=...)`
(1.51.0). The dashboard ALSO feature-detects `width` at runtime, so a
reader on an older Streamlit gets the app instead of a `TypeError` --
but the floor is what CI tests against, and the shim is what keeps old
readers working. Both are needed; neither substitutes for the other.

**Why it was plausible:** `>=` is the conventional way to write a floor,
and it is what `pyproject.toml` correctly says. But a *declared
dependency* and a *tested version* are different claims, and only the
second one can catch a bug. The floor in `pyproject.toml` is a promise
to readers; the version in CI is the promise to ourselves.

**How it was caught:** by reading the CI file against the requirement,
after the floor itself had been raised. The floor was raised and the
defect stayed, because the check that was supposed to confirm the floor
was not checking it.

**The rule:** a floor that nothing installs is a comment. If the whole
point of the floor is to catch an incompatible feature, then the test
environment must BE the floor -- not "at least the floor", which is the
newest thing available and therefore always passes.

## 35. An audit that trusted a report it did not produce

The claim audit re-ran the DESK. It did not re-run the BACKTEST. So
`reports/evaluation.json` -- the file every documented number was
checked against -- could be stale, and a stale report supplies numbers
the current code no longer produces.

**Impact:** high, and invisible. The audit's whole job is to catch a
number that has drifted away from the code. A stale report inverts that:
the documented number and the stale report agree with each other, so the
check passes, and the code has moved on without anyone noticing.

**Why it was plausible:** the two are different experiments. The desk
runs ONE trading day; the report is the full 15-year walk-forward
backtest. They share field names and measure different things -- n_days
is 1 in one and 3915 in the other -- so comparing them reports a false
positive on a perfectly fresh report. The first version of the fix
compared them anyway, and failed on a correct report. The second
version compared the gate metrics, and failed the same way.

**How it was caught:** by asking what the audit was actually checking.
The only sound comparison is the SAME experiment run again, so the
audit now re-runs the backtest -- about 25 seconds on the bundled
fixture -- and compares the two reports field by field.

**Fix.** When `--report` is given, the report is current by
construction, so no check is needed. When it is not, the committed
report is compared against a fresh backtest, and a disagreement is a
FAILURE, not a warning:

    FAIL  the committed reports/evaluation.json is STALE: it disagrees
    with a fresh backtest on 1 field(s): summary.n_trades=999 (fresh run:
    121). A stale report silently supplies numbers the current code no
    longer produces, so every number it contributed is unverified.

**Proved by breaking it:** changing one number in the committed report
fails the audit with that exact message; restoring it passes.

**The rule:** *a checker that reads a file it did not produce is
checking the file, not the code.* If the artefact can drift, the check
has to regenerate it. And when two things share names but measure
different things, the fix is to run the same experiment twice, not to
find a field where they happen to agree.
