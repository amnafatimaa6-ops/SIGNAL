from pathlib import Path
import json
import zipfile
import warnings

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ------------------------------------------------------------
# PROJECT SIGNAL | Customer Intelligence & Retention Analytics
# Loads the uploaded PROJECT_SIGNAL_ARTIFACTS.zip automatically.
# ------------------------------------------------------------

st.set_page_config(
    page_title="PROJECT SIGNAL",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "PROJECT_SIGNAL_ARTIFACTS.zip"
EXTRACT_DIR = ROOT / ".signal_artifacts"

# ---------- Visual styling ----------
st.markdown(
    """
    <style>
    .stApp { background: #080d18; color: #e8edf7; }
    [data-testid="stSidebar"] { background: #0d1424; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #111c31, #0d1628);
        border: 1px solid #233553;
        padding: 15px 17px;
        border-radius: 13px;
    }
    [data-testid="stMetricLabel"] { color: #9eb0ca; }
    [data-testid="stMetricValue"] { color: #f2f6ff; }
    h1, h2, h3 { color: #edf3ff; }
    .signal-subtitle { color: #8da5c8; letter-spacing: 2px; font-size: 0.76rem; }
    .signal-note {
        padding: 12px 15px; border-left: 3px solid #5b8cff;
        background: #101b30; border-radius: 5px; color: #c5d3e9;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Find and unpack the artifact archive ----------
def locate_artifacts():
    """Return a directory containing the exported SIGNAL files."""
    required = [
        "transactions.csv",
        "orders.csv",
        "customers_rfm.csv",
        "signal_repeat_purchase_model.joblib",
        "model_metadata.json",
    ]

    # Support either an already-unpacked repo or the ZIP in the repo root.
    for base in [ROOT, EXTRACT_DIR]:
        if all((base / name).exists() for name in required):
            return base

    if not ZIP_PATH.exists():
        return None

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(ZIP_PATH, "r") as archive:
            # Prevent unsafe paths inside an archive from writing outside
            # the extraction directory.
            destination = EXTRACT_DIR.resolve()
            for member in archive.infolist():
                target = (EXTRACT_DIR / member.filename).resolve()
                if target != destination and destination not in target.parents:
                    raise ValueError("Unsafe path detected in ZIP archive.")
            archive.extractall(EXTRACT_DIR)
    except Exception as exc:
        st.error(f"Could not extract the artifact ZIP: {exc}")
        st.stop()

    return EXTRACT_DIR


ARTIFACTS = locate_artifacts()
if ARTIFACTS is None:
    st.error(
        "PROJECT_SIGNAL_ARTIFACTS.zip was not found. "
        "Upload it to the same GitHub repository directory as app.py."
    )
    st.stop()


def find_file(filename):
    """Find a named artifact in the repository or extracted archive."""
    direct = ARTIFACTS / filename
    if direct.exists():
        return direct
    matches = list(ARTIFACTS.rglob(filename))
    return matches[0] if matches else None


@st.cache_data(show_spinner=False)
def load_csv(path_string):
    return pd.read_csv(path_string)


def load_table(filename, required=False):
    path = find_file(filename)
    if path is None:
        if required:
            st.error(f"Required data file is missing: {filename}")
            st.stop()
        return pd.DataFrame()
    return load_csv(str(path))


transactions = load_table("transactions.csv", required=True)
orders = load_table("orders.csv", required=True)
customers = load_table("customers_rfm.csv", required=True)
at_risk = load_table("at_risk_customers.csv")
strategy = load_table("retention_strategy.csv")
targeting = load_table("targeting_results.csv")
model_evaluation = load_table("final_model_evaluation.csv")

# ---------- Helpers ----------
def first_existing(frame, candidates):
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def money(value):
    return f"${value:,.0f}"


def safe_numeric(frame, column):
    if column and column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(dtype=float)


# Identify columns robustly, including slight naming differences.
sales_col = first_existing(transactions, ["Sales", "sales"])
profit_col = first_existing(transactions, ["Profit", "profit"])
date_col = first_existing(transactions, ["Order Date", "Order_Date"])
category_col = first_existing(transactions, ["Category", "category"])
discount_col = first_existing(transactions, ["Discount", "discount"])
customer_col = first_existing(transactions, ["Customer Name", "Customer_Name"])
segment_col = first_existing(
    customers, ["Customer_Segment", "RFM_Segment", "Segment", "Customer Segment"]
)
recency_col = first_existing(customers, ["Recency", "Recency_Days"])
frequency_col = first_existing(customers, ["Frequency", "Order_Frequency"])
monetary_col = first_existing(customers, ["Monetary", "Total_Sales", "Monetary_Value"])
customer_profit_col = first_existing(customers, ["Total_Profit", "Profit"])

if date_col:
    transactions[date_col] = pd.to_datetime(transactions[date_col], errors="coerce")

# ---------- Sidebar ----------
st.sidebar.markdown("## ◈ SIGNAL")
st.sidebar.caption("CUSTOMER INTELLIGENCE PLATFORM")
page = st.sidebar.radio(
    "NAVIGATION",
    [
        "Executive Overview",
        "Customer Intelligence",
        "Retention Analytics",
        "Discount Economics",
        "Predictive Analytics",
        "Business Strategy",
    ],
)
st.sidebar.divider()
st.sidebar.caption("PROJECT DATA")
st.sidebar.write(f"{len(transactions):,} transaction rows")
st.sidebar.write(f"{len(customers):,} customer profiles")
st.sidebar.caption("Sample Superstore · 2015–2018")

# Date/category filters apply to transaction-based views.
filtered_transactions = transactions.copy()
if date_col and transactions[date_col].notna().any():
    min_date = transactions[date_col].min().date()
    max_date = transactions[date_col].max().date()
    selected_dates = st.sidebar.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
        mask = transactions[date_col].dt.date.between(start_date, end_date)
        filtered_transactions = filtered_transactions.loc[mask]

if category_col:
    categories = sorted(transactions[category_col].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        "Product categories",
        categories,
        default=categories,
    )
    filtered_transactions = filtered_transactions[
        filtered_transactions[category_col].isin(selected_categories)
    ]

# ---------- Header ----------
st.markdown('<p class="signal-subtitle">THE HIDDEN ECONOMICS OF CUSTOMER DECISIONS</p>', unsafe_allow_html=True)
st.title(page)

# ---------- EXECUTIVE OVERVIEW ----------
if page == "Executive Overview":
    st.markdown(
        "A research-led view of customer purchasing, profitability and retention opportunities."
    )

    sales = safe_numeric(filtered_transactions, sales_col).sum()
    profit = safe_numeric(filtered_transactions, profit_col).sum()
    customer_count = (
        filtered_transactions[customer_col].nunique()
        if customer_col else len(customers)
    )
    order_id_col = first_existing(filtered_transactions, ["Order ID", "Order_ID"])
    order_count = (
        filtered_transactions[order_id_col].nunique()
        if order_id_col else len(orders)
    )
    margin = profit / sales if sales else np.nan

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Revenue", money(sales))
    k2.metric("Profit", money(profit))
    k3.metric("Customers", f"{customer_count:,}")
    k4.metric("Orders", f"{order_count:,}")
    k5.metric("Profit margin", f"{margin:.1%}" if pd.notna(margin) else "N/A")

    st.divider()
    left, right = st.columns(2)

    if category_col and sales_col:
        category_sales = (
            filtered_transactions.groupby(category_col, as_index=False)[sales_col]
            .sum()
            .sort_values(sales_col, ascending=False)
        )
        with left:
            st.subheader("Revenue by category")
            fig = px.bar(
                category_sales, x=category_col, y=sales_col,
                template="plotly_dark", color=sales_col,
                color_continuous_scale=["#243b64", "#4d83e6", "#73c8e8"],
            )
            fig.update_layout(coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    if category_col and profit_col:
        category_profit = (
            filtered_transactions.groupby(category_col, as_index=False)[profit_col]
            .sum()
            .sort_values(profit_col, ascending=False)
        )
        with right:
            st.subheader("Profit by category")
            fig = px.bar(
                category_profit, x=category_col, y=profit_col,
                template="plotly_dark", color=profit_col,
                color_continuous_scale=["#a64d79", "#4d83e6", "#53c6ad"],
            )
            fig.update_layout(coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    if date_col and sales_col:
        st.subheader("Monthly revenue trend")
        monthly = filtered_transactions.dropna(subset=[date_col]).copy()
        monthly["Month"] = monthly[date_col].dt.to_period("M").astype(str)
        monthly = monthly.groupby("Month", as_index=False)[sales_col].sum()
        fig = px.line(
            monthly, x="Month", y=sales_col, markers=True,
            template="plotly_dark",
        )
        fig.update_traces(line_color="#65a9ff", line_width=3)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div class="signal-note">These are historical descriptive metrics from the Sample Superstore dataset, not live company performance.</div>',
        unsafe_allow_html=True,
    )

# ---------- CUSTOMER INTELLIGENCE ----------
elif page == "Customer Intelligence":
    st.markdown("Explore customer value, purchasing frequency and RFM segment composition.")

    if segment_col:
        segments = sorted(customers[segment_col].dropna().unique().tolist())
        chosen = st.multiselect("Filter customer segments", segments, default=segments)
        view = customers[customers[segment_col].isin(chosen)].copy()
    else:
        view = customers.copy()
        st.warning("A customer-segment column was not detected in customers_rfm.csv.")

    a, b, c = st.columns(3)
    a.metric("Customers shown", f"{len(view):,}")
    if frequency_col:
        b.metric("Average order frequency", f"{safe_numeric(view, frequency_col).mean():.2f}")
    if monetary_col:
        b.metric("Average customer sales", money(safe_numeric(view, monetary_col).mean()))
    if customer_profit_col:
        c.metric("Total historical customer profit", money(safe_numeric(view, customer_profit_col).sum()))

    left, right = st.columns(2)
    if segment_col:
        with left:
            st.subheader("Customer segment distribution")
            counts = view[segment_col].value_counts().rename_axis("Segment").reset_index(name="Customers")
            fig = px.pie(counts, names="Segment", values="Customers", hole=0.58, template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    if frequency_col and monetary_col:
        with right:
            st.subheader("Frequency vs monetary value")
            plot_df = view.copy()
            plot_df[frequency_col] = pd.to_numeric(plot_df[frequency_col], errors="coerce")
            plot_df[monetary_col] = pd.to_numeric(plot_df[monetary_col], errors="coerce")
            fig = px.scatter(
                plot_df, x=frequency_col, y=monetary_col,
                color=segment_col if segment_col else None,
                hover_name=customer_col if customer_col and customer_col in plot_df else None,
                template="plotly_dark",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Customer records")
    search = st.text_input("Search customer name")
    if search and customer_col and customer_col in view.columns:
        view = view[view[customer_col].astype(str).str.contains(search, case=False, na=False)]
    st.dataframe(view, use_container_width=True, hide_index=True)

# ---------- RETENTION ANALYTICS ----------
elif page == "Retention Analytics":
    st.markdown("Historical inactivity and customer-priority analysis. These are prioritisation rules, not predicted recoveries.")

    if not at_risk.empty:
        priority_col = first_existing(at_risk, ["Retention_Priority", "Retention Priority"])
        ratio_col = first_existing(at_risk, ["Inactivity_Ratio"])
        profit_col_risk = first_existing(at_risk, ["Total_Profit", "Profit"])
        recency_risk = first_existing(at_risk, ["Recency", "Recency_Days"])

        x1, x2, x3 = st.columns(3)
        x1.metric("At-risk customers", f"{len(at_risk):,}")
        if profit_col_risk:
            x2.metric("Historical profit", money(pd.to_numeric(at_risk[profit_col_risk], errors="coerce").sum()))
        if priority_col:
            high_count = (at_risk[priority_col] == "High-priority re-engagement").sum()
            x3.metric("High-priority group", f"{high_count:,}")

        if priority_col:
            st.subheader("Retention priority distribution")
            priority_counts = at_risk[priority_col].value_counts().rename_axis("Priority").reset_index(name="Customers")
            fig = px.bar(priority_counts, x="Priority", y="Customers", color="Priority", template="plotly_dark")
            fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        if ratio_col and profit_col_risk:
            st.subheader("Inactivity relative to typical purchase cadence")
            plot_df = at_risk.copy()
            plot_df[ratio_col] = pd.to_numeric(plot_df[ratio_col], errors="coerce")
            plot_df[profit_col_risk] = pd.to_numeric(plot_df[profit_col_risk], errors="coerce")
            fig = px.scatter(
                plot_df, x=ratio_col, y=profit_col_risk,
                color=priority_col if priority_col else None,
                hover_name=customer_col if customer_col and customer_col in plot_df else None,
                template="plotly_dark",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("At-risk customer list")
        st.dataframe(at_risk, use_container_width=True, hide_index=True)
    else:
        st.info("At-risk customer data was not found in the artifact package.")

# ---------- DISCOUNT ECONOMICS ----------
elif page == "Discount Economics":
    st.markdown("Explore how discount levels are associated with sales and profitability. Associations are not causal effects.")

    if discount_col and sales_col and profit_col:
        disc = filtered_transactions.copy()
        disc[discount_col] = pd.to_numeric(disc[discount_col], errors="coerce")
        disc[sales_col] = pd.to_numeric(disc[sales_col], errors="coerce")
        disc[profit_col] = pd.to_numeric(disc[profit_col], errors="coerce")
        disc_summary = (
            disc.groupby(discount_col, as_index=False)
            .agg(
                Lines=(profit_col, "size"),
                Sales=(sales_col, "sum"),
                Profit=(profit_col, "sum"),
            )
        )
        disc_summary["Profit_Margin"] = np.where(
            disc_summary["Sales"] > 0,
            disc_summary["Profit"] / disc_summary["Sales"],
            np.nan,
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Discount levels", f"{len(disc_summary)}")
        m2.metric("Total sales", money(disc_summary["Sales"].sum()))
        m3.metric("Total profit", money(disc_summary["Profit"].sum()))

        left, right = st.columns(2)
        with left:
            st.subheader("Profit by discount level")
            fig = px.bar(disc_summary, x=discount_col, y="Profit", template="plotly_dark")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            st.subheader("Aggregate profit margin by discount")
            fig = px.line(disc_summary, x=discount_col, y="Profit_Margin", markers=True, template="plotly_dark")
            fig.update_layout(yaxis_tickformat=".0%", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Discount-level summary")
        st.dataframe(disc_summary, use_container_width=True, hide_index=True)

        if category_col:
            st.subheader("Profitability by product category")
            category_summary = (
                disc.groupby(category_col, as_index=False)
                .agg(Sales=(sales_col, "sum"), Profit=(profit_col, "sum"))
            )
            category_summary["Profit_Margin"] = category_summary["Profit"] / category_summary["Sales"]
            fig = px.bar(category_summary, x=category_col, y="Profit_Margin", template="plotly_dark")
            fig.update_layout(yaxis_tickformat=".0%", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Required Sales, Profit or Discount columns were not found.")

# ---------- PREDICTIVE ANALYTICS ----------
elif page == "Predictive Analytics":
    st.markdown("Exploratory 90-day repeat-purchase model. The model is not deployment-ready.")

    model_path = find_file("signal_repeat_purchase_model.joblib")
    metadata_path = find_file("model_metadata.json")
    metadata = {}
    if metadata_path:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            metadata = json.load(handle)

    if not model_evaluation.empty:
        st.subheader("Held-out test evaluation")
        st.dataframe(model_evaluation, use_container_width=True, hide_index=True)

        model_col = first_existing(model_evaluation, ["Model"])
        if model_col:
            selected_model = model_evaluation[
                model_evaluation[model_col].astype(str).str.contains("Month Only", case=False, na=False)
            ]
            if not selected_model.empty:
                row = selected_model.iloc[0]
                roc_col = first_existing(model_evaluation, ["ROC_AUC"])
                pr_col = first_existing(model_evaluation, ["PR_AUC"])
                brier_col = first_existing(model_evaluation, ["Brier_Score"])
                p1, p2, p3 = st.columns(3)
                if roc_col: p1.metric("Test ROC-AUC", f"{float(row[roc_col]):.4f}")
                if pr_col: p2.metric("Test PR-AUC", f"{float(row[pr_col]):.4f}")
                if brier_col: p3.metric("Test Brier score", f"{float(row[brier_col]):.4f}")

    if not targeting.empty:
        st.subheader("Validation targeting analysis")
        st.dataframe(targeting, use_container_width=True, hide_index=True)

    if model_path and metadata:
        st.success("Saved model and metadata found in the artifact package.")
        st.write("Model:", metadata.get("model_name", "Not specified"))
        st.write("Prediction target:", metadata.get("prediction_target", "Not specified"))
        st.write("Lookback window:", f'{metadata.get("historical_lookback_days", "N/A")} days')
        st.write("Prediction horizon:", f'{metadata.get("prediction_horizon_days", "N/A")} days')
        st.caption(
            "The exported package does not include a validated live customer-snapshot feature table. "
            "Therefore this page reports model evaluation; it does not invent live customer predictions."
        )
        with st.expander("Model details"):
            st.json(metadata)
    else:
        st.warning("Saved model or metadata file was not found.")

    st.markdown(
        '<div class="signal-note">Test ROC-AUC of approximately 0.57 indicates modest ranking ability. '
        'Predictions should not be used as guaranteed purchase forecasts.</div>',
        unsafe_allow_html=True,
    )

# ---------- BUSINESS STRATEGY ----------
elif page == "Business Strategy":
    st.markdown("Segment-level recommendations derived from historical customer and profitability analysis.")

    if not strategy.empty:
        st.dataframe(strategy, use_container_width=True, hide_index=True)
    else:
        st.warning("Retention strategy table was not found.")

    st.subheader("Research-backed operating principles")
    st.markdown(
        """
        - Prioritise profitable at-risk customers for controlled re-engagement tests.
        - Avoid blanket discounts where historical margins are weak.
        - Measure repeat purchases and customer profit together.
        - Use control groups before attributing incremental results to a campaign.
        - Track campaign costs before reporting return on investment.
        """
    )
    st.info(
        "Campaign outcomes and ROI have not been measured in this dataset. "
        "Recommendations are hypotheses for future testing, not proven effects."
    )

# ---------- Footer ----------
st.divider()
st.caption(
    "PROJECT SIGNAL · Sample Superstore 2015–2018 · "
    "Historical observational analysis · Built with Streamlit and Plotly"
)
