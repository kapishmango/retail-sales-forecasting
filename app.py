"""Read-only dashboard over reproducible CLI outputs."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Retail Sales | Forecast Lab",page_icon="📈",layout="wide")
st.title("Retail Sales Forecast Lab")
st.caption("Historical sales • Chronological evaluation • One week ahead")
folder=Path("reports")
if not (folder/"metrics.json").exists():
    st.info("Generate reports first: python -m retail_forecast.cli run --demo")
    st.stop()
summary=json.loads((folder/"metrics.json").read_text())
st.sidebar.subheader("Explore the holdout")
data=pd.read_csv(folder/"predictions.csv",dtype={"product_id":str},parse_dates=["week"])
stores=st.sidebar.multiselect("Store / channel",sorted(data.store_id.unique()),default=sorted(data.store_id.unique()))
products=st.sidebar.multiselect("Products",sorted(data.product_id.unique()),default=sorted(data.product_id.unique()))
filtered=data[data.store_id.isin(stores)&data.product_id.isin(products)]
st.sidebar.caption(f"Source: {summary['data_source']}")
st.sidebar.caption("UCI data represents one online retailer. Demo data contains two synthetic stores.")
if filtered.empty:st.info("Select at least one store and product.");st.stop()
mae=filtered.absolute_error.mean();denominator=filtered.actual.abs().sum()
wape=filtered.absolute_error.sum()/denominator if denominator else None
columns=st.columns(4)
columns[0].metric("Observed units",f"{filtered.actual.sum():,.0f}")
columns[1].metric("MAE (units)",f"{mae:,.1f}")
columns[2].metric("WAPE",f"{wape:.1%}" if wape is not None else "Undefined")
columns[3].metric("Holdout weeks",filtered.week.nunique())
st.subheader("Actual sales and forecasts")
st.line_chart(filtered.groupby("week")[["actual","gradient_boosting","seasonal_naive","rolling_mean"]].sum(),color=["#193f48","#dc784c","#9bb4b6","#9381ac"])
st.subheader("Error by week")
st.bar_chart(filtered.groupby("week")[["absolute_error","baseline_absolute_error"]].sum())
with st.expander("Inspect evaluated forecasts"):
    st.dataframe(filtered,hide_index=True,width="stretch")
st.download_button("Download filtered forecasts",filtered.to_csv(index=False),"forecasts.csv","text/csv")
st.info("Sales are a lower bound on demand when items are out of stock. Missing transaction weeks are filled with zero; availability and lost sales are not observed.")
