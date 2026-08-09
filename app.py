from pathlib import Path
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="E-Commerce Retention & Funnel Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def get_db_connection():
    return duckdb.connect(database=':memory:')

conn = get_db_connection()

@st.cache_data(ttl=3600)
def run_query(query_str: str) -> pd.DataFrame:
    return conn.execute(query_str).df()

def load_sql(filename: str) -> str:
    return Path(f"sql/{filename}").read_text(encoding="utf-8")

if not Path("data/events.parquet").exists():
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from generate_data import generate_datasets

    st.info("Generating Parquet dataset (500k events)...")
    generate_datasets()
    st.rerun()

st.sidebar.title("⚡ Analytics")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    [
        "📊 Overview & Quality Audit",
        "🎯 Conversion Funnel",
        "🔄 Cohort Retention",
        "💎 RFM Segmentation"
    ]
)

if page == "📊 Overview & Quality Audit":
    st.title("Executive Overview & Quality Audit")
    st.write("")

    kpis = run_query("""
        SELECT
            (SELECT COUNT(DISTINCT customer_id) FROM read_parquet('data/customers.parquet')) AS total_customers,
            (SELECT COUNT(*) FROM read_parquet('data/events.parquet')) AS total_events,
            (SELECT COUNT(*) FROM read_parquet('data/transactions.parquet') WHERE status='Completed') AS total_orders,
            (SELECT ROUND(SUM(amount), 2) FROM read_parquet('data/transactions.parquet') WHERE status='Completed') AS total_revenue
    """).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Customers", f"{int(kpis['total_customers']):,}")
    c2.metric("Total Events", f"{int(kpis['total_events']):,}")
    c3.metric("Completed Orders", f"{int(kpis['total_orders']):,}")
    c4.metric("Total Revenue", f"${kpis['total_revenue']:,.2f}")

    st.write("")
    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.subheader("Event Breakdown by Type")
        df_evt = run_query("""
            SELECT event_type, COUNT(*) AS count
            FROM read_parquet('data/events.parquet')
            GROUP BY event_type
            ORDER BY count DESC
        """)
        fig_donut = px.pie(df_evt, values='count', names='event_type', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
        fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_b:
        st.subheader("Automated Data Quality Audit")
        df_dq = run_query(load_sql("data_quality.sql"))
        st.dataframe(df_dq, use_container_width=True, hide_index=True)

elif page == "🎯 Conversion Funnel":
    st.title("Conversion Funnel Analysis")
    st.write("")

    selected_device = st.selectbox("Device Filter", ["All", "desktop", "mobile", "tablet"])
    df_funnel = run_query(load_sql("funnel.sql"))

    if selected_device != "All":
        df_filtered = df_funnel[df_funnel['device'] == selected_device].copy()
    else:
        df_filtered = df_funnel.groupby(['stage_order', 'funnel_stage'], as_index=False).agg({'unique_users': 'sum'}).sort_values('stage_order')
        top_u = df_filtered['unique_users'].iloc[0]
        df_filtered['overall_conversion_pct'] = (df_filtered['unique_users'] / top_u * 100).round(2)
        df_filtered['prev_users'] = df_filtered['unique_users'].shift(1).fillna(top_u)
        df_filtered['step_conversion_pct'] = (df_filtered['unique_users'] / df_filtered['prev_users'] * 100).round(2)
        df_filtered['dropoff_pct'] = (100.0 - df_filtered['step_conversion_pct']).round(2)

    col_a, col_b = st.columns([1.2, 1])

    with col_a:
        st.subheader("Funnel Stage Progression")
        blue_gradient = ["#0ea5e9", "#0284c7", "#0369a1", "#075985", "#0c4a6e"]
        fig_funnel = go.Figure(go.Funnel(
            y=df_filtered['funnel_stage'],
            x=df_filtered['unique_users'],
            textinfo="value+percent initial",
            marker=dict(color=blue_gradient[:len(df_filtered)])
        ))
        fig_funnel.update_layout(margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_funnel, use_container_width=True)

    with col_b:
        st.subheader("Step Metrics & Drop-offs")
        df_disp = df_filtered[['funnel_stage', 'unique_users', 'overall_conversion_pct', 'step_conversion_pct', 'dropoff_pct']].copy()
        st.dataframe(
            df_disp,
            column_config={
                "funnel_stage": st.column_config.TextColumn("Stage"),
                "unique_users": st.column_config.NumberColumn("Unique Users", format="%d"),
                "overall_conversion_pct": st.column_config.NumberColumn("Overall Conversion", format="%.2f%%"),
                "step_conversion_pct": st.column_config.NumberColumn("Step Conversion", format="%.2f%%"),
                "dropoff_pct": st.column_config.NumberColumn("Drop-off Rate", format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True
        )

elif page == "🔄 Cohort Retention":
    st.title("Monthly Cohort Retention")
    st.write("")

    df_cohort = run_query(load_sql("cohort_retention.sql"))
    
    # 1. Format cohort_month as 'YYYY-MM' string
    df_cohort['cohort_month'] = pd.to_datetime(df_cohort['cohort_month']).dt.strftime('%Y-%m')
    
    # Pivot matrix
    pivot_df = df_cohort.pivot(index='cohort_month', columns='period_offset', values='retention_rate_pct')
    
    # 3. Format column headers as 'Month 0', 'Month 1', etc.
    pivot_df.columns = [f"Month {col}" for col in pivot_df.columns]

    st.subheader("Retention Heatmap (%)")
    fig_heatmap = px.imshow(
        pivot_df,
        labels=dict(x="Months After First Visit", y="Cohort Join Month", color="Retention %"),
        color_continuous_scale="Blues",
        aspect="auto"
    )
    fig_heatmap.update_layout(margin=dict(t=30, b=20, l=20, r=20))
    st.plotly_chart(fig_heatmap, use_container_width=True)

    st.subheader("Cohort Retention Matrix")
    
    # Reset index so cohort_month is a standard column (text format without %)
    df_table = pivot_df.reset_index()
    
    # 2. Apply percentage formatting ONLY to numeric month columns
    col_cfg = {
        "cohort_month": st.column_config.TextColumn("Cohort Join Month")
    }
    for col in pivot_df.columns:
        col_cfg[col] = st.column_config.NumberColumn(col, format="%.2f%%")

    st.dataframe(
        df_table,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True
    )

elif page == "💎 RFM Segmentation":
    st.title("RFM Customer Segmentation")
    st.write("")

    df_rfm = run_query(load_sql("rfm_segmentation.sql"))
    
    col_a, col_b = st.columns([1.2, 1])

    with col_a:
        st.subheader("Segment Revenue & Size")
        color_map = {seg: "#38bdf8" if seg == "Champions" else "#334155" for seg in df_rfm['rfm_segment']}
        fig_bar = px.bar(
            df_rfm,
            x='rfm_segment',
            y='total_segment_revenue',
            color='rfm_segment',
            color_discrete_map=color_map,
            labels={'total_segment_revenue': 'Total Revenue ($)', 'rfm_segment': 'RFM Segment'}
        )
        # 4. Clean RFM hoverlabel formatting
        fig_bar.update_traces(
            hovertemplate="<b>%{x}</b><br>Total Revenue: $%{y:,.2f}<extra></extra>"
        )
        fig_bar.update_layout(showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        st.subheader("Segment Breakdown")
        st.dataframe(
            df_rfm,
            column_config={
                "rfm_segment": st.column_config.TextColumn("Segment"),
                "customer_count": st.column_config.NumberColumn("Customers", format="%d"),
                "avg_recency_days": st.column_config.NumberColumn("Avg Recency (Days)", format="%.1f"),
                "avg_frequency": st.column_config.NumberColumn("Avg Frequency", format="%.1f"),
                "avg_monetary_spend": st.column_config.NumberColumn("Avg Spend", format="$%.2f"),
                "total_segment_revenue": st.column_config.NumberColumn("Total Revenue", format="$%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )
