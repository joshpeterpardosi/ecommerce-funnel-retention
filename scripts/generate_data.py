import numpy as np
import pandas as pd
from pathlib import Path

def generate_datasets(output_dir: str = "data", total_events: int = 500_000, num_customers: int = 25_000):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    np.random.seed(42)
    
    print(f"Generating {num_customers:,} customers...")
    customer_ids = [f"CUST_{i:05d}" for i in range(1, num_customers + 1)]
    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp("2026-07-31")
    
    random_days = np.random.randint(0, (end_date - start_date).days, size=num_customers)
    signup_dates = start_date + pd.to_timedelta(random_days, unit="D")
    
    countries = np.random.choice(["US", "UK", "CA", "DE", "FR", "AU"], size=num_customers, p=[0.45, 0.15, 0.10, 0.10, 0.10, 0.10])
    devices = np.random.choice(["mobile", "desktop", "tablet"], size=num_customers, p=[0.60, 0.32, 0.08])
    channels = np.random.choice(["Paid Search", "Organic", "Social Media", "Email", "Referral"], size=num_customers, p=[0.30, 0.25, 0.25, 0.10, 0.10])
    
    df_customers = pd.DataFrame({
        "customer_id": customer_ids,
        "signup_date": signup_dates,
        "country": pd.Categorical(countries),
        "device_category": pd.Categorical(devices),
        "acquisition_channel": pd.Categorical(channels)
    })
    
    df_customers.to_parquet(out_path / "customers.parquet", index=False)
    print(f"Saved customers.parquet ({len(df_customers):,} rows)")
    
    print(f"Generating {total_events:,} funnel events...")
    cust_indices = np.random.randint(0, num_customers, size=total_events)
    cust_id_lookup = np.asarray(customer_ids)
    base_signup = signup_dates.values[cust_indices]

    added_seconds = np.random.randint(0, 180 * 86400, size=total_events)
    event_timestamps = pd.to_datetime(base_signup) + pd.to_timedelta(added_seconds, unit="s")

    # Store repeated string keys as Categorical: 500k rows collapse to int codes
    # plus a small category index, instead of 500k separate Python strings.
    assigned_cust_ids = pd.Categorical.from_codes(cust_indices, categories=cust_id_lookup)

    session_num = np.random.randint(1, 10, size=total_events)
    session_ids = pd.Categorical(
        np.char.add(
            np.char.add(np.char.add("SESS_", cust_id_lookup[cust_indices]), "_"),
            session_num.astype(str),
        )
    )
    
    event_types = np.random.choice(
        ["page_view", "product_view", "add_to_cart", "checkout_start", "purchase"],
        size=total_events,
        p=[0.45, 0.30, 0.13, 0.08, 0.04]
    )
    
    page_category_map = {
        "page_view": "home",
        "product_view": "product_detail",
        "add_to_cart": "cart",
        "checkout_start": "checkout",
        "purchase": "thank_you"
    }
    event_types = pd.Categorical(event_types)
    page_categories = pd.Categorical(
        event_types.rename_categories(page_category_map)
    )

    event_devices = np.random.choice(["mobile", "desktop", "tablet"], size=total_events, p=[0.58, 0.34, 0.08])

    event_ids = np.char.add("EVT_", np.char.zfill(np.arange(1, total_events + 1).astype(str), 7))

    df_events = pd.DataFrame({
        "event_id": event_ids,
        "customer_id": assigned_cust_ids,
        "session_id": session_ids,
        "timestamp": event_timestamps,
        "event_type": pd.Categorical(event_types),
        "device": pd.Categorical(event_devices),
        "page_category": pd.Categorical(page_categories)
    }).sort_values("timestamp").reset_index(drop=True)
    
    df_events.to_parquet(out_path / "events.parquet", index=False)
    print(f"Saved events.parquet ({len(df_events):,} rows)")
    
    print("Generating transactions from purchase events...")
    purchases = df_events[df_events["event_type"] == "purchase"].copy()
    num_txns = len(purchases)
    
    amounts = np.random.lognormal(mean=3.8, sigma=0.6, size=num_txns).round(2).astype("float32")
    amounts = np.clip(amounts, 10.0, 999.0)
    payment_methods = np.random.choice(["Credit Card", "PayPal", "Apple Pay", "Klarna"], size=num_txns, p=[0.50, 0.25, 0.15, 0.10])
    statuses = np.random.choice(["Completed", "Refunded", "Failed"], size=num_txns, p=[0.92, 0.05, 0.03])
    
    df_transactions = pd.DataFrame({
        "transaction_id": [f"TXN_{i:06d}" for i in range(1, num_txns + 1)],
        "customer_id": purchases["customer_id"].values,
        "transaction_timestamp": purchases["timestamp"].values,
        "amount": amounts,
        "payment_method": pd.Categorical(payment_methods),
        "status": pd.Categorical(statuses)
    })
    
    df_transactions.to_parquet(out_path / "transactions.parquet", index=False)
    print(f"Saved transactions.parquet ({len(df_transactions):,} rows)")

if __name__ == "__main__":
    generate_datasets()
