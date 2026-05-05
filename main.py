# datalogger_streamlit.py
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Data-Logger Exceptional Report-SUR",
    page_icon="🚄",
    layout="wide"
)

# ====================== CUSTOM CSS ======================
st.markdown("""
<style>
    .main-header {font-size: 2.8rem; font-weight: 700; color: #00b894; text-align: center;}
    .sub-header {font-size: 1.4rem; color: #2d3436; text-align: center; margin-bottom: 2rem;}
</style>
""", unsafe_allow_html=True)

# ====================== SECRETS ======================
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== LOGIN ======================
def login_page():
    st.markdown('<h1 class="main-header">An initiative by Safety Branch</h1>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">Central Railway, Solapur Division</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Data-Logger Exceptional Reports-SUR DIVN.</p>', unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Login to Access Dashboard")
        with st.form("login_form"):
            email = st.text_input("Email / Username", placeholder="Enter ID")
            password = st.text_input("Password", type="password", placeholder="Enter Password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if email in USERS and password == USERS[email].get("password"):
                    st.session_state.logged_in = True
                    st.session_state.user_name = USERS[email].get("name")
                    st.success(f"Welcome, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("Invalid credentials!")

# ====================== LOAD DATA ======================
@st.cache_data(ttl=300)
def load_data_from_gsheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())

        if df.empty:
            st.error("Google Sheet is empty!")
            st.stop()

        df.columns = df.columns.str.strip()
        
        # Fixed regex warning
        df = df.loc[:, ~df.columns.str.lower().str.replace('.', '', regex=False)
                    .str.contains(r'^(?:sl|sr)\s*no', regex=True)]

        if 'FCOUNT' in df.columns:
            df['FCOUNT'] = pd.to_numeric(df['FCOUNT'], errors='coerce').fillna(0).astype(int)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.stop()

# ====================== REFRESH FUNCTION ======================
def refresh_data():
    st.cache_data.clear()
    st.success("✅ Data refreshed from Google Sheet!")
    st.rerun()

# ====================== MAIN APP ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    st.markdown('<h1 class="main-header">An initiative by Safety Branch</h1>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">Central Railway, Solapur Division</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Data-Logger Exceptional Reports SUR DIVN.</p>', unsafe_allow_html=True)
    st.caption(f"Logged in as: **{st.session_state.user_name}**")

    # Top Refresh Button (Optional - keeping one at top also)
    if st.button("🔄 Refresh Data from Sheet", type="primary"):
        refresh_data()

    st.divider()

    df_original = load_data_from_gsheet()

    # ====================== LIVE FILTERS + SEARCH ======================
    st.subheader("🔍 Live Filters")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "🔎 Global Search (across all columns)", 
            placeholder="Search station, error, category, date, fcount...",
            key="global_search"
        )

    filtered_df = df_original.copy()

    # Apply Global Search
    if search_term:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.columns:
            mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[mask]

    # Column-wise Filters
    filter_cols = st.columns(4)
    for i, col in enumerate(df_original.columns):
        with filter_cols[i % 4]:
            if col == 'FCOUNT':
                selected = st.multiselect(f"{col}", options=sorted(df_original[col].unique()), default=[], key=f"f_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].isin(selected)]
            elif pd.api.types.is_numeric_dtype(df_original[col]) and col != 'FCOUNT':
                minv, maxv = int(df_original[col].min()), int(df_original[col].max())
                rng = st.slider(col, minv, maxv, (minv, maxv), key=f"f_{col}")
                filtered_df = filtered_df[(filtered_df[col] >= rng[0]) & (filtered_df[col] <= rng[1])]
            else:
                selected = st.multiselect(f"{col}", options=sorted(df_original[col].dropna().astype(str).unique()), default=[], key=f"f_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

    # ====================== METRICS & CHARTS ======================
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Records", f"{len(filtered_df):,}")
    with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
    with c3: 
        top_st = filtered_df.groupby('STATION')['FCOUNT'].sum().idxmax() if not filtered_df.empty and 'STATION' in filtered_df.columns else "-"
        st.metric("Top Station", top_st)
    with c4: st.metric("Max FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}" if not filtered_df.empty else 0)

    # Charts and Summary Table (same as before)
    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader("Top 15 Stations by FCOUNT")
        if not filtered_df.empty and 'STATION' in filtered_df.columns and 'FCOUNT' in filtered_df.columns:
            top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
            fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT',
                         color='FCOUNT', color_continuous_scale=['#00FF00', '#FF7F00', '#FF0000'])
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(height=550, xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.subheader("Station Summary")
        if not filtered_df.empty:
            summary = filtered_df.groupby('STATION')['FCOUNT'].agg(Total_FCOUNT='sum', Records='count').sort_values('Total_FCOUNT', ascending=False)
            st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                        .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'), 
                        use_container_width=True)

    # ====================== DETAILED RECORDS ======================
    st.divider()
    st.subheader("📋 Detailed Records")

    if filtered_df.empty:
        st.warning("No records found.")
    else:
        display_df = filtered_df.copy()
        if 'Date' in display_df.columns:
            display_df['Date'] = display_df['Date'].dt.date

        st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

        # ====================== REFRESH BUTTON BELOW TABLE ======================
        st.markdown("---")
        if st.button("🔄 Refresh Latest Data from Google Sheet", type="primary", use_container_width=True):
            refresh_data()

        # Download Section
        st.subheader("📥 Download Filtered Data")
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
            # Add summary sheet...
            summary_df = filtered_df.groupby('STATION')['FCOUNT'].agg(Total_FCOUNT='sum', Record_Count='count').reset_index()
            summary_df.to_excel(writer, index=False, sheet_name='Station_Summary')

        st.download_button(
            label="⬇️ Download Excel Report",
            data=output.getvalue(),
            file_name="Datalogger_Filtered_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

    st.caption("🚄 Safety Branch, Solapur Division | Data Logger Exceptional Report Dashboard")
