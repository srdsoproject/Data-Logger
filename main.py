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

# ====================== CUSTOM CSS (Professional Look) ======================
st.markdown("""
<style>
    .main-header {
        font-size: 2.4rem; 
        font-weight: 700; 
        color: #FF9933; 
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.5rem; 
        color: #003087; 
        text-align: center;
        font-weight: 500;
    }
    .dashboard-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF9933, #003087);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .stDataFrame {border-radius: 8px; overflow: hidden;}
</style>
""", unsafe_allow_html=True)

# ====================== INDIAN RAILWAYS LOGO ======================
# You can replace this URL with your own hosted logo if needed
IR_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Ministry_of_Railways_India.svg/800px-Ministry_of_Railways_India.svg.png"

# ====================== SECRETS ======================
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== LOGIN ======================
def login_page():
    st.image(IR_LOGO_URL, width=180)
    st.markdown('<h1 class="dashboard-title">SAFETY BRANCH</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Central Railway • Solapur Division</p>', unsafe_allow_html=True)
    st.markdown("### Data Logger Exceptional Report Dashboard")
    
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
                    st.error("Invalid credentials. Please try again.")

# ====================== LOAD & REFRESH DATA ======================
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
    st.success("✅ Dashboard refreshed with latest data!")
    st.rerun()

# ====================== MAIN DASHBOARD ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # ====================== HEADER ======================
    col_logo, col_title = st.columns([1, 4])
    with col_logo:
        st.image(IR_LOGO_URL, width=120)
    with col_title:
        st.markdown('<h1 class="dashboard-title">DATA LOGGER EXCEPTIONAL REPORT</h1>', unsafe_allow_html=True)
        st.markdown("**Central Railway • Solapur Division • Safety Branch**")

    st.caption(f"**Logged in as:** {st.session_state.user_name}  |  Last Updated: Just now")

    st.divider()

    # Sidebar for controls
    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Latest Data", type="primary", use_container_width=True):
            refresh_data()
        
        st.divider()
        st.info("Use filters below to analyze exceptional reports.")

    # Load Data
    df_original = load_data_from_gsheet()

    # ====================== FILTERS ======================
    st.subheader("🔍 Filters")
    col_search, col_spacer = st.columns([3, 1])
    with col_search:
        search_term = st.text_input(
            "Global Search", 
            placeholder="Search across Station, Error, Category...",
            key="global_search"
        )

    filtered_df = df_original.copy()

    if search_term:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.columns:
            mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[mask]

    # Column filters in 4 columns
    filter_cols = st.columns(4)
    for i, col in enumerate(df_original.columns):
        with filter_cols[i % 4]:
            if col == 'FCOUNT':
                selected = st.multiselect(f"{col}", sorted(df_original[col].unique()), default=[], key=f"f_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].isin(selected)]
            elif pd.api.types.is_numeric_dtype(df_original[col]) and col != 'FCOUNT':
                minv, maxv = int(df_original[col].min()), int(df_original[col].max())
                rng = st.slider(col, minv, maxv, (minv, maxv), key=f"f_{col}")
                filtered_df = filtered_df[(filtered_df[col] >= rng[0]) & (filtered_df[col] <= rng[1])]
            else:
                opts = sorted(df_original[col].dropna().astype(str).unique())
                selected = st.multiselect(f"{col}", opts, default=[], key=f"f_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

    # ====================== METRICS ======================
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Records", f"{len(filtered_df):,}")
    with c2:
        st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
    with c3:
        top_st = filtered_df.groupby('STATION')['FCOUNT'].sum().idxmax() if not filtered_df.empty else "-"
        st.metric("Top Station", top_st)
    with c4:
        st.metric("Peak FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}")

    # Charts
    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader("Top 15 Stations by FCOUNT")
        if not filtered_df.empty:
            top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
            fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT',
                         color='FCOUNT', color_continuous_scale='RdYlGn_r')
            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(height=520, xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.subheader("Station-wise Summary")
        if not filtered_df.empty:
            summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                Total_FCOUNT='sum', Records='count'
            ).sort_values('Total_FCOUNT', ascending=False)
            st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                        .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                        use_container_width=True)

    # Detailed Records + Download
    st.divider()
    st.subheader("📋 Detailed Records")

    if filtered_df.empty:
        st.warning("No records match the selected filters.")
    else:
        display_df = filtered_df.copy()
        if 'Date' in display_df.columns:
            display_df['Date'] = display_df['Date'].dt.date

        st.dataframe(
            display_df.style.format({"FCOUNT": "{:,}"}),
            use_container_width=True, 
            hide_index=True
        )

        st.markdown("---")
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button("🔄 Refresh Latest Data", type="primary", use_container_width=True):
                refresh_data()

        # Professional Excel Download (Same as previous improved version)
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

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division | Data Logger Exceptional Reports")
