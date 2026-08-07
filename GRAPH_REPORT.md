# 🗺️ System Architecture & Graphify Dependency Report

Executive architectural summary and component dependency mapping for **ecommerce-funnel-retention**.

---

## 1. Top-Level Module Organization

The project is structured into 5 decoupled analytical layers:

```
[UI Dashboard Layer: app.py]
       │
       ├── Reads DuckDB SQL Queries ──► [SQL Layer: sql/*.sql] ──► Reads Parquet Files ──► [Data Storage: data/*.parquet]
       │
       └── Modular Analytics Package ──► [Python Package: src/*.py] ◄── Verified by ──► [Test Suite: tests/*.py]
```

---

## 2. Core Architectural Hubs & Data Flows

### A. Dashboard UI Hub (`app.py`)
- **Role**: 4-page Streamlit application rendering Plotly interactive visualizers and KPI metrics.
- **Connections**:
  - `Overview`: Queries `sql/data_quality.sql` & raw `events.parquet`.
  - `Funnel Page`: Queries `sql/funnel.sql` and builds `go.Funnel` stage progression charts.
  - `Cohort Page`: Queries `sql/cohort_retention.sql` and builds `px.imshow` monthly decay heatmaps.
  - `RFM Page`: Queries `sql/rfm_segmentation.sql` and highlights *Champions* vs *At-Risk* segments.

### B. High-Performance SQL Query Engine (`sql/`)
- **Role**: Pure SQL analytical transformations executed in-memory by DuckDB directly over zero-copy Parquet tables.
- **Key Modules**:
  - `sql/funnel.sql`: Stage progression, step conversion %, and drop-offs using `LAG()` & `FIRST_VALUE()`.
  - `sql/cohort_retention.sql`: Monthly user join dates & retention offsets using `DATEDIFF('month', ...)`.
  - `sql/rfm_segmentation.sql`: 4-quantile Recency, Frequency, and Monetary scoring using `NTILE(4) OVER (...)`.
  - `sql/data_quality.sql`: Multi-UNION null key, orphan customer ID, and duplicate event audits.

### C. Analytical Core & Verification (`src/` & `tests/`)
- **Role**: Pure vectorized Python functions for stand-alone analytics execution and automated testing.
- **Modules**:
  - `src/funnel.py` ◄── Tested by ── `tests/test_funnel.py`
  - `src/retention.py` ◄── Tested by ── `tests/test_retention.py`

---

## 3. Data Storage Layer (`data/`)

| File | Rows | Compressed Size | Description |
|---|---|---|---|
| `data/events.parquet` | 500,000 | ~11.8 MB | Sequential user journey event logs (`page_view` -> `purchase`). |
| `data/customers.parquet` | 25,000 | ~234 KB | User demographic and acquisition channel profiles. |
| `data/transactions.parquet` | 20,224 | ~530 KB | Purchase transaction records ($34,210+ total revenue). |
