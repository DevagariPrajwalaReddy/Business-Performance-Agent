import streamlit as st


def render_sidebar(df):

    st.sidebar.title("Business Performance AI")

    st.sidebar.markdown("---")

    st.sidebar.markdown("### Dataset Information")

    st.sidebar.write(
        f"Date Range: {df['orderdate'].min().date()} to {df['orderdate'].max().date()}"
    )

    st.sidebar.markdown("---")

    st.sidebar.markdown("### Example Queries")

    example_queries = [
        "Show Q4 2004 performance",
        "Top customers in 2005",
        "Recent sales trends",
        "Which category generated highest revenue?",
        "Compare Q1 2005 vs Q1 2004",
        "Show monthly sales trend"
    ]

    for q in example_queries:
        st.sidebar.write(f"- {q}")
