import os
import pandas as pd
import streamlit as st
import plotly.express as px

from agent import ask, load_data

st.set_page_config(
    page_title="DataPilot AI — CSV Q&A Agent",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 2rem;}
.hero {padding: 1.2rem 1.4rem; border-radius: 18px; background: linear-gradient(135deg,#111827,#1f2937); color:white; margin-bottom:1rem;}
.hero h1 {margin:0; font-size:2.2rem;}
.hero p {margin:.35rem 0 0; opacity:.82;}
.metric-card {padding: .8rem 1rem; border:1px solid #e5e7eb; border-radius:12px; background:#fff;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>📊 DataPilot AI</h1>
<p>Ask plain-English questions. Python computes the answer from your real spreadsheet.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("1 · Load data")
    uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx", "xls"])
    st.caption("For the demo, use data/sample_sales.csv.")

    st.divider()
    st.header("2 · Ask")
    st.markdown("Try:")
    examples = [
        "Which region grew fastest in the last quarter?",
        "What was total sales in the latest quarter?",
        "Which region had the highest profit in 2025?",
        "What is the average order value by region?",
        "Which region had the most customers in 2026-Q1?",
    ]
    for q in examples:
        st.caption("• " + q)

if uploaded is None:
    st.info("Upload a CSV/Excel file to start, or run the app with the included sample dataset.")
    if os.path.exists("data/sample_sales.csv"):
        if st.button("Use included sample dataset", type="primary"):
            df = pd.read_csv("data/sample_sales.csv")
            st.session_state["df"] = df
            st.session_state["filename"] = "sample_sales.csv"
            st.rerun()
    st.stop()

try:
    df = load_data(uploaded)
    st.session_state["df"] = df
    st.session_state["filename"] = uploaded.name
except Exception as e:
    st.error(str(e))
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Columns", f"{len(df.columns):,}")
c3.metric("Numeric columns", f"{len(df.select_dtypes(include='number').columns):,}")

with st.expander("Dataset preview & schema", expanded=False):
    st.dataframe(df.head(20), use_container_width=True)
    schema = pd.DataFrame({
        "column": df.columns,
        "dtype": [str(x) for x in df.dtypes],
        "missing": [int(x) for x in df.isna().sum()],
        "unique": [int(df[c].nunique(dropna=True)) for c in df.columns],
    })
    st.dataframe(schema, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Ask your data")
question = st.chat_input("e.g. Which region grew fastest last quarter?")

if question:
    with st.spinner("Planning computation → executing pandas → grounding answer..."):
        try:
            result = ask(question, df)
            st.session_state["last_result"] = result
        except Exception as e:
            st.error(f"Agent error: {e}")
            st.stop()

if "last_result" in st.session_state:
    r = st.session_state["last_result"]

    st.markdown("### Answer")
    st.success(r.answer)

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("### Evidence used")
        st.dataframe(r.evidence, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Visualization")
        numeric = r.evidence.select_dtypes(include="number").columns.tolist()
        non_numeric = [c for c in r.evidence.columns if c not in numeric]
        if len(r.evidence) >= 2 and numeric and non_numeric:
            x = non_numeric[0]
            y = numeric[0]
            chart = px.bar(r.evidence, x=x, y=y, title=f"{y} by {x}")
            st.plotly_chart(chart, use_container_width=True)
        elif len(r.evidence) >= 2 and len(numeric) >= 2:
            chart = px.scatter(r.evidence, x=numeric[0], y=numeric[1])
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.caption("A chart is not useful for this scalar/small result; the evidence table is the source of truth.")

    with st.expander("🔎 See the exact computation"):
        st.code(r.code, language="python")
        st.caption("The code above was generated for this question and executed against the uploaded dataframe.")

    with st.expander("🧮 How the number was computed"):
        st.write(r.computation_note or "The agent computed the result with pandas from the uploaded data.")
