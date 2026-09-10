# Sales Report Generator

Generates a synthetic sales dataset, then processes it into a per-product revenue report while validating and logging bad rows.

## What it does

1. **`generate_data.py`** — creates `sales.csv` with 100,000 rows of synthetic sales transactions (product, region, quantity, unit price). Deliberately injects ~489 bad rows (missing product, negative quantity, non-numeric price, missing quantity) to simulate dirty data.
2. **`main.py`** — reads `sales.csv`, validates each row, skips and logs any bad rows to `errors.log`, then aggregates valid transactions per product (only orders with total price ≥ $50 count) and writes the result to `report.csv`.

## Usage

```bash
# 1. Generate the sales data
python3 generate_data.py

# 2. Run the report pipeline
python3 main.py
```

## Output

**`report.csv`** — one row per product, sorted by revenue descending:

| Column | Description |
|---|---|
| `product` | Product name |
| `total_revenue` | Sum of `quantity * unit_price` across valid orders |
| `total_units` | Total units sold |
| `avg_order_value` | `total_revenue / order_count` |

**`errors.log`** — one line per skipped row, with the transaction ID and the reason it was skipped (e.g. missing product, negative quantity, non-numeric price).

Console output reports total rows processed and how many were skipped.

## Requirements

Python 3, standard library only (`csv`, `random`, `uuid`, `datetime`).
