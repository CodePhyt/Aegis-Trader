import streamlit as st
import pandas as pd
import httpx
import sqlite3
import plotly.express as px
import time
import os
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Project Predator Portal",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for that "Hacker" feel
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #00ff41;
    }
    .metric-card {
        background-color: #1e1e1e;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 5px;
        color: #fff;
    }
    h1, h2, h3 {
        color: #00ff41 !important;
        font-family: 'Courier New', Courier, monospace;
    }
    div.stDataFrame {
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection (Read-Only)
DB_FILE = "tradebot.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

def fetch_positions():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM positions", conn)
    conn.close()
    return df

def fetch_history():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT 100", conn)
    conn.close()
    return df

def get_logs():
    if os.path.exists("tradebot.log"):
        with open("tradebot.log", "r") as f:
            lines = f.readlines()
            return lines[-50:]
    return ["Log file not found."]

# --- SIDEBAR ---
with st.sidebar:
    st.title("🦅 PREDATOR")
    st.markdown("---")
    st.write(f"**Status**: 🟢 ONLINE")
    st.write(f"**Last Update**: {datetime.now().strftime('%H:%M:%S')}")
    st.markdown("---")
    
    if st.button("🔄 FORCE SYNC"):
        try:
            r = httpx.post("http://localhost:8000/sync")
            if r.status_code == 200:
                st.success("Sync Triggered")
            else:
                st.error("API Error")
        except:
            st.error("API Offline")

    st.markdown("---")
    auto_refresh = st.checkbox("Auto Refresh (5s)", value=True)

    if auto_refresh:
        time.sleep(5)
        st.rerun()

# --- MAIN CONTENT ---
st.title("COMMAND CENTER")

# Top Metrics
df_pos = fetch_positions()
if not df_pos.empty:
    total_invested = (df_pos['entry_price'] * df_pos['current_amount']).sum()
    moonbags = df_pos[df_pos['status'] == 'moonbag_secured']
    secured_value = (moonbags['current_amount'] * moonbags['entry_price']).sum() # roughly
    active_count = len(df_pos[df_pos['status'] == 'active'])
else:
    total_invested = 0
    secured_value = 0
    active_count = 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Active Positions", active_count)
with col2:
    st.metric("MoonBags Secured", len(df_pos[df_pos['status'] == 'moonbag_secured']) if not df_pos.empty else 0)
with col3:
    st.metric("Total Invested (Est)", f"${total_invested:,.2f}")
with col4:
    st.metric("MoonBag Value (Base)", f"${secured_value:,.2f}")

# Portfolio Grid
st.subheader("📡 Live Portfolio")
if not df_pos.empty:
    # Stylize
    def highlight_status(val):
        color = '#00ff41' if val == 'moonbag_secured' else '#ff4b4b'
        return f'color: {color}'

    st.dataframe(
        df_pos.style.applymap(highlight_status, subset=['status']),
        use_container_width=True
    )
else:
    st.info("No active positions found.")

# Trade History Chart
st.subheader("📊 Trade Performance")
df_hist = fetch_history()
if not df_hist.empty:
    fig = px.scatter(df_hist, x='timestamp', y='profit_pnl', color='type', title="Trade PnL Over Time", template='plotly_dark')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No trade history yet.")

# Logs
with st.expander("📝 System Logs (Last 50 Lines)", expanded=False):
    logs = get_logs()
    st.code("".join(logs))
