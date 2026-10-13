# Convergence loop: a worked example (synthetic)
A fictional PR run through `tools/class-ledger/ledger.py` end to end, to test whether the design catches the instance-chasing pattern (`rules/leak-classes.md`, C1). Everything here is invented: the project (recipe-box), the PR (12), the vendors (Alpha, Beta), the comment ids and the sweep outputs. Nothing was read from any real project. Run by the Platform Engineer on 2026-10-13, Windows 11, Python 3.12.10.

## The story
- **PR 12** adds a unit converter. Author: Build Engineer · Beta. Round 1 is the PROPOSED dual-vendor parallel round: Independent Reviewer · Alpha (verdict counts) and Independent Reviewer · Beta (extra opinion).
- **Round 1.** Alpha raises class `unit-alias` with the generator "any unit spelling the parser accepts that is not a row of the canonical unit table", two instances (`tbsp.`, `TBSP`). Beta raises the same `tbsp.` instance (counted once, both vendors recorded) and a P3 wording class. The Orchestrator sorts: `unit-alias` Act on, `help-wording` Noted.
- **Builder fix 1.** The builder blocks the two reported spellings and "sweeps" only those two: it patched instances, not the generator. It closes the class.
- **Round 2.** Alpha re-sweeps with a different vocabulary and finds `Tbl`, a third member of the same class. It first tries to file it as a new class with a reworded generator; the ledger refuses (generator overlap 0.62 with `unit-alias`). Filed under the right class, it is a **REOPEN**: the report shows `reopen_count 1`, round 2 with 0 new classes and 1 reopen, and `unit-alias` under "needs a different agent". The original builder's second close is refused.
- **Limit shown on a throwaway copy.** The same dodge with fully reworded generator words ("capitalised kitchen measures the converter takes") gets through as a new class. It is not hidden: the report lists it under "new classes after round 1" for the Orchestrator to confirm, and it blocks exit like any open P2.
- **Different-agent sweep.** Platform Engineer · Alpha changes the parser to accept only table rows and sweeps the whole space (1840 spellings, 0 accepted outside the table; the new test is red on the round-2 head). The ledger accepts the close because this signature never closed the class before.
- **Round 3.** Alpha's verification with the closer's own generator is refused; with a different generator (a public units list plus one-character drops) it is recorded. `exit ready: yes` at round 3 of a budget of 3.

## Result
The design did what it claims on this example: the third instance was recorded as a reopen of a closed class, not as a fresh class; the metrics made it visible (`reopen_count: 1`, `reopened_classes`, `per_round.2.reopens: 1`, `needs_different_agent`); the same closer could not close it again; and the loop converged at round 3 once the fix addressed the generator. It also shows the main gap: a reviewer who rewords the generator enough can still open a new class; the ledger only flags it for review. What this example cannot show: whether real reviewers write good generators, whether real builders' sweeps cover them, and whether rounds actually drop. That needs the trial in `docs/convergence-loop.md`.

## Exact commands
Saved as `f3-run.sh` in a scratch folder and run with `bash f3-run.sh <empty folder>`. `run` prints each command (without shell quoting), the tool's output and its exit code. `T` is this repo's `tools/class-ledger`.

```bash
#!/bin/bash
# Worked example: fictional PR 12 of the invented project recipe-box.
T=/c/Users/carlo/dev/agent-orchestration/tools/class-ledger
cd "$1"
run() { echo "\$ ledger $*"; python -B "$T/ledger.py" "$@" 2>&1; echo "[exit $?]"; echo; }
RA="Independent Reviewer · Alpha"; RB="Independent Reviewer · Beta"
BB="Build Engineer · Beta"; PA="Platform Engineer · Alpha"; OR="Orchestrator · Alpha"
GEN="any unit spelling the parser accepts that is not a row of the canonical unit table"

echo "## Round 1"
run init pr-12.json --pr 12 --budget 3 --head 1111111111111111111111111111111111111111
run add-finding pr-12.json --class unit-alias --by "$RA" --severity P2 --file app/units.py:41 --generator "$GEN" --counterexample "'tbsp.' parses as tablespoon" --repro "python -m recipe convert '1 tbsp.'"
run add-finding pr-12.json --class unit-alias --by "$RA" --severity P2 --file app/units.py:41 --counterexample "'TBSP' parses as tablespoon" --repro "python -m recipe convert '1 TBSP'"
run add-finding pr-12.json --class unit-alias --by "$RB" --severity P2 --file app/units.py:41 --counterexample "'tbsp.' parses as tablespoon" --repro "python -m recipe convert '1 tbsp.'"
run add-finding pr-12.json --class help-wording --by "$RB" --severity P3 --file docs/units.md:8 --generator "any help sentence naming a unit the table does not list" --counterexample "help mentions 'dash'" --repro "grep -n dash docs/units.md"
run sort pr-12.json unit-alias --bucket act --by "$OR"
run sort pr-12.json help-wording --bucket noted --by "$OR" --reason "P3 wording, one line"
run status pr-12.json
echo "## Builder fix 1: patches the two reported spellings, sweeps only them"
printf 'tbsp. rejected\nTBSP rejected\n2 of 2 checked\n' > sweep-1.txt
run close-class pr-12.json unit-alias --by "$BB" --evidence "builder comment 2001" --sweep-cmd "python sweep_units.py --only 'tbsp.' TBSP" --sweep-output sweep-1.txt

echo "## Round 2"
run new-round pr-12.json --head 2222222222222222222222222222222222222222
echo "# reviewer tries to file the third spelling as a fresh class (the dodge)"
run add-finding pr-12.json --class unit-abbrev-case --by "$RA" --severity P2 --file app/units.py:44 --generator "any unit abbreviation the parser accepts that is not in the canonical table" --new-reason "different spelling" --counterexample "'Tbl' parses as tablespoon" --repro "python -m recipe convert '1 Tbl'"
echo "# filed under the class it belongs to"
run add-finding pr-12.json --class unit-alias --by "$RA" --severity P2 --file app/units.py:44 --counterexample "'Tbl' parses as tablespoon" --repro "python -m recipe convert '1 Tbl'"
run report pr-12.json
echo "# LIMIT, on a throwaway copy: the same dodge with reworded generator words gets through, but is listed for the Orchestrator"
cp pr-12.json dodge-copy.json
run add-finding dodge-copy.json --class capital-measure --by "$RA" --severity P2 --file app/units.py:47 --generator "capitalised kitchen measures the converter takes" --new-reason "capital letters, not punctuation" --counterexample "'Tbs' parses as tablespoon" --repro "python -m recipe convert '1 Tbs'"
run status dodge-copy.json
echo "# the same builder tries to close it again"
run close-class pr-12.json unit-alias --by "$BB" --evidence "builder comment 2002" --sweep-cmd "python sweep_units.py --only Tbl"
echo "## Whole-class sweep by a different agent: parser now accepts only table rows"
printf 'enumerated 1840 spellings (table rows x case x punctuation x common abbreviations)\naccepted: 23, all table rows\nnot in table and accepted: 0\nmutation: old head accepts 41 of them (red)\n' > sweep-2.txt
run close-class pr-12.json unit-alias --by "$PA" --evidence "sweep comment 2003; test test_units_whole_space red on 2222222, green on 3333333" --sweep-cmd "python sweep_units.py --all-spellings" --sweep-output sweep-2.txt

echo "## Round 3"
run new-round pr-12.json --head 3333333333333333333333333333333333333333
run verify-class pr-12.json unit-alias --by "$RA" --generator-used "$GEN" --evidence "round 3 notes"
run verify-class pr-12.json unit-alias --by "$RA" --generator-used "every unit string in the public cooking-units list, plus each with one character dropped" --evidence "round 3 notes: 312 strings, 0 accepted outside the table"
run report pr-12.json
```

## Exact output
Sweep files are made by `printf` in the script; the ledger hashes them into the close record.

```text
## Round 1
$ ledger init pr-12.json --pr 12 --budget 3 --head 1111111111111111111111111111111111111111
ledger for PR 12 created, round 1, budget 3
[exit 0]

$ ledger add-finding pr-12.json --class unit-alias --by Independent Reviewer · Alpha --severity P2 --file app/units.py:41 --generator any unit spelling the parser accepts that is not a row of the canonical unit table --counterexample 'tbsp.' parses as tablespoon --repro python -m recipe convert '1 tbsp.'
F1: new class 'unit-alias' opened in round 1
[exit 0]

$ ledger add-finding pr-12.json --class unit-alias --by Independent Reviewer · Alpha --severity P2 --file app/units.py:41 --counterexample 'TBSP' parses as tablespoon --repro python -m recipe convert '1 TBSP'
F2: instance of open class 'unit-alias'
[exit 0]

$ ledger add-finding pr-12.json --class unit-alias --by Independent Reviewer · Beta --severity P2 --file app/units.py:41 --counterexample 'tbsp.' parses as tablespoon --repro python -m recipe convert '1 tbsp.'
F3: same instance as F1 in class 'unit-alias' (vendor recorded, not counted)
[exit 0]

$ ledger add-finding pr-12.json --class help-wording --by Independent Reviewer · Beta --severity P3 --file docs/units.md:8 --generator any help sentence naming a unit the table does not list --counterexample help mentions 'dash' --repro grep -n dash docs/units.md
F4: new class 'help-wording' opened in round 1
[exit 0]

$ ledger sort pr-12.json unit-alias --bucket act --by Orchestrator · Alpha
class 'unit-alias' -> act
[exit 0]

$ ledger sort pr-12.json help-wording --bucket noted --by Orchestrator · Alpha --reason P3 wording, one line
class 'help-wording' -> noted
[exit 0]

$ ledger status pr-12.json
class         state  sev  bucket  inst  reopen  vendors     opened
------------  -----  ---  ------  ----  ------  ----------  ------
help-wording  open   P3   noted   1     0       beta        r1
unit-alias    open   P2   act     2     0       alpha+beta  r1

PR 12  round 1 of budget 3
classes: 2 opened, 0 closed, 2 open, 0 dismissed; reopens: 0
per round: r1: 2 new / 1 inst / 0 reopen
exit ready: no (blocking: unit-alias; last round must add no new class and no reopen)
[exit 0]

## Builder fix 1: patches the two reported spellings, sweeps only them
$ ledger close-class pr-12.json unit-alias --by Build Engineer · Beta --evidence builder comment 2001 --sweep-cmd python sweep_units.py --only 'tbsp.' TBSP --sweep-output sweep-1.txt
class 'unit-alias' closed by Build Engineer · Beta in round 1
[exit 0]

## Round 2
$ ledger new-round pr-12.json --head 2222222222222222222222222222222222222222
round 2 started at 2222222222222222222222222222222222222222
[exit 0]

# reviewer tries to file the third spelling as a fresh class (the dodge)
$ ledger add-finding pr-12.json --class unit-abbrev-case --by Independent Reviewer · Alpha --severity P2 --file app/units.py:44 --generator any unit abbreviation the parser accepts that is not in the canonical table --new-reason different spelling --counterexample 'Tbl' parses as tablespoon --repro python -m recipe convert '1 Tbl'
REFUSED: looks like a known class: unit-alias (generator overlap 0.62, state closed). File it under that class, or pass --distinct-from <class> with --new-reason so the Orchestrator can check the call
[exit 1]

# filed under the class it belongs to
$ ledger add-finding pr-12.json --class unit-alias --by Independent Reviewer · Alpha --severity P2 --file app/units.py:44 --counterexample 'Tbl' parses as tablespoon --repro python -m recipe convert '1 Tbl'
F5: REOPEN of closed class 'unit-alias' (reopen #1); failed sweep by Build Engineer · Beta; the next close must come from a different agent
[exit 0]

$ ledger report pr-12.json
{
  "blocking_classes": [
    "unit-alias"
  ],
  "both_vendor_classes": [
    "unit-alias"
  ],
  "buckets": {
    "act": 1,
    "consider": 0,
    "dismissed": 0,
    "noted": 1,
    "unsorted": 0
  },
  "budget": 3,
  "classes_closed": 0,
  "classes_dismissed": 0,
  "classes_merged": 0,
  "classes_open": 2,
  "classes_opened": 2,
  "exit_ready": false,
  "instances_per_class": {
    "help-wording": 1,
    "unit-alias": 3
  },
  "needs_different_agent": [
    "unit-alias"
  ],
  "new_classes_after_round_1": [],
  "over_budget": false,
  "per_round": {
    "1": {
      "duplicates": 1,
      "findings": 4,
      "instances": 1,
      "new_classes": 2,
      "reopens": 0
    },
    "2": {
      "duplicates": 0,
      "findings": 1,
      "instances": 0,
      "new_classes": 0,
      "reopens": 1
    }
  },
  "pr": "12",
  "reopen_count": 1,
  "reopened_classes": [
    "unit-alias"
  ],
  "round": 2
}

class         state     sev  bucket  inst  reopen  vendors     opened
------------  --------  ---  ------  ----  ------  ----------  ------
help-wording  open      P3   noted   1     0       beta        r1
unit-alias    reopened  P2   act     3     1       alpha+beta  r1

PR 12  round 2 of budget 3
classes: 2 opened, 0 closed, 2 open, 0 dismissed; reopens: 1
per round: r1: 2 new / 1 inst / 0 reopen, r2: 0 new / 0 inst / 1 reopen
NEEDS A DIFFERENT AGENT'S WHOLE-CLASS SWEEP: unit-alias
exit ready: no (blocking: unit-alias; last round must add no new class and no reopen)
[exit 0]

# LIMIT, on a throwaway copy: the same dodge with reworded generator words gets through, but is listed for the Orchestrator
$ ledger add-finding dodge-copy.json --class capital-measure --by Independent Reviewer · Alpha --severity P2 --file app/units.py:47 --generator capitalised kitchen measures the converter takes --new-reason capital letters, not punctuation --counterexample 'Tbs' parses as tablespoon --repro python -m recipe convert '1 Tbs'
F6: new class 'capital-measure' opened in round 2
[exit 0]

$ ledger status dodge-copy.json
class            state     sev  bucket    inst  reopen  vendors     opened
---------------  --------  ---  --------  ----  ------  ----------  ------
capital-measure  open      P2   unsorted  1     0       alpha       r2
help-wording     open      P3   noted     1     0       beta        r1
unit-alias       reopened  P2   act       3     1       alpha+beta  r1

PR 12  round 2 of budget 3
classes: 3 opened, 0 closed, 3 open, 0 dismissed; reopens: 1
per round: r1: 2 new / 1 inst / 0 reopen, r2: 1 new / 0 inst / 1 reopen
NEEDS A DIFFERENT AGENT'S WHOLE-CLASS SWEEP: unit-alias
new classes after round 1 (Orchestrator: confirm each is not a renamed known class): capital-measure
exit ready: no (blocking: capital-measure, unit-alias; last round must add no new class and no reopen)
[exit 0]

# the same builder tries to close it again
$ ledger close-class pr-12.json unit-alias --by Build Engineer · Beta --evidence builder comment 2002 --sweep-cmd python sweep_units.py --only Tbl
REFUSED: class 'unit-alias' was reopened after Build Engineer · Beta closed it; a DIFFERENT agent must do the whole-class sweep and close it
[exit 1]

## Whole-class sweep by a different agent: parser now accepts only table rows
$ ledger close-class pr-12.json unit-alias --by Platform Engineer · Alpha --evidence sweep comment 2003; test test_units_whole_space red on 2222222, green on 3333333 --sweep-cmd python sweep_units.py --all-spellings --sweep-output sweep-2.txt
class 'unit-alias' closed by Platform Engineer · Alpha in round 2
[exit 0]

## Round 3
$ ledger new-round pr-12.json --head 3333333333333333333333333333333333333333
round 3 started at 3333333333333333333333333333333333333333
[exit 0]

$ ledger verify-class pr-12.json unit-alias --by Independent Reviewer · Alpha --generator-used any unit spelling the parser accepts that is not a row of the canonical unit table --evidence round 3 notes
REFUSED: that is the generator the class was closed with; re-sweep with a DIFFERENT vocabulary or generator
[exit 1]

$ ledger verify-class pr-12.json unit-alias --by Independent Reviewer · Alpha --generator-used every unit string in the public cooking-units list, plus each with one character dropped --evidence round 3 notes: 312 strings, 0 accepted outside the table
class 'unit-alias' verified clean by Independent Reviewer · Alpha with a different generator
[exit 0]

$ ledger report pr-12.json
{
  "blocking_classes": [],
  "both_vendor_classes": [
    "unit-alias"
  ],
  "buckets": {
    "act": 1,
    "consider": 0,
    "dismissed": 0,
    "noted": 1,
    "unsorted": 0
  },
  "budget": 3,
  "classes_closed": 1,
  "classes_dismissed": 0,
  "classes_merged": 0,
  "classes_open": 1,
  "classes_opened": 2,
  "exit_ready": true,
  "instances_per_class": {
    "help-wording": 1,
    "unit-alias": 3
  },
  "needs_different_agent": [],
  "new_classes_after_round_1": [],
  "over_budget": false,
  "per_round": {
    "1": {
      "duplicates": 1,
      "findings": 4,
      "instances": 1,
      "new_classes": 2,
      "reopens": 0
    },
    "2": {
      "duplicates": 0,
      "findings": 1,
      "instances": 0,
      "new_classes": 0,
      "reopens": 1
    },
    "3": {
      "duplicates": 0,
      "findings": 0,
      "instances": 0,
      "new_classes": 0,
      "reopens": 0
    }
  },
  "pr": "12",
  "reopen_count": 1,
  "reopened_classes": [
    "unit-alias"
  ],
  "round": 3
}

class         state   sev  bucket  inst  reopen  vendors     opened
------------  ------  ---  ------  ----  ------  ----------  ------
help-wording  open    P3   noted   1     0       beta        r1
unit-alias    closed  P2   act     3     1       alpha+beta  r1

PR 12  round 3 of budget 3
classes: 2 opened, 1 closed, 1 open, 0 dismissed; reopens: 1
per round: r1: 2 new / 1 inst / 0 reopen, r2: 0 new / 0 inst / 1 reopen, r3: 0 new / 0 inst / 0 reopen
exit ready: yes
[exit 0]
```
