import sys
import os
import time
import json

# -------------------------------------------------
# PATH SETUP
# -------------------------------------------------
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import streamlit as st

# Custom module imports
from core.agent_setup import get_agent, df, llm
from core.cache import query_cache, update_persistent_cache
from core.kpi import build_report
from core.logger import logger
from core.utils import clean_output
from components.sidebar import render_sidebar

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="Business Performance AI",
    page_icon="📊",
    layout="wide"
)

# -------------------------------------------------
# TITLE & SIDEBAR
# -------------------------------------------------
st.markdown("<h3 style='margin:0; padding:0;'>📊 Business Performance AI Analyst</h3>", unsafe_allow_html=True)

# Sidebar handles data filters and displays dataframe info
render_sidebar(df)

# -------------------------------------------------
# LOAD AGENT (built once, reused)
# -------------------------------------------------
agent = get_agent()

# -------------------------------------------------
# SESSION STATE (display history only - the agent does not see earlier turns)
# -------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -------------------------------------------------
# DISPLAY CHAT HISTORY
# -------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------------------------
# USER INPUT
# -------------------------------------------------
query = st.chat_input("Enter your business analysis query...")

# -------------------------------------------------
# QUERY EXECUTION
# -------------------------------------------------
if query:
    # 1. Normalize query for consistent cache keys
    normalized_query = " ".join(query.lower().strip().split())

    # 2. Store user message in Session State
    st.session_state.messages.append({
        "role": "user",
        "content": query
    })

    with st.chat_message("user"):
        st.markdown(query)

    # ---------------------------------------------
    # CACHE CHECK (Long-term Storage Memory)
    # ---------------------------------------------
    if normalized_query in query_cache:
        output = query_cache[normalized_query]
        logger.info(f"CACHE HIT: {query}")
        execution_time = 0

    else:
        logger.info(f"NEW QUERY: {query}")
        with st.spinner("Analyzing business data..."):
            try:
                start_time = time.time()
                cacheable = True

                # 1) Performance / comparison questions: exact numbers computed in pandas,
                #    LLM only writes the commentary.
                report = build_report(df, query, llm)

                if report is not None:
                    output, cacheable = report
                else:
                    # 2) Everything else: pandas agent
                    result = agent.invoke({"input": query})
                    output = clean_output(result["output"])

                execution_time = round(time.time() - start_time, 2)

                if (
                    cacheable
                    and "Invalid Date Range" not in output
                    and "No data available" not in output
                    and "Agent stopped due to iteration limit or time limit." not in output
                ):
                    update_persistent_cache(normalized_query, output)
            except Exception as e:
                output = f"An error occurred: {str(e)}"
                execution_time = 0

    # ---------------------------------------------
    # DISPLAY & STORE ASSISTANT RESPONSE
    # ---------------------------------------------
    with st.chat_message("assistant"):
        st.markdown(output)
        st.caption(f"Response generated in {execution_time} sec")

    st.session_state.messages.append({
        "role": "assistant",
        "content": output
    })