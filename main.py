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
    .main-header {font-size: 2.4rem; font-weight: 700; color: #FF9933; text-align: center;}
    .dashboard-title {
        font-size: 2.9rem; 
        font-weight: 800;
        background: linear-gradient(90deg, #FF9933, #003087);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.3rem;
    }
    .subtitle {
        font-size: 1.35rem; 
        color: #003087; 
        text-align: center;
        font-weight: 500;
        margin-top: -0.5rem;
    }
    .stImage {text-align: center;}
</style>
""", unsafe_allow_html=True)

# ====================== INDIAN RAILWAYS LOGO ======================
# More reliable logo URL
IR_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/0/07/Ministry_of_Railways_India.svg"

# ====================== SECRETS & FUNCTIONS (unchanged) ======================
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

def login_page():
    st.image(IR_LOGO_URL, width=220)
    st.markdown('<h1 class="dashboard-title">SAFETY BRANCH</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Central Railway • Solapur Division</p>', unsafe_allow_html=True)
    st.divider()
    # ... (rest of login remains same)
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
    st.success("✅ Data refreshed successfully!")
    st.rerun()

# ====================== MAIN DASHBOARD ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # ====================== PROFESSIONAL HEADER ======================
    header_col1, header_col2 = st.columns([1.2, 5])
    
    with header_col1:
        st.image(IR_LOGO_URL, width=140)
    
    with header_col2:
        st.markdown('<h1 class="dashboard-title">DATA LOGGER EXCEPTIONAL REPORT</h1>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Central Railway • Solapur Division • Safety Branch</p>', unsafe_allow_html=True)

    st.caption(f"**Logged in as:** {st.session_state.user_name}   |   Last Refreshed: Just now")

    st.divider()

    # Sidebar
    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True, key="sidebar_refresh"):
            refresh_data()
        st.divider()
        st.info("Live filters applied below.")

    # Rest of your app (Filters, Metrics, Charts, Detailed Records, Download) remains same...
    df_original = load_data_from_gsheet()

    # ====================== FILTERS ======================
    st.subheader("🔍 Live Filters")
    col1, _ = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "🔎 Global Search", 
            placeholder="Search station, error, category, date...",
            key="global_search"
        )

    filtered_df = df_original.copy()
    if search_term:
        mask = pd.Series(False, index=filtered_df.index)
        for col in filtered_df.columns:
            mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = filtered_df[mask]

    # Column filters (same as before)
    filter_cols = st.columns(4)
    for i, col in enumerate(df_original.columns):
        with filter_cols[i % 4]:
            if col == 'FCOUNT':
                selected = st.multiselect(f"{col}", sorted(df_original[col].unique()), default=[], key=f"filter_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].isin(selected)]
            elif pd.api.types.is_numeric_dtype(df_original[col]) and col != 'FCOUNT':
                minv, maxv = int(df_original[col].min() or 0), int(df_original[col].max() or 0)
                rng = st.slider(col, minv, maxv, (minv, maxv), key=f"filter_{col}")
                filtered_df = filtered_df[(filtered_df[col] >= rng[0]) & (filtered_df[col] <= rng[1])]
            else:
                opts = sorted(df_original[col].dropna().astype(str).unique())
                selected = st.multiselect(f"{col}", opts, default=[], key=f"filter_{col}")
                if selected:
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected)]

    # ... [Rest of your Metrics, Charts, Detailed Records, and Download code remains unchanged] ...

    # (Keep all the remaining code from your previous version - Metrics, Charts, Detailed Records, etc.)
