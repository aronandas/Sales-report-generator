"""Aggregates sales.csv into a per-product report.csv, logging any skipped bad rows to errors.log."""

import csv
import os
import sys

INPUT_CSV_FILE = "sales.csv"
OUTPUT_CSV_FILE = "report.csv"
ERROR_LOG_FILE = "errors.log"
MIN_TOTAL_PRICE = 50.0

EXPECTED_COLUMNS = [
    "transaction_id",
    "date",
    "product",
    "region",
    "quantity",
    "unit_price",
]

KNOWN_PRODUCTS = ["Laptop", "Mouse", "Keyboard", "Monitor", "Headset"]


def load_products():
    """Fresh per-product stats dict: revenue, units_sold, order_count."""
    result = {}
    for product in KNOWN_PRODUCTS:
        result[product] = {"revenue": 0.0, "units_sold": 0, "order_count": 0}
    return result


def validate_row(row):
    """Returns None if the row is usable, otherwise a reason string for errors.log."""
    if not row["product"]: #Python treats empty strings as false
        return "missing product name"

    quantity_raw = row["quantity"]
    if not quantity_raw:
        return "missing quantity"
    try:
        quantity = int(quantity_raw)
    except ValueError:
        return f"non-numeric quantity ({quantity_raw})" #f-string — the part is evaluated and interpolated into the string at runtime
    if quantity < 0:
        return f"negative quantity ({quantity})"

    price_raw = row["unit_price"]
    try:
        float(price_raw)
    except ValueError:
        return f"non-numeric unit_price ({price_raw})"

    return None


def process_sales(input_path, error_log_path):
    """Reads the sales CSV row by row, validates it, and aggregates per-product stats.

    Returns (products, total_rows, skipped_rows).
    """
    products = load_products()
    total_rows = 0
    skipped_rows = 0

    with open(input_path, newline="", encoding="utf-8") as csvfile, \
         open(error_log_path, mode="w", encoding="utf-8") as errfile:
        reader = csv.DictReader(csvfile)
        # Guards against silent column-order/name drift: DictReader maps by header name,
        # so a reordered or renamed column would otherwise read the wrong field silently.
        if reader.fieldnames != EXPECTED_COLUMNS:
            print("CSV file columns do not match the expected columns")
            sys.exit(1)

        # Iterating the reader yields one row at a time, so memory stays flat
        # regardless of file size (matters for the 100k-row input).
        for row in reader:
            total_rows += 1
            
            # Must validate before int()/float() conversion below, since a bad row
            # (empty or non-numeric quantity/price) would otherwise raise and crash the run.
            skip_reason = validate_row(row)
            if skip_reason:
                skipped_rows += 1
                errfile.write(f"SKIPPED [transaction_id={row['transaction_id']}] reason={skip_reason}\n")
                continue

            quantity = int(row["quantity"])
            unit_price = float(row["unit_price"])
            total_price = quantity * unit_price
            if total_price < MIN_TOTAL_PRICE:
                continue

            product = row["product"]
            # Silently ignores any product outside KNOWN_PRODUCTS rather than
            # crashing or polluting the report with an unexpected category.
            if product in products:
                products[product]["revenue"] += total_price
                products[product]["units_sold"] += quantity
                products[product]["order_count"] += 1

    return products, total_rows, skipped_rows


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
    report_rows.sort(key=lambda row: row["total_revenue"], reverse=True)
    return report_rows


def write_report(report_rows, output_path):
    """Writes report_rows to a CSV at output_path, rounding money fields to 2 decimals."""
    headers = ["product", "total_revenue", "total_units", "avg_order_value"]
    with open(output_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
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


def main():
    """Runs the full pipeline: validate input exists, process sales.csv, write report.csv."""
    if not os.path.isfile(INPUT_CSV_FILE):
        print("File does not exist")
        sys.exit(1)

    products, total_rows, skipped_rows = process_sales(INPUT_CSV_FILE, ERROR_LOG_FILE)
    report_rows = build_report_rows(products)
    write_report(report_rows, OUTPUT_CSV_FILE)

    print("Total rows:", total_rows)
    print("Skipped rows:", skipped_rows)


if __name__ == "__main__":
    main()
