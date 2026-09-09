# generate_data.py
import csv
import random
import uuid
from datetime import date, timedelta

products = ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Headset']
regions = ['North', 'South', 'East', 'West']

total_rows = 100000
bad_rows_target = 489

# Pre-determine unique row indices to inject with bad data
bad_row_indices = set(random.sample(range(total_rows), bad_rows_target))

with open('sales.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['transaction_id', 'date', 'product', 'region', 'quantity', 'unit_price'])
    
    start = date(2024, 1, 1)
    
    for i in range(total_rows):
        d = start + timedelta(days=random.randint(0, 364))
        product = random.choice(products)
        price = {'Laptop': 999.99, 'Mouse': 29.99, 'Keyboard': 79.99, 'Monitor': 349.99, 'Headset': 89.99}[product]
        qty = random.randint(1, 5)
        region = random.choice(regions)
        
        # Inject an anomaly if the current row index matches our target list
        if i in bad_row_indices:
            anomaly_type = random.randint(1, 4)
            if anomaly_type == 1:
                product = ""      # Missing product name
            elif anomaly_type == 2:
                qty = -qty         # Negative quantity
            elif anomaly_type == 3:
                price = "N/A"      # Non-numeric unit price
            elif anomaly_type == 4:
                qty = ""           # Missing quantity
                
        writer.writerow([str(uuid.uuid4()), d, product, region, qty, price])
