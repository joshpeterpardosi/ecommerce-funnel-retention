"""Synthetic e-commerce clickstream generator.

Events are built session by session rather than sampled independently, so each
session contains a coherent journey: a customer views pages, then maybe products,
then maybe carts, checks out and purchases — always in that order, with strictly
increasing timestamps. That matters because sql/funnel.sql only credits a stage
when it happens *after* the preceding stage inside the same session.

Each customer is assigned a maximum stage they will ever reach, drawn from an
intent distribution. Because that ceiling is per-customer rather than per-session,
session volume can be tuned to hit an event target without distorting the
distinct-customer conversion rates the dashboard reports.
"""

import numpy as np
import pandas as pd
from pathlib import Path

FUNNEL_STAGES = ["page_view", "product_view", "add_to_cart", "checkout_start", "purchase"]

PAGE_CATEGORY_MAP = {
    "page_view": "home",
    "product_view": "product_detail",
    "add_to_cart": "cart",
    "checkout_start": "checkout",
    "purchase": "thank_you",
}

# Share of customers whose deepest-ever stage is 1..5. Cumulative reach is
# therefore 100 / 62 / 28 / 14 / 8 percent, a realistic retail funnel shape.
MAX_STAGE_WEIGHTS = [0.38, 0.34, 0.14, 0.06, 0.08]


def generate_datasets(
    output_dir: str = "data",
    total_events: int = 500_000,
    num_customers: int = 25_000,
) -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)

    # ------------------------------------------------------------- customers
    print(f"Generating {num_customers:,} customers...")
    customer_ids = np.array([f"CUST_{i:05d}" for i in range(1, num_customers + 1)])
    start_date = pd.Timestamp("2025-01-01")
    end_date = pd.Timestamp("2026-07-31")

    signup_dates = start_date + pd.to_timedelta(
        rng.integers(0, (end_date - start_date).days, size=num_customers), unit="D"
    )
    countries = rng.choice(["US", "UK", "CA", "DE", "FR", "AU"], size=num_customers, p=[0.45, 0.15, 0.10, 0.10, 0.10, 0.10])
    devices = rng.choice(["mobile", "desktop", "tablet"], size=num_customers, p=[0.60, 0.32, 0.08])
    channels = rng.choice(["Paid Search", "Organic", "Social Media", "Email", "Referral"], size=num_customers, p=[0.30, 0.25, 0.25, 0.10, 0.10])

    df_customers = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "signup_date": signup_dates,
            "country": pd.Categorical(countries),
            "device_category": pd.Categorical(devices),
            "acquisition_channel": pd.Categorical(channels),
        }
    )
    df_customers.to_parquet(out_path / "customers.parquet", index=False)
    print(f"Saved customers.parquet ({len(df_customers):,} rows)")

    # -------------------------------------------------------------- sessions
    # Deepest stage each customer will ever reach.
    customer_max_stage = rng.choice([1, 2, 3, 4, 5], size=num_customers, p=MAX_STAGE_WEIGHTS)

    # Average events per session, derived from the stage mix, so session volume
    # can be solved for the requested event target.
    events_by_stage = np.array([2.0, 4.0, 5.0, 6.0, 7.0])  # avg events when a session ends at stage i
    avg_events = float(np.mean(events_by_stage[customer_max_stage - 1]) * 0.75 + events_by_stage[0] * 0.25)
    sessions_per_customer = max(1, round(total_events / (avg_events * num_customers)))

    # Upper bound is exclusive, so this averages sessions_per_customer exactly.
    n_sessions = rng.integers(1, 2 * sessions_per_customer, size=num_customers)
    session_customer_idx = np.repeat(np.arange(num_customers), n_sessions)
    total_sessions = session_customer_idx.size
    print(f"Generating ~{total_events:,} events across {total_sessions:,} sessions...")

    cust_ceiling = customer_max_stage[session_customer_idx]
    # Half the sessions go as deep as the customer ever gets; the rest fall short.
    session_max = np.where(
        rng.random(total_sessions) < 0.5,
        cust_ceiling,
        rng.integers(1, cust_ceiling + 1),
    )
    # Guarantee each customer actually attains their ceiling at least once.
    first_session_of_customer = np.concatenate(([0], np.cumsum(n_sessions)[:-1]))
    session_max[first_session_of_customer] = customer_max_stage

    # ---------------------------------------------------------------- events
    # Repeat browsing stages a few times per session; commit stages happen once.
    repeats = np.ones((total_sessions, 5), dtype=np.int64)
    repeats[:, 0] = rng.integers(1, 4, size=total_sessions)  # page_view
    repeats[:, 1] = rng.integers(1, 4, size=total_sessions)  # product_view
    reached = np.arange(1, 6)[None, :] <= session_max[:, None]
    repeats = np.where(reached, repeats, 0)

    session_col, stage_col = [], []
    for stage in range(5):
        counts = repeats[:, stage]
        session_col.append(np.repeat(np.arange(total_sessions), counts))
        stage_col.append(np.full(int(counts.sum()), stage + 1, dtype=np.int64))

    ev_session = np.concatenate(session_col)
    ev_stage = np.concatenate(stage_col)

    # Order events within each session by stage, then space them out in time so
    # every stage strictly follows the one before it.
    order = np.lexsort((ev_stage, ev_session))
    ev_session, ev_stage = ev_session[order], ev_stage[order]

    # Offsets must be a running total of the gaps, not index * gap: the latter
    # lets a later event draw a small gap and land before an earlier one, which
    # would break the chronological ordering sql/funnel.sql depends on.
    gaps = rng.integers(30, 600, size=ev_session.size)  # 0.5-10 min between hits
    offsets = pd.Series(gaps).groupby(ev_session).cumsum().to_numpy() - gaps

    session_start = (
        signup_dates.values[session_customer_idx]
        + pd.to_timedelta(rng.integers(0, 180 * 86400, size=total_sessions), unit="s")
    )
    ev_timestamp = pd.to_datetime(session_start[ev_session]) + pd.to_timedelta(offsets, unit="s")

    n_events = ev_session.size
    ev_customer_idx = session_customer_idx[ev_session]
    event_types = np.array(FUNNEL_STAGES)[ev_stage - 1]

    df_events = pd.DataFrame(
        {
            "event_id": np.char.add("EVT_", np.char.zfill(np.arange(1, n_events + 1).astype(str), 7)),
            "customer_id": pd.Categorical.from_codes(ev_customer_idx, categories=customer_ids),
            "session_id": pd.Categorical(
                np.char.add("SESS_", np.char.zfill(ev_session.astype(str), 7))
            ),
            "timestamp": ev_timestamp,
            "event_type": pd.Categorical(event_types, categories=FUNNEL_STAGES),
            # Device is a property of the customer, so the per-device funnels
            # partition the customer base instead of double-counting it.
            "device": pd.Categorical(devices[ev_customer_idx]),
            "page_category": pd.Categorical(
                pd.Categorical(event_types, categories=FUNNEL_STAGES).rename_categories(PAGE_CATEGORY_MAP)
            ),
        }
    ).sort_values("timestamp").reset_index(drop=True)

    df_events.to_parquet(out_path / "events.parquet", index=False)
    print(f"Saved events.parquet ({len(df_events):,} rows)")

    # ---------------------------------------------------------- transactions
    print("Generating transactions from purchase events...")
    purchases = df_events[df_events["event_type"] == "purchase"]
    num_txns = len(purchases)

    amounts = np.clip(rng.lognormal(mean=3.8, sigma=0.6, size=num_txns).round(2), 10.0, 999.0).astype("float32")
    payment_methods = rng.choice(["Credit Card", "PayPal", "Apple Pay", "Klarna"], size=num_txns, p=[0.50, 0.25, 0.15, 0.10])
    statuses = rng.choice(["Completed", "Refunded", "Failed"], size=num_txns, p=[0.92, 0.05, 0.03])

    df_transactions = pd.DataFrame(
        {
            "transaction_id": np.char.add("TXN_", np.char.zfill(np.arange(1, num_txns + 1).astype(str), 6)),
            "customer_id": purchases["customer_id"].values,
            "transaction_timestamp": purchases["timestamp"].values,
            "amount": amounts,
            "payment_method": pd.Categorical(payment_methods),
            "status": pd.Categorical(statuses),
        }
    )
    df_transactions.to_parquet(out_path / "transactions.parquet", index=False)
    print(f"Saved transactions.parquet ({len(df_transactions):,} rows)")


if __name__ == "__main__":
    generate_datasets()
