# datalogger_streamlit.py
# Professional Indian Railways Data Logger Analyzer - With Login & Google Sheets

import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

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
    .login-box {
        max-width: 400px;
        margin: 50px auto;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# ====================== SECRETS & CONFIG ======================
# These will be stored in .streamlit/secrets.toml

SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]

USERS = st.secrets["users"]   # List of users

# ====================== LOGIN FUNCTION ======================
# ====================== LOGIN FUNCTION (Fixed) ======================
def login_page():
    # Title
    st.markdown('<h1 class="main-header">Safety Branch</h1>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">Central Railway, Solapur Division</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Data-Logger Exceptional Reports Analyzer</p>', unsafe_allow_html=True)

    st.divider()

    # Centered Login Card using Streamlit columns (more reliable than custom div)
    col1, col2, col3 = st.columns([1, 2, 1])   # This centers the box

    with col2:
        st.subheader("🔐 Login to Access Dashboard")
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email / Username", placeholder="SAFETY/SUR", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter Password", key="login_password")
            
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            
            if submitted:
                if email in USERS and password == USERS[email].get("password"):
                    st.session_state.logged_in = True
                    st.session_state.user_name = USERS[email].get("name")
                    st.success(f"Welcome, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password. Please try again.")

    st.caption("🚄 Indian Railways - Solapur Division")

# ====================== LOAD DATA FROM GOOGLE SHEET ======================
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data_from_gsheet():
    try:
        # Define scope
        scope = ["https://spreadsheets.google.com/feeds",
                 "https://www.googleapis.com/auth/drive"]

        # Authorize
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        if df.empty:
            st.error("Google Sheet is empty!")
            st.stop()

        # Clean column names
        df.columns = df.columns.str.strip()

        # Remove Sl.No / Sr.No columns
        df = df.loc[:, ~df.columns.str.lower().str.replace('.', '', regex=False)
                    .str.contains(r'^(sl|sr)\s*no')]

        # Convert FCOUNT to integer
        COLS = {'fcount': 'FCOUNT'}
        if COLS['fcount'] in df.columns:
            df[COLS['fcount']] = pd.to_numeric(df[COLS['fcount']], errors='coerce').fillna(0).astype(int)

        # Convert Date if exists
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        return df

    except Exception as e:
        st.error(f"Failed to load data from Google Sheet: {e}")
        st.stop()


# ====================== MAIN APP ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    # ====================== LOAD DATA ======================
    df_original = load_data_from_gsheet()

    COLS = {
        'station': 'STATION',
        'fcount': 'FCOUNT',
        'month': 'Month',
        'category': 'Category',
        'error': 'Error',
        'date': 'Date'
    }

    # ====================== TITLE ======================
    st.markdown('<h1 class="main-header">Safety Branch</h1>', unsafe_allow_html=True)
    st.markdown('<h1 class="main-header">Central Railway, Solapur Division</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Data-Logger Exceptional Reports Analyzer</p>', unsafe_allow_html=True)
    st.caption(f"Logged in as: **{st.session_state.user_name}**")

    st.divider()

    # ====================== LIVE FILTERS ======================
    st.subheader("🔍 Live Filters")

    filter_cols = st.columns(4)
    filtered_df = df_original.copy()

    for i, col in enumerate(df_original.columns):
        with filter_cols[i % 4]:
            unique_vals = sorted(df_original[col].dropna().unique().astype(str))

            if col == COLS['fcount']:
                selected_fcounts = st.multiselect(
                    f"{col} (Select Values)",
                    options=sorted(df_original[col].unique()),
                    default=[],
                    key=f"filter_{col}"
                )
                if selected_fcounts:
                    filtered_df = filtered_df[filtered_df[col].isin(selected_fcounts)]

            elif pd.api.types.is_numeric_dtype(df_original[col]) and col != COLS['fcount']:
                min_val = int(df_original[col].min())
                max_val = int(df_original[col].max())
                selected_range = st.slider(
                    f"{col}",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val),
                    key=f"filter_{col}"
                )
                filtered_df = filtered_df[
                    (filtered_df[col] >= selected_range[0]) &
                    (filtered_df[col] <= selected_range[1])
                ]

            else:
                selected_vals = st.multiselect(
                    f"{col}",
                    options=unique_vals,
                    default=[],
                    key=f"filter_{col}"
                )
                if selected_vals:
                    filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected_vals)]

    # ====================== METRICS ======================
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Records", f"{len(filtered_df):,}")
    with c2: st.metric("Total FCOUNT", f"{filtered_df[COLS.get('fcount', 'FCOUNT')].sum():,}")
    with c3:
        fcount_col = COLS.get('fcount', 'FCOUNT')
        top_station = filtered_df.groupby(COLS.get('station', 'STATION'))[fcount_col].sum().idxmax() if not filtered_df.empty else "-"
        st.metric("Top Station", top_station)
    with c4: st.metric("Max FCOUNT", f"{filtered_df[fcount_col].max():,}" if not filtered_df.empty else 0)

    st.divider()

    # ====================== CHART ======================
    col_chart, col_table = st.columns([3, 2])

    with col_chart:
        st.subheader(f"Top 15 Stations by FCOUNT")
        fcount_col = COLS.get('fcount', 'FCOUNT')
        station_col = COLS.get('station', 'STATION')

        if not filtered_df.empty:
            top_df = (filtered_df.groupby(station_col)[fcount_col]
                      .sum()
                      .sort_values(ascending=False)
                      .head(15)
                      .reset_index())

            fig = px.bar(
                top_df,
                x=station_col,
                y=fcount_col,
                text=fcount_col,
                color=fcount_col,
                color_continuous_scale=['#00FF00', '#FF7F00', '#FF0000'],  # Green → Orange → Red
                range_color=[top_df[fcount_col].min(), top_df[fcount_col].max()]
            )

            fig.update_traces(texttemplate='%{text:,}', textposition='outside')
            fig.update_layout(height=550, xaxis_tickangle=45, coloraxis_colorbar_title="FCOUNT Intensity")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No data available.")

    with col_table:
        st.subheader("Summary Table")
        if not filtered_df.empty:
            summary = (filtered_df.groupby(station_col)[fcount_col]
                       .agg(Total_FCOUNT='sum', Record_Count='count')
                       .sort_values('Total_FCOUNT', ascending=False)
                       .reset_index())

            st.dataframe(
                summary.style.format({"Total_FCOUNT": "{:,}", "Record_Count": "{:,}"})
                           .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                use_container_width=True,
                hide_index=True
            )

    # ====================== DETAILED RECORDS ======================
    st.divider()
    st.subheader("📋 Detailed Records")

    if filtered_df.empty:
        st.warning("No records match your current filters.")
    else:
        display_df = filtered_df.copy()

        # Remove Sl.No if exists
        sl_col = next((col for col in display_df.columns 
                       if str(col).strip().lower() in ["sl.no.", "sl no", "slno", "s.no", "sr no"]), None)
        if sl_col:
            display_df = display_df.drop(columns=[sl_col])

        if 'Date' in display_df.columns:
            display_df['Date'] = display_df['Date'].dt.date

        st.dataframe(
            display_df.style.format({fcount_col: "{:,}"}),
            use_container_width=True,
            hide_index=True
        )

        # Summary by Category & Error
        col1, col2 = st.columns(2)
        with col1:
            if 'Category' in display_df.columns:
                st.markdown("#### Category-wise FCOUNT")
                cat_sum = display_df.groupby('Category')[fcount_col].sum().sort_values(ascending=False)
                st.dataframe(cat_sum.reset_index().style.format({fcount_col: "{:,}"}), 
                           use_container_width=True, hide_index=True)

        with col2:
            if 'Error' in display_df.columns:
                st.markdown("#### Error-wise FCOUNT")
                err_sum = display_df.groupby('Error')[fcount_col].sum().sort_values(ascending=False)
                st.dataframe(err_sum.reset_index().style.format({fcount_col: "{:,}"}), 
                           use_container_width=True, hide_index=True)

        # ====================== DOWNLOAD ======================
        # ====================== DOWNLOAD SECTION ======================
        st.divider()
        st.subheader("📥 Download Filtered Data")
    
        if filtered_df.empty:
            st.warning("No data to download. Please adjust your filters.")
        else:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Main filtered data
                final_download_df = display_df.copy()
                final_download_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
    
                # Station Summary
                summary_df = (filtered_df.groupby(COLS.get('station', 'STATION'))[COLS.get('fcount', 'FCOUNT')]
                              .agg(Total_FCOUNT='sum', Record_Count='count')
                              .sort_values('Total_FCOUNT', ascending=False)
                              .reset_index())
                
                summary_df.to_excel(writer, index=False, sheet_name='Station_Summary')
    
                # Auto-adjust column widths
                for sheet_name, data_df in [('Filtered_Records', final_download_df), ('Station_Summary', summary_df)]:
                    worksheet = writer.sheets[sheet_name]
                    for idx, col in enumerate(data_df.columns):
                        max_len = max(data_df[col].astype(str).map(len).max(), len(str(col))) + 3
                        worksheet.set_column(idx, idx, min(max_len, 60))
    
            output.seek(0)
    
            st.download_button(
                label="⬇️ Download Filtered Report as Excel",
                data=output.getvalue(),
                file_name="Datalogger_Filtered_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    st.caption("🚄 Indian Railways - Solapur Division | Data Logger Exceptional Report Dashboard")
