# Learning Report — `main.py` Line-by-Line Walkthrough

This document exists so you can defend every line of `main.py` in a mentor
review: what it does, why it's written that way, and what alternatives were
rejected. Read top to bottom once, then use the Q&A section at the end as a
rehearsal for questions you're likely to get asked.

## 0. File structure check

```
project/
|-- generate_data.py     provided/extended — generates sales.csv + ~489 bad rows
|-- sales.csv             100,000 rows, generated
|-- main.py               solution file
|-- report.csv            output
|-- errors.log            output
```

This matches the assignment spec exactly.

---

## 1. Line-by-line walkthrough

### Lines 1–5 — module docstring and imports

```python
"""Aggregates sales.csv into a per-product report.csv, logging any skipped bad rows to errors.log."""

import csv
import os
import sys
```

- The triple-quoted string right under the top of the file is a **module
  docstring**. Python attaches it to `main.__doc__`. It's not a comment — if
  you ran `import main; print(main.__doc__)` you'd get that string back. This
  is different from a `#` comment, which is stripped at parse time and
  invisible to the running program.
- `csv` — standard library module for reading/writing CSV files. It handles
  quoting, embedded commas, and newlines-in-fields correctly, which a naive
  `line.split(",")` would not.
- `os` — used once, for `os.path.isfile(...)`, to check the input file exists
  before we try to open it.
- `sys` — used for `sys.exit(1)`, which stops the program with a non-zero exit
  code (signals failure to the shell / caller) without raising a traceback the
  user would find alarming.

### Lines 7–10 — file path and threshold constants

```python
INPUT_CSV_FILE = "sales.csv"
OUTPUT_CSV_FILE = "report.csv"
ERROR_LOG_FILE = "errors.log"
MIN_TOTAL_PRICE = 50.0
```

- All-caps names are a Python convention (not enforced by the language) for
  values meant to be treated as constants — i.e., nobody should reassign
  `INPUT_CSV_FILE` at runtime.
- Centralizing these at the top means if the assignment changed the minimum
  order threshold from $50 to $75, there's exactly one number to edit, and no
  risk of missing a second copy buried in a loop.

### Lines 12–19 — expected column schema

```python
EXPECTED_COLUMNS = [
    "transaction_id",
    "date",
    "product",
    "region",
    "quantity",
    "unit_price",
]
```

- This is a `list` of strings, in the exact order the CSV header should
  appear. It's compared later (`reader.fieldnames != EXPECTED_COLUMNS`)
  against what's actually in the file's first row.
- Why a list and not a `set`? Because order matters here as an extra sanity
  check — a `set` comparison would consider `["a","b"]` equal to `["b","a"]`,
  but we want to catch column reordering too, not just column renaming/loss.

### Line 21 — known product whitelist

```python
KNOWN_PRODUCTS = ["Laptop", "Mouse", "Keyboard", "Monitor", "Headset"]
```

- The fixed set of products the business report cares about, per the
  assignment spec. Used to pre-seed the aggregation dict (see
  `load_products`) and to filter out any unexpected product value.

### Lines 24–29 — `load_products()`

```python
def load_products():
    """Fresh per-product stats dict: revenue, units_sold, order_count."""
    return {
        product: {"revenue": 0.0, "units_sold": 0, "order_count": 0}
        for product in KNOWN_PRODUCTS
    }
```

- This is a **dict comprehension**: `{key_expr: value_expr for item in
  iterable}`. It's equivalent to:
  ```python
  result = {}
  for product in KNOWN_PRODUCTS:
      result[product] = {"revenue": 0.0, "units_sold": 0, "order_count": 0}
  return result
  ```
  but more idiomatic Python.
- Each value is itself a small dict — so the overall structure is a
  dict-of-dicts, e.g. `{"Laptop": {"revenue": 0.0, "units_sold": 0,
  "order_count": 0}, "Mouse": {...}, ...}`.
- Why a function instead of a module-level dict literal? So every call
  returns a **brand new** dict. If it were a single module-level dict shared
  across calls (or across test runs), running `process_sales` twice in the
  same process would silently accumulate totals from the first run into the
  second — a classic mutable-default-state bug.

### Lines 32–53 — `validate_row(row)`

```python
def validate_row(row):
    """Returns None if the row is usable, otherwise a reason string for errors.log."""
    if not row["product"]:
        return "missing product name"
```

- `row` is a `dict` (because we use `csv.DictReader`, see below), keyed by
  column name, e.g. `{"transaction_id": "...", "product": "Laptop", ...}`.
- `row["product"]` fetches the product field as a **string** (CSV has no
  native types — everything read from a CSV file is text).
- `not row["product"]` is `True` when the string is empty (`""`), because
  Python treats empty strings as falsy. This is the "missing product name"
  bad-row case from the generator.

```python
    quantity_raw = row["quantity"]
    if not quantity_raw:
        return "missing quantity"
```

- Same falsy-empty-string check, this time for quantity. Caught **before**
  attempting `int()` on it, because `int("")` raises `ValueError` — we want a
  clean, readable log reason instead of a crash.

```python
    try:
        quantity = int(quantity_raw)
    except ValueError:
        return f"non-numeric quantity ({quantity_raw})"
```

- `try/except` around `int(quantity_raw)`: if the string isn't a valid
  integer (e.g. `"abc"`), `int()` raises `ValueError`, which we catch and
  convert into a descriptive skip reason instead of letting the exception
  propagate and kill the whole run.
- `f"non-numeric quantity ({quantity_raw})"` is an **f-string** — the
  `{quantity_raw}` part is evaluated and interpolated into the string at
  runtime. Equivalent to `"non-numeric quantity (" + quantity_raw + ")"` but
  clearer and handles non-string values automatically via `str()`.

```python
    if quantity < 0:
        return f"negative quantity ({quantity})"
```

- Here `quantity` is now an actual `int` (the conversion above succeeded), so
  this is a numeric comparison, not a string one.

```python
    price_raw = row["unit_price"]
    try:
        float(price_raw)
    except ValueError:
        return f"non-numeric unit_price ({price_raw})"

    return None
```

- Same pattern for price, using `float()` since price has a decimal
  component (`999.99`).
- Note: the result of `float(price_raw)` is **not saved** here — this
  function is *purely* a validator, it just proves the conversion would
  succeed. The actual conversion for use in the aggregation happens later in
  `process_sales`, after this function has already given the green light. That
  is a deliberate separation of concerns: `validate_row` answers "is this row
  usable?", it doesn't do the row's real work.
- `return None` at the end is the "all checks passed" case. `None` is falsy,
  so callers just do `if skip_reason:` to branch on whether validation
  failed.

### Lines 56–101 — `process_sales(input_path, error_log_path)`

```python
def process_sales(input_path, error_log_path):
    """Reads the sales CSV row by row, validates it, and aggregates per-product stats.

    Returns (products, total_rows, skipped_rows).
    """
    products = load_products()
    total_rows = 0
    skipped_rows = 0
```

- This is a **multi-line docstring** (triple-quoted, spans more than one
  line). The blank line inside separates the one-line summary from further
  detail — this is the standard convention many style guides (e.g. Google,
  NumPy docstring styles) recommend.
- Three local variables initialize the function's working state: the
  aggregation dict, and two running counters. Because they're declared inside
  the function (not at module level), they can't leak or get corrupted by
  other code, unlike the original version of this script which used module-
  level globals.

```python
    with open(input_path, newline="", encoding="utf-8") as csvfile, \
         open(error_log_path, mode="w", encoding="utf-8") as errfile:
```

- `with ... as ...` is a **context manager**. It guarantees the file is
  closed automatically when the block exits — even if an exception is
  raised inside it — without needing an explicit `try/finally`.
- This line opens **two files at once** in a single `with` statement, joined
  by a comma. The trailing `\` is a **line continuation character**, letting
  the statement span two physical lines for readability (it has no runtime
  effect other than telling Python "this line isn't finished yet").
- `newline=""` on the input file is the standard/required way to open a file
  for `csv` module reading — it disables Python's own universal-newline
  translation so the `csv` module can handle line endings itself, avoiding
  duplicate/blank rows on Windows-style files.
- `encoding="utf-8"` is explicit rather than relying on the OS/locale
  default, so the script behaves the same on any machine.
- `mode="w"` on `error_log_path` means: create the file if it doesn't exist,
  and **truncate** it if it does — so every run starts `errors.log` fresh
  rather than appending to stale results from a previous run.

```python
        reader = csv.DictReader(csvfile)
```

- `csv.DictReader` wraps the file object and turns each row into a `dict`
  keyed by the header row's column names (read automatically from the first
  line). Compare to plain `csv.reader`, which would give you a `list` per row
  and force you to remember column *positions* (`row[4]` for quantity) — far
  more fragile if columns ever get reordered.

```python
        # Guards against silent column-order/name drift: DictReader maps by header name,
        # so a reordered or renamed column would otherwise read the wrong field silently.
        if reader.fieldnames != EXPECTED_COLUMNS:
            print("CSV file columns do not match the expected columns")
            sys.exit(1)
```

- `reader.fieldnames` is a list of the header names, populated as a side
  effect of constructing the `DictReader` (it peeks at the first line).
- Comparing this list to `EXPECTED_COLUMNS` is a **fail-fast** guard: if
  someone hands the script a CSV with different or reordered columns, we stop
  immediately with a clear message rather than silently producing a bogus
  report.
- `sys.exit(1)` — exit code `1` conventionally means "the program failed."
  `0` means success. This is how shell scripts / CI pipelines detect failure.

```python
        for row in reader:
            total_rows += 1
```

- Iterating `reader` in a `for` loop pulls **one row at a time** from disk —
  this is the mechanism that satisfies "read the file one row at a time, do
  not load the entire file into memory." Internally, `DictReader` reads a
  chunk, parses one line into a dict, yields it, and only reads the next
  chunk when asked — it never materializes all 100,000 rows as a Python list.
- `total_rows` counts every row read, valid or not — matching the assignment
  requirement to report total row count including bad ones.

```python
            skip_reason = validate_row(row)
            if skip_reason:
                skipped_rows += 1
                errfile.write(f"SKIPPED [transaction_id={row['transaction_id']}] reason={skip_reason}\n")
                continue
```

- Calls the validator from earlier. If it returns a non-empty string (truthy),
  the row is bad: increment the counter, write one line to `errors.log` in
  the exact format the assignment specifies, then `continue` — which skips
  straight to the next loop iteration, bypassing all the aggregation code
  below for this row.
- Note the explicit `\n` at the end of the `write()` call — unlike `print()`,
  `file.write()` does **not** add a newline automatically.

```python
            quantity = int(row["quantity"])
            unit_price = float(row["unit_price"])
            total_price = quantity * unit_price
            if total_price < MIN_TOTAL_PRICE:
                continue
```

- Only reached for rows that passed validation, so these conversions are now
  safe to do without a `try/except` — the risky cases were already filtered
  out.
- `total_price = quantity * unit_price` is Task 2's core formula.
- If the order is under $50, `continue` skips aggregation for this row (but
  it was *not* counted as "skipped" in the error sense — it's excluded by
  business rule, not by bad data, so `skipped_rows` is untouched here).

```python
            product = row["product"]
            # Silently ignores any product outside KNOWN_PRODUCTS rather than
            # crashing or polluting the report with an unexpected category.
            if product in products:
                products[product]["revenue"] += total_price
                products[product]["units_sold"] += quantity
                products[product]["order_count"] += 1
```

- `product in products` checks dict **key** membership (`products` is
  `{"Laptop": {...}, "Mouse": {...}, ...}`), so this is `True` only if
  `product` is one of the 5 known names.
- The three `+=` lines mutate the nested dict in place: add this order's
  revenue to the running total, add its quantity to units sold, and increment
  the order count by exactly 1 (one row = one order, by this script's
  definition).

```python
    return products, total_rows, skipped_rows
```

- Returns a 3-tuple. Note this line is *outside* (dedented from) the `with`
  block — it runs after both files have been closed, but the local variables
  (`products`, `total_rows`, `skipped_rows`) built inside the block are still
  in scope, since Python's `with` block does not create a new local scope
  (unlike, say, a function).

### Lines 104–116 — `build_report_rows(products)`

```python
def build_report_rows(products):
    """Turns per-product stats into report rows, sorted by revenue descending."""
    report_rows = [
        {
            "product": product,
            "total_revenue": stats["revenue"],
            "total_units": stats["units_sold"],
            "avg_order_value": stats["revenue"] / stats["order_count"] if stats["order_count"] > 0 else 0.0,
        }
        for product, stats in products.items()
    ]
```

- This is a **list comprehension** producing a list of dicts (one dict per
  product), the shape `write_report` expects.
- `products.items()` iterates `(key, value)` pairs — here `(product_name,
  stats_dict)`.
- `stats["revenue"] / stats["order_count"] if stats["order_count"] > 0 else
  0.0` is a **conditional expression** (a.k.a. ternary): `A if condition else
  B`. It guards against **division by zero** — if a product had zero
  qualifying orders (e.g. every Mouse order happened to be under $50, or no
  Mouse rows existed at all), `order_count` would be `0`, and dividing by it
  would raise `ZeroDivisionError`. This makes the average safely default to
  `0.0` instead.

```python
    report_rows.sort(key=lambda row: row["total_revenue"], reverse=True)
    return report_rows
```

- `.sort()` sorts the list **in place** (mutates `report_rows`, returns
  `None` itself — which is why we call `.sort()` on its own line, then
  `return report_rows` separately, rather than `return report_rows.sort(...)`
  which would incorrectly return `None`).
- `key=lambda row: row["total_revenue"]` — a **lambda** is an anonymous
  inline function. `sort`'s `key` parameter tells it *what to compare* for
  each element rather than comparing the dicts themselves directly (dicts
  aren't inherently orderable/comparable with `<`).
- `reverse=True` sorts highest-to-lowest, satisfying "sort by total_revenue
  from HIGHEST to LOWEST."

### Lines 119–135 — `write_report(report_rows, output_path)`

```python
def write_report(report_rows, output_path):
    """Writes report_rows to a CSV at output_path, rounding money fields to 2 decimals."""
    headers = ["product", "total_revenue", "total_units", "avg_order_value"]
    with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
```

- `csv.DictWriter` is the write-side counterpart to `DictReader`: give it
  dicts, it writes CSV rows in the column order given by `fieldnames`
  (regardless of the dict's internal key order — dicts passed to `writerow`
  are matched by key, not position).
- `writer.writeheader()` writes the header row (`product,total_revenue,...`)
  using the `fieldnames` list, satisfying "the first line must be the header
  row."

```python
        for row in report_rows:
            # Round only here, at the output boundary, so upstream sums/averages
            # stay at full float precision rather than compounding rounding error.
            writer.writerow(
                {
                    "product": row["product"],
                    "total_revenue": f"{row['total_revenue']:.2f}",
                    "total_units": row["total_units"],
                    "avg_order_value": f"{row['avg_order_value']:.2f}",
                }
            )
```

- `f"{row['total_revenue']:.2f}"` — the `:.2f` is a **format spec** inside an
  f-string: format the value as a fixed-point float with exactly 2 digits
  after the decimal. This both rounds *and* pads (e.g. `5.0` becomes
  `"5.00"`), satisfying "round to 2 decimal places."
  - Note this produces a **string**, not a float — that's fine and in fact
    desirable for CSV output, since we want the literal text `"2999.62"` to
    appear in the file, not a Python float repr that could show extra digits
    or scientific notation for large/small numbers.
- `total_units` is written as-is (an `int`) — it's a count, not money, so it
  isn't rounded.

### Lines 138–149 — `main()`

```python
def main():
    """Runs the full pipeline: validate input exists, process sales.csv, write report.csv."""
    if not os.path.isfile(INPUT_CSV_FILE):
        print("File does not exist")
        sys.exit(1)
```

- `os.path.isfile(...)` returns `True` only if the path exists **and** is a
  regular file (not a directory). Checked before attempting to open it, to
  give a clean error message rather than an `FileNotFoundError` traceback.

```python
    products, total_rows, skipped_rows = process_sales(INPUT_CSV_FILE, ERROR_LOG_FILE)
    report_rows = build_report_rows(products)
    write_report(report_rows, OUTPUT_CSV_FILE)

    print("Total rows:", total_rows)
    print("Skipped rows:", skipped_rows)
```

- This is **tuple unpacking**: `process_sales` returns a 3-tuple, and the
  three names on the left are bound to its three elements in order.
- The three calls form a simple **pipeline**: read+aggregate → shape+sort →
  write. Each function does exactly one job and hands a plain data structure
  (dict, then list-of-dicts) to the next, rather than one function doing
  everything.
- `print("Total rows:", total_rows)` — `print` with multiple arguments joins
  them with a space automatically, so this prints `Total rows: 100000`
  without needing string concatenation or an f-string.

### Lines 152–153 — entry point guard

```python
if __name__ == "__main__":
    main()
```

- Every Python module has a built-in `__name__` variable. When you *run* a
  file directly (`python3 main.py`), Python sets `__name__` to the string
  `"__main__"` for that file. If the file is instead **imported** by another
  module (`import main`), `__name__` is set to `"main"` (the module name)
  instead.
- This guard means: `main()` only executes automatically when the file is run
  directly, not when it's imported elsewhere (e.g. by a test file that wants
  to import `validate_row` without triggering the whole pipeline as a side
  effect of the import). This is the standard Python idiom for "this is a
  script, but also a safely importable module."

---

## 2. Design decisions — the "why" behind the structure

| Decision | Why |
|---|---|
| Functions instead of one long top-level script | Each function is independently testable/readable; no shared mutable globals to reason about |
| `load_products()` returns a fresh dict each call | Prevents state leaking between repeated calls in the same process (e.g. tests) |
| Validation is a separate function from aggregation | Single Responsibility — `validate_row` only judges, never mutates state |
| Validate *before* casting to `int`/`float` in the main loop | The cast is exactly where a bad row would crash the program; validating first turns a crash into a clean, logged skip |
| Unknown products silently ignored (`if product in products`) | Matches the assignment's fixed 5-product scope; a stray/typo'd product name shouldn't blow up the report |
| Round only at the CSV-writing boundary | Avoids compounding rounding error across 100k additions — you always want to round the final displayed number, not intermediate sums |
| `errors.log` opened with `mode="w"` | Each run should reflect the current data, not accumulate log lines from old runs |
| Row-by-row iteration via `DictReader`, never `list(reader)` | Satisfies the "don't load the whole file into memory" requirement — memory use is O(1) relative to file size |
| `sys.exit(1)` on bad input/schema | Distinguishes "this ran and failed" (exit code 1) from "this ran and succeeded" (exit code 0) for anything scripting around this tool |

---

## 3. Likely mentor questions, with answers

**Q: What's the time complexity?**
O(n) where n = number of rows. Every row is visited exactly once; aggregation
per row is O(1) dict lookups/updates. Sorting the final report is O(k log k)
where k = number of products (5), negligible.

**Q: What's the space complexity?**
O(1) relative to the input file size — the CSV is streamed row-by-row, not
loaded as a list. The only memory that grows with input is `errors.log`'s
buffered writes (handled by the OS/file buffering, not by Python holding rows
in memory) and the fixed 5-entry `products` dict.

**Q: Why `DictReader`/`DictWriter` instead of the plain `csv.reader`/`writer`?**
Column-name-based access (`row["quantity"]`) is more robust to column
reordering than positional access (`row[4]`), and self-documents what each
field means at the call site.

**Q: What happens if `quantity` is a float string like `"2.5"`?**
`int("2.5")` raises `ValueError` (Python's `int()` does not parse decimal
strings), so it would be caught and logged as `non-numeric quantity (2.5)`.
This is a known simplification — the assignment's bad-data types don't
include this case, so it's treated the same as any other non-numeric string.

**Q: What happens if `unit_price` is negative?**
It isn't checked — only quantity's sign is validated, per the assignment
spec. A negative price would flow through and produce a negative
`total_price`, which would then almost certainly be filtered out by the
`< MIN_TOTAL_PRICE` check (since a negative number is always less than 50).

**Q: Why does `total_rows` include skipped/filtered rows, but the per-product
stats don't?**
`total_rows` answers "how many rows did we read from the file" (Task 1).
`skipped_rows` answers "how many were unusable" (Task 4). The per-product
aggregates only reflect rows that were both valid *and* met the $50 order
minimum (Task 2) — three different, deliberately distinct counters.

**Q: Why is the `$50` filter not counted as a "skip" in `errors.log`?**
Because it isn't bad data — it's a valid, well-formed transaction that the
business chose to exclude from the summary for being too small. `errors.log`
is reserved for data-quality problems, not business-rule exclusions.

**Q: Could you use `pandas` instead?**
Yes, and it would be shorter (`pd.read_csv`, `groupby`, `sum`), but it loads
the whole file into memory by default (violating Task 1's constraint) unless
you explicitly use chunked reading, and it's a much heavier dependency for
what is fundamentally a simple streaming aggregation. The stdlib `csv` module
keeps this dependency-free and memory-bounded by construction.

**Q: How would you test this?**
Unit-test `validate_row` directly with hand-built dict rows for each bad-data
case (missing product, missing/negative quantity, non-numeric price, and a
fully valid row). Unit-test `build_report_rows` with a small fake `products`
dict, including a product with `order_count == 0` to check the
division-by-zero guard. For `process_sales`/`write_report`, use a small
temp CSV fixture rather than the full 100k-row `sales.csv`.

**Q: What would you change for a "production" version of this?**
Make paths configurable via CLI args instead of hardcoded constants; use
`Decimal` instead of `float` for money to avoid floating-point rounding
artifacts at scale; add logging instead of bare `print`; consider making
`KNOWN_PRODUCTS` dynamic (discovered from the data) instead of hardcoded, if
the product catalog were expected to change.
