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

