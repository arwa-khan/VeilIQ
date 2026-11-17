"""
Generate a synthetic hijab retail dataset (customers, products, orders, order items).

The data is synthetic, built with realistic patterns so the SQL analysis has something
meaningful to find:
  - fabrics with different price ranges and seasonal demand (chiffon in summer, wool blends in winter)
  - demand spikes before Eid (Ramadan and Eid al-Adha) and back-to-school
  - a mix of loyal repeat customers and one-time buyers who churn over time
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).parent

FABRICS = {
    # fabric: (price range, monthly demand weights Jan..Dec)
    "Chiffon":    ((18, 35), [0.6, 0.7, 1.2, 1.3, 1.5, 1.6, 1.6, 1.3, 0.9, 0.7, 0.6, 0.6]),
    "Jersey":     ((15, 28), [1.0, 1.0, 1.2, 1.2, 1.0, 1.0, 1.0, 1.4, 1.5, 1.1, 1.0, 1.0]),
    "Modal":      ((20, 38), [0.9, 0.9, 1.1, 1.1, 1.1, 1.1, 1.1, 1.2, 1.2, 1.0, 0.9, 0.9]),
    "Silk":       ((40, 85), [0.6, 0.7, 1.6, 1.8, 0.8, 1.4, 0.7, 0.6, 0.6, 0.7, 1.0, 1.5]),
    "Satin":      ((25, 50), [0.6, 0.7, 1.5, 1.6, 0.8, 1.3, 0.7, 0.6, 0.7, 0.8, 1.0, 1.4]),
    "Wool Blend": ((30, 60), [1.7, 1.4, 0.9, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 1.4, 1.8, 1.9]),
}
COLOURS = ["Black", "Nude", "Navy", "Sage", "Dusty Rose", "Ivory", "Mocha", "Burgundy"]
COLOUR_WEIGHTS = [3.0, 2.5, 1.5, 1.2, 1.3, 1.0, 1.4, 0.9]
COLLECTIONS = {  # month -> seasonal collection
    1: "Winter", 2: "Winter", 3: "Ramadan & Eid", 4: "Ramadan & Eid", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Back to School", 9: "Back to School",
    10: "Fall", 11: "Fall", 12: "Winter",
}

def write(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

# Products: each style is a fabric + colour combination
products, pid = [], 1
for fabric, ((lo, hi), _) in FABRICS.items():
    for colour in COLOURS:
        products.append((pid, f"{colour} {fabric} Hijab", fabric, colour, round(random.uniform(lo, hi), 2)))
        pid += 1
write("products.csv", ["product_id", "product_name", "fabric", "colour", "unit_price"], products)

# Customers
start, end = date(2024, 1, 1), date(2025, 12, 31)
customers = []
for cid in range(1, 2001):
    signup = start + timedelta(days=random.randint(0, 600))
    customers.append((cid, signup.isoformat(), random.choice(["Ontario", "Quebec", "BC", "Alberta", "Other"])))
write("customers.csv", ["customer_id", "signup_date", "region"], customers)

# Orders + items
orders, items, oid, iid = [], [], 1, 1
loyalty = {c[0]: random.random() ** 2 for c in customers}
colour_w = dict(zip(COLOURS, COLOUR_WEIGHTS))
for cid, signup, _ in customers:
    d = date.fromisoformat(signup)
    active_until = min(end, d + timedelta(days=int(random.expovariate(1 / 240))))
    first = True
    while d <= active_until:
        if first or random.random() < 0.1 + 0.6 * loyalty[cid]:
            first = False
            orders.append((oid, cid, d.isoformat(), d.strftime("%Y-%m"), COLLECTIONS[d.month]))
            for _ in range(random.randint(1, 4)):
                weights = [FABRICS[p[2]][1][d.month - 1] * colour_w[p[3]] for p in products]
                p = random.choices(products, weights=weights)[0]
                qty = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
                discount = random.choices([0, 0.1, 0.2, 0.3], weights=[0.6, 0.2, 0.15, 0.05])[0]
                items.append((iid, oid, p[0], qty, round(p[4] * (1 - discount), 2)))
                iid += 1
            oid += 1
        d += timedelta(days=random.randint(20, 90))
write("orders.csv", ["order_id", "customer_id", "order_date", "order_month", "collection"], orders)
write("order_items.csv", ["order_item_id", "order_id", "product_id", "quantity", "sale_price"], items)
print(f"{len(customers)} customers, {len(products)} styles, {len(orders)} orders, {len(items)} order items")
