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
