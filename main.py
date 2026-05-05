# datalogger_streamlit.py
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Data-Logger | SUR Division",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== CUSTOM CSS ======================
st.markdown("""
<style>
    .dashboard-title {
        font-size: 2.85rem; 
        font-weight: 800;
        background: linear-gradient(90deg, #FF9933, #003087);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.4rem; 
        color: #003087; 
        text-align: center;
        font-weight: 500;
        margin-top: -0.4rem;
    }
    .stImage {text-align: center;}
</style>
""", unsafe_allow_html=True)

# ====================== YOUR CUSTOM INDIAN RAILWAYS LOGO ======================
IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/Data-Logger/main/398-3987834_indian-railways-logo-hd-png-download.png"

# ====================== SECRETS ======================
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== LOGIN PAGE ======================
def login_page():
    st.image(IR_LOGO_URL, width=320)
    st.markdown('<h1 class="dashboard-title">SAFETY BRANCH</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Central Railway • Solapur Division</p>', unsafe_allow_html=True)
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔐 Secure Login")
        with st.form("login_form"):
            email = st.text_input("Username / Email", placeholder="Enter your ID")
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

def refresh_data():
    st.cache_data.clear()
    st.success("✅ Data refreshed successfully from Google Sheet!")
    st.rerun()

# ====================== MAIN DASHBOARD ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # ====================== HEADER WITH YOUR LOGO ======================
    col_logo, col_title = st.columns([1.2, 5])
    
    with col_logo:
        st.image(IR_LOGO_URL, width=160)
    
    with col_title:
        st.markdown('<h1 class="dashboard-title">DATA LOGGER EXCEPTIONAL REPORT</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Central Railway • Solapur Division • Safety Branch</p>', unsafe_allow_html=True)

    st.caption(f"**Logged in as:** {st.session_state.user_name}")

    st.divider()

    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True, key="sidebar_refresh"):
            refresh_data()
        st.divider()
        st.info("Live filters are applied below.")

    # Load Data
    df_original = load_data_from_gsheet()

    # ====================== LIVE FILTERS ======================
    st.subheader("🔍 Live Filters")
    col1, _ = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "🔎 Global Search (across all columns)", 
            placeholder="Search station, error, category, date...",
            key="global_search"
        )

    filtered_df = df_original.copy()

    if search_term:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.columns:
            mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[mask]

    # Column Filters
    filter_cols = st.columns(4)
    for i, col in enumerate(df_original.columns):
        with filter_cols[i % 4]:
            if col == 'FCOUNT':
                selected = st.multiselect(f"{col}", sorted(df_original[col].unique()), default=[], key=f"filter_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].isin(selected)]
            elif pd.api.types.is_numeric_dtype(df_original[col]) and col != 'FCOUNT':
                minv = int(df_original[col].min() or 0)
                maxv = int(df_original[col].max() or 0)
                rng = st.slider(col, minv, maxv, (minv, maxv), key=f"filter_{col}")
                filtered_df = filtered_df[(filtered_df[col] >= rng[0]) & (filtered_df[col] <= rng[1])]
            else:
                opts = sorted(df_original[col].dropna().astype(str).unique())
                selected = st.multiselect(f"{col}", opts, default=[], key=f"filter_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

    # ====================== METRICS ======================
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Records", f"{len(filtered_df):,}")
    with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
    with c3: 
        top_st = filtered_df.groupby('STATION')['FCOUNT'].sum().idxmax() if not filtered_df.empty and 'STATION' in filtered_df.columns else "-"
        st.metric("Top Station", top_st)
    with c4: st.metric("Max FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}" if not filtered_df.empty else 0)

    # ====================== CHARTS ======================
    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader("Top 15 Stations by FCOUNT")
        if not filtered_df.empty and 'STATION' in filtered_df.columns:
            top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
            fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT',
                         color='FCOUNT', color_continuous_scale='RdYlGn_r')
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(height=520, xaxis_tickangle=45)
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

        st.markdown("---")

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("🔄 Refresh Latest Data from Google Sheet", 
                        type="primary", use_container_width=True, key="main_refresh"):
                refresh_data()

        # ====================== DOWNLOAD SECTION ======================
        with col_btn2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                
                summary_df = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Record_Count='count'
                ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                summary_df.to_excel(writer, index=False, sheet_name='Station_Summary')

                for sheet_name, df_sheet in [('Filtered_Records', display_df), ('Station_Summary', summary_df)]:
                    worksheet = writer.sheets[sheet_name]
                    header_format = writer.book.add_format({
                        'bold': True, 'bg_color': '#003087', 'font_color': 'white',
                        'border': 1, 'align': 'center'
                    })
                    for col_num, value in enumerate(df_sheet.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    for idx, col in enumerate(df_sheet.columns):
                        max_len = max(df_sheet[col].astype(str).map(len).max(), len(str(col))) + 5
                        worksheet.set_column(idx, idx, min(max_len, 60))

            output.seek(0)
            st.download_button(
                label="⬇️ Download Professional Excel Report",
                data=output.getvalue(),
                file_name=f"Datalogger_Report_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
