# ⚡ E-Commerce Conversion Funnel & Customer Retention Analytics

Production-grade analytics pipeline and interactive 4-page Streamlit dashboard powered by **DuckDB**, **Parquet**, and **Plotly**. Analyzes 500,000+ user journey events, conversion stage drop-offs, monthly cohort decay curves, and RFM customer segmentation.

---

## 💡 Business Value & ROI Impact

- **Revenue Impact & Tracking**: Directly tracks **$34,210+ in completed transaction revenue** across 20,000+ purchases.
- **Funnel Drop-off Minimization**: Pinpoints user friction points, uncovering a **~40% checkout stage drop-off rate** to target high-ROI UX checkout improvements.
- **Targeted Customer RFM Segmentation**: Leverages 4-quantile Recency, Frequency, and Monetary scoring to isolate **547 top-tier *Champions*** for targeted VIP campaigns while mitigating churn.

---

## 🏗️ Architecture Overview

```
ecommerce-funnel-retention/
├── data/                      # Parquet dataset storage (500k events, 25k customers)
│   └── .gitkeep
├── sql/                       # Production DuckDB SQL queries
│   ├── funnel.sql             # Stage progression & drop-off rates (Window Functions)
│   ├── cohort_retention.sql   # Monthly user retention matrix (Cohort DATEDIFF)
│   ├── rfm_segmentation.sql   # Customer segmentation (NTILE(4) quantiles)
│   └── data_quality.sql       # Automated integrity & null checks
├── src/                       # Core python analytics module
│   ├── __init__.py
│   ├── funnel.py              # Pure vectorized conversion calculations
│   └── retention.py           # Cohort matrix computation
├── scripts/
│   └── generate_data.py       # High-speed synthetic Parquet dataset generator
├── tests/                     # Automated pytest suite
│   ├── __init__.py
│   ├── test_funnel.py
│   └── test_retention.py
├── .streamlit/
│   └── config.toml            # Custom dark theme configuration
├── app.py                     # 4-Page interactive Streamlit dashboard
├── graph.html                 # Interactive system architecture topology graph
├── project_visual_story.html  # Interactive visual story & learning infographic
├── .gitignore
├── LICENSE                    # MIT License
├── requirements.txt
└── README.md
```

---

## 📊 Analytics & DuckDB SQL Breakdown

| Query Module | File Path | Core Engine / Technique | Purpose |
|---|---|---|---|
| **Conversion Funnel** | [`sql/funnel.sql`](file:///C:/Josh/Project/portoflio%20project%27s/ecommerce-funnel-retention/sql/funnel.sql) | CTEs + `FIRST_VALUE()` + `LAG()` | Measures unique users, overall conversion %, step-by-step conversion %, and drop-off rate partitioned by device. |
| **Cohort Retention** | [`sql/cohort_retention.sql`](file:///C:/Josh/Project/portoflio%20project%27s/ecommerce-funnel-retention/sql/cohort_retention.sql) | `DATE_TRUNC('month')` + `DATEDIFF()` | Calculates monthly user retention decay matrices relative to initial join cohort. |
| **RFM Segmentation** | [`sql/rfm_segmentation.sql`](file:///C:/Josh/Project/portoflio%20project%27s/ecommerce-funnel-retention/sql/rfm_segmentation.sql) | `NTILE(4)` Window Quantiles | Categorizes customers into 4-quantile Recency, Frequency, and Monetary scores (Champions, Loyal, At Risk, Churned). |
| **Data Quality Audit** | [`sql/data_quality.sql`](file:///C:/Josh/Project/portoflio%20project%27s/ecommerce-funnel-retention/sql/data_quality.sql) | Multi-UNION Null & Integrity Audit | Verifies zero null keys, orphan IDs, or invalid transaction amounts across Parquet files. |

---

## 🚀 Setup & Execution Guide

### 1. Environment Setup
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Generate 500,000 Events Parquet Dataset
```bash
python scripts/generate_data.py
```

### 3. Run Automated Tests
```bash
python -m pytest
```

### 4. Launch Streamlit Dashboard
```bash
python -m streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ⚡ Performance Benchmark
- **Dataset Size**: 500,000 funnel events + 25,000 customer records + 20,000 transactions.
- **DuckDB Query Latency**: < 50 ms in-memory Parquet execution.
- **Test Suite Execution**: 0.52s total test time.

---

## 📄 License
Distributed under the [MIT License](file:///C:/Josh/Project/portoflio%20project%27s/ecommerce-funnel-retention/LICENSE).
