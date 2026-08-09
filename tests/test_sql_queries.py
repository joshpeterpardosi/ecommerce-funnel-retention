"""Correctness tests for the DuckDB SQL that powers the dashboard.

These run the real, unmodified files in sql/ against tiny hand-built fixtures
whose expected answers were worked out by hand. Each test chdir's into a temp
directory holding its own data/*.parquet, so the queries' relative paths resolve
to the fixture instead of the production dataset.
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def run_sql(filename: str) -> pd.DataFrame:
    """Execute a query from sql/ against whatever data/ is in the cwd."""
    query = (SQL_DIR / filename).read_text(encoding="utf-8")
    return duckdb.connect().execute(query).df()


def write_fixture(root: Path, customers=None, events=None, transactions=None) -> None:
    """Materialise the supplied frames as data/*.parquet under root."""
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in (
        ("customers", customers),
        ("events", events),
        ("transactions", transactions),
    ):
        if frame is not None:
            frame.to_parquet(data_dir / f"{name}.parquet", index=False)


def ts(day: int, hour: int = 0) -> pd.Timestamp:
    return pd.Timestamp("2025-01-01") + pd.Timedelta(days=day, hours=hour)


# ---------------------------------------------------------------- funnel.sql


@pytest.fixture
def funnel_data(tmp_path, monkeypatch):
    """Three desktop users and one mobile user with known stage progression.

    desktop: C1 completes all 5 stages, C2 stops after product_view,
             C3 only ever views a page.
    mobile:  C4 reaches add_to_cart.
    """
    rows = []

    def ev(eid, cust, sess, hour, etype, device):
        rows.append(
            {
                "event_id": eid,
                "customer_id": cust,
                "session_id": sess,
                "timestamp": ts(0, hour),
                "event_type": etype,
                "device": device,
                "page_category": "x",
            }
        )

    # C1 walks the full funnel in order
    for i, stage in enumerate(
        ["page_view", "product_view", "add_to_cart", "checkout_start", "purchase"]
    ):
        ev(f"E1{i}", "C1", "S1", i, stage, "desktop")
    # C2 drops after product_view
    ev("E20", "C2", "S2", 0, "page_view", "desktop")
    ev("E21", "C2", "S2", 1, "product_view", "desktop")
    # C3 never leaves the landing page
    ev("E30", "C3", "S3", 0, "page_view", "desktop")
    # C4 on mobile reaches the cart
    ev("E40", "C4", "S4", 0, "page_view", "mobile")
    ev("E41", "C4", "S4", 1, "product_view", "mobile")
    ev("E42", "C4", "S4", 2, "add_to_cart", "mobile")

    write_fixture(tmp_path, events=pd.DataFrame(rows))
    monkeypatch.chdir(tmp_path)


def test_funnel_counts_unique_users_per_device_stage(funnel_data):
    df = run_sql("funnel.sql").set_index(["device", "stage_order"])

    # desktop: 3 land, 2 view a product, 1 carts/checks out/buys
    assert df.loc[("desktop", 1), "unique_users"] == 3
    assert df.loc[("desktop", 2), "unique_users"] == 2
    assert df.loc[("desktop", 3), "unique_users"] == 1
    assert df.loc[("desktop", 4), "unique_users"] == 1
    assert df.loc[("desktop", 5), "unique_users"] == 1

    # mobile: one user who stops at add_to_cart
    assert df.loc[("mobile", 1), "unique_users"] == 1
    assert df.loc[("mobile", 3), "unique_users"] == 1
    assert df.loc[("mobile", 4), "unique_users"] == 0
    assert df.loc[("mobile", 5), "unique_users"] == 0


def test_funnel_conversion_and_dropoff_math(funnel_data):
    df = run_sql("funnel.sql").set_index(["device", "stage_order"])

    # overall = stage / stage 1
    assert df.loc[("desktop", 1), "overall_conversion_pct"] == 100.0
    assert df.loc[("desktop", 2), "overall_conversion_pct"] == 66.67  # 2/3
    assert df.loc[("desktop", 3), "overall_conversion_pct"] == 33.33  # 1/3

    # step = stage / previous stage
    assert df.loc[("desktop", 2), "step_conversion_pct"] == 66.67  # 2/3
    assert df.loc[("desktop", 3), "step_conversion_pct"] == 50.0  # 1/2
    assert df.loc[("desktop", 4), "step_conversion_pct"] == 100.0  # 1/1

    # drop-off is the complement of step conversion
    assert df.loc[("desktop", 2), "dropoff_pct"] == 33.33
    assert df.loc[("desktop", 3), "dropoff_pct"] == 50.0

    # a stage nobody reaches is a total drop-off, not a null
    assert df.loc[("mobile", 4), "step_conversion_pct"] == 0.0
    assert df.loc[("mobile", 4), "dropoff_pct"] == 100.0


def test_funnel_requires_stages_in_chronological_order(tmp_path, monkeypatch):
    """A purchase timestamped before the page_view must not count.

    This is the sequencing guarantee the README advertises: reaching a stage
    means reaching it *after* the preceding one within the same session.
    """
    rows = [
        {
            "event_id": "A",
            "customer_id": "C1",
            "session_id": "S1",
            "timestamp": ts(0, 5),
            "event_type": "page_view",
            "device": "desktop",
            "page_category": "x",
        },
        {
            "event_id": "B",
            "customer_id": "C1",
            "session_id": "S1",
            "timestamp": ts(0, 1),  # earlier than the page_view above
            "event_type": "product_view",
            "device": "desktop",
            "page_category": "x",
        },
    ]
    write_fixture(tmp_path, events=pd.DataFrame(rows))
    monkeypatch.chdir(tmp_path)

    df = run_sql("funnel.sql").set_index(["device", "stage_order"])
    assert df.loc[("desktop", 1), "unique_users"] == 1
    assert df.loc[("desktop", 2), "unique_users"] == 0


# ------------------------------------------------------- cohort_retention.sql


def test_cohort_retention_matrix(tmp_path, monkeypatch):
    """C1 active Jan/Feb/Mar, C2 active Jan/Mar, C3 first seen in Feb.

    January cohort has 2 members: both active at offset 0, only C1 at
    offset 1, both again at offset 2.
    """
    rows = []
    for i, (cust, month) in enumerate(
        [
            ("C1", "2025-01-15"),
            ("C1", "2025-02-15"),
            ("C1", "2025-03-15"),
            ("C2", "2025-01-20"),
            ("C2", "2025-03-20"),
            ("C3", "2025-02-10"),
        ]
    ):
        rows.append(
            {
                "event_id": f"E{i}",
                "customer_id": cust,
                "session_id": f"S{i}",
                "timestamp": pd.Timestamp(month),
                "event_type": "page_view",
                "device": "desktop",
                "page_category": "x",
            }
        )
    write_fixture(tmp_path, events=pd.DataFrame(rows))
    monkeypatch.chdir(tmp_path)

    df = run_sql("cohort_retention.sql")
    df["cohort_month"] = pd.to_datetime(df["cohort_month"]).dt.strftime("%Y-%m")
    m = df.set_index(["cohort_month", "period_offset"])

    assert m.loc[("2025-01", 0), "initial_cohort_size"] == 2
    assert m.loc[("2025-01", 0), "active_users"] == 2
    assert m.loc[("2025-01", 0), "retention_rate_pct"] == 100.0
    assert m.loc[("2025-01", 1), "active_users"] == 1
    assert m.loc[("2025-01", 1), "retention_rate_pct"] == 50.0
    assert m.loc[("2025-01", 2), "active_users"] == 2
    assert m.loc[("2025-01", 2), "retention_rate_pct"] == 100.0

    # C3 forms its own February cohort and never returns
    assert m.loc[("2025-02", 0), "initial_cohort_size"] == 1
    assert ("2025-02", 1) not in m.index


# ------------------------------------------------------ rfm_segmentation.sql


def test_rfm_quartile_segmentation(tmp_path, monkeypatch):
    """Eight customers ranked cleanly 1-8 on all three RFM dimensions.

    With 8 rows NTILE(4) puts exactly 2 per quartile, so the top pair scores
    4/4/4 (Champions) and the next pair scores 3/3 (Loyal Customers).
    """
    rows = []
    txn = 0
    for i, cust in enumerate(["A", "B", "C", "D", "E", "F", "G", "H"]):
        n_txns = 8 - i  # A=8 ... H=1, so frequency and monetary both rank A top
        latest = pd.Timestamp("2025-06-01") - pd.Timedelta(days=i)
        for _ in range(n_txns):
            txn += 1
            rows.append(
                {
                    "transaction_id": f"T{txn:03d}",
                    "customer_id": cust,
                    "transaction_timestamp": latest,
                    "amount": 10.0,
                    "payment_method": "Credit Card",
                    "status": "Completed",
                }
            )
    write_fixture(tmp_path, transactions=pd.DataFrame(rows))
    monkeypatch.chdir(tmp_path)

    df = run_sql("rfm_segmentation.sql").set_index("rfm_segment")

    # A and B lead on recency, frequency and monetary simultaneously
    assert df.loc["Champions", "customer_count"] == 2
    assert df.loc["Champions", "avg_frequency"] == 7.5  # A=8, B=7
    assert df.loc["Champions", "total_segment_revenue"] == 150.0  # (8+7)*10

    # C and D sit in the third quartile on both R and F
    assert df.loc["Loyal Customers", "customer_count"] == 2

    # every customer lands in exactly one segment
    assert df["customer_count"].sum() == 8
    assert df["total_segment_revenue"].sum() == 360.0  # (8+7+...+1)*10


def test_rfm_ignores_non_completed_transactions(tmp_path, monkeypatch):
    rows = [
        {
            "transaction_id": "T1",
            "customer_id": "A",
            "transaction_timestamp": pd.Timestamp("2025-06-01"),
            "amount": 100.0,
            "payment_method": "Credit Card",
            "status": "Completed",
        },
        {
            "transaction_id": "T2",
            "customer_id": "A",
            "transaction_timestamp": pd.Timestamp("2025-06-02"),
            "amount": 999.0,
            "payment_method": "Credit Card",
            "status": "Refunded",
        },
        {
            "transaction_id": "T3",
            "customer_id": "B",
            "transaction_timestamp": pd.Timestamp("2025-06-02"),
            "amount": 500.0,
            "payment_method": "PayPal",
            "status": "Failed",
        },
    ]
    write_fixture(tmp_path, transactions=pd.DataFrame(rows))
    monkeypatch.chdir(tmp_path)

    df = run_sql("rfm_segmentation.sql")
    # Only A's completed $100 counts; the refund and the failure are excluded.
    assert df["customer_count"].sum() == 1
    assert df["total_segment_revenue"].sum() == 100.0


# ----------------------------------------------------------- data_quality.sql


def test_data_quality_audit_detects_each_defect_class(tmp_path, monkeypatch):
    """Fixture seeded with one of every defect the audit claims to catch.

    Critically, customers.parquet contains a NULL customer_id. Under the old
    `NOT IN (SELECT customer_id ...)` formulation that NULL made the predicate
    unknown for every row, so the orphan counts silently came back 0. This is
    the regression test for that fix.
    """
    customers = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", None],  # the NULL that broke NOT IN
            "signup_date": [ts(0), ts(0), ts(0)],
            "country": ["US", "UK", "US"],
            "device_category": ["mobile", "desktop", "mobile"],
            "acquisition_channel": ["Organic", "Email", "Organic"],
        }
    )
    events = pd.DataFrame(
        [
            {"event_id": "E1", "customer_id": "C1"},
            {"event_id": "E1", "customer_id": "C2"},  # duplicate event_id
            {"event_id": "E2", "customer_id": "ORPHAN"},  # no such customer
            {"event_id": "E3", "customer_id": None},  # null key
        ]
    ).assign(
        session_id="S1",
        timestamp=ts(0),
        event_type="page_view",
        device="desktop",
        page_category="x",
    )
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "T1",
                "customer_id": "C1",
                "transaction_timestamp": ts(0),
                "amount": 10.0,
                "payment_method": "Credit Card",
                "status": "Completed",
            },
            {
                "transaction_id": "T2",
                "customer_id": "ORPHAN2",  # no such customer
                "transaction_timestamp": ts(0),
                "amount": -5.0,  # invalid amount
                "payment_method": "PayPal",
                "status": "Completed",
            },
        ]
    )
    write_fixture(tmp_path, customers, events, transactions)
    monkeypatch.chdir(tmp_path)

    df = run_sql("data_quality.sql")
    # The UNION reuses the first branch's column names across all three rows.
    nulls, orphans, anomalies = df.iloc[0], df.iloc[1], df.iloc[2]

    assert nulls["missing_customer_ids"] == 1  # the NULL customer row
    assert nulls["missing_event_keys"] == 1  # E3 has no customer_id
    assert nulls["missing_txn_keys"] == 0

    assert orphans["missing_customer_ids"] == 1  # ORPHAN in events
    assert orphans["missing_event_keys"] == 1  # ORPHAN2 in transactions

    assert anomalies["missing_customer_ids"] == 1  # the -5.00 amount
    assert anomalies["missing_event_keys"] == 1  # duplicated E1


def test_data_quality_audit_is_clean_on_sound_data(tmp_path, monkeypatch):
    customers = pd.DataFrame(
        {
            "customer_id": ["C1"],
            "signup_date": [ts(0)],
            "country": ["US"],
            "device_category": ["mobile"],
            "acquisition_channel": ["Organic"],
        }
    )
    events = pd.DataFrame(
        [{"event_id": "E1", "customer_id": "C1"}]
    ).assign(
        session_id="S1",
        timestamp=ts(0),
        event_type="page_view",
        device="desktop",
        page_category="x",
    )
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "T1",
                "customer_id": "C1",
                "transaction_timestamp": ts(0),
                "amount": 10.0,
                "payment_method": "Credit Card",
                "status": "Completed",
            }
        ]
    )
    write_fixture(tmp_path, customers, events, transactions)
    monkeypatch.chdir(tmp_path)

    df = run_sql("data_quality.sql")
    numeric = df.select_dtypes(include="number")
    assert (numeric == 0).all().all(), f"clean data reported defects:\n{df}"
