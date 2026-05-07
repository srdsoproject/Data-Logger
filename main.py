# datalogger_streamlit.py
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

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
    .subtitle { font-size: 1.4rem; color: #003087; text-align: center; font-weight: 500; margin-top: -0.4rem; }
    .map-container { border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ====================== INDIAN RAILWAYS LOGO ======================
IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/testing/main/Central%20Railway%20Logo.png"

# ====================== SECRETS ======================
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== SOLAPUR DIVISION STATION COORDINATES ======================
station_coords = {
    "SOLAPUR": {"lat": 17.664, "lon": 75.893, "code": "SUR"},
    "KURDUWADI": {"lat": 18.090, "lon": 75.415, "code": "KWV"},
    "HOTGI": {"lat": 17.550, "lon": 76.000, "code": "HG"},
    "MOHOL": {"lat": 17.810, "lon": 75.640, "code": "MO"},
    "AKALKOT ROAD": {"lat": 17.520, "lon": 76.200, "code": "AKOR"},
    "BALE": {"lat": 17.680, "lon": 75.950, "code": "BALE"},
    "PAKNI": {"lat": 17.620, "lon": 75.920, "code": "PK"},
    "TIKEKARWADI": {"lat": 17.700, "lon": 75.880, "code": "TKWD"},
    "PANDHARPUR": {"lat": 17.670, "lon": 75.330, "code": "PVR"},
    "BARSHI": {"lat": 18.230, "lon": 75.410, "code": "BTW"},
    "LATUR": {"lat": 18.400, "lon": 76.570, "code": "LUR"},
    "KALABURAGI": {"lat": 17.330, "lon": 76.830, "code": "KLBG"},
    "WADI": {"lat": 17.070, "lon": 76.920, "code": "WADI"},
    "DAUND": {"lat": 18.460, "lon": 74.580, "code": "DD"},
    "AHMEDNAGAR": {"lat": 19.090, "lon": 74.740, "code": "ANG"},
    "SAINAGAR SHIRDI": {"lat": 19.770, "lon": 74.480, "code": "SNSI"},
    "OSMANABAD": {"lat": 18.180, "lon": 76.040, "code": "UMD"},
    # Add more stations as needed
}

# ====================== LOGIN PAGE ======================
def login_page():
    col1, col2, col3 = st.columns([3, 3, 3])
    with col2:
        st.subheader("🔐 Secure Login")
        with st.form("login_form", clear_on_submit=False):
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
    st.success("✅ Data refreshed successfully!")
    st.rerun()

# ====================== MAIN APP ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_page()
else:
    col1, col2, col3 = st.columns([3, 3, 1])
    with col2:
        st.image(IR_LOGO_URL, width=220)
    st.markdown('<h1 class="dashboard-title">DATA LOGGER EXCEPTIONAL REPORT</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Central Railway • Solapur Division • Safety Branch</p>', unsafe_allow_html=True)
    st.caption(f"**Logged in as:** {st.session_state.user_name}")
    st.divider()

    # Sidebar
    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_data()
        st.divider()
        st.info("Live filters applied below.")

    df_original = load_data_from_gsheet()

    # ====================== TABS ======================
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🗺️ Interactive Map", "📈 Charts", "📋 Detailed Records"])

    # ====================== LIVE FILTERS (Common) ======================
    with st.expander("🔍 Live Filters", expanded=True):
        col_search, col_refresh = st.columns([4, 1])
        with col_search:
            search_term = st.text_input("Global Search", placeholder="Search station, error...", key="global_search")
        
        filtered_df = df_original.copy()
        if search_term:
            mask = pd.Series(False, index=filtered_df.index)
            for col in filtered_df.columns:
                mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[mask]

        # Date Filter
        if 'Date' in filtered_df.columns and not filtered_df.empty:
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                from_date = st.date_input("From Date", value=filtered_df['Date'].min().date())
            with col_d2:
                to_date = st.date_input("To Date", value=filtered_df['Date'].max().date())
            filtered_df = filtered_df[(filtered_df['Date'].dt.date >= from_date) & 
                                     (filtered_df['Date'].dt.date <= to_date)]

    # ====================== TAB 1: OVERVIEW ======================
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Records", f"{len(filtered_df):,}")
        with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
        with c3:
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                top = filtered_df.loc[filtered_df['FCOUNT'].idxmax(), 'STATION']
                st.metric("Top Station", top)
        with c4: st.metric("Max FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}")

    # ====================== TAB 2: INTERACTIVE MAP ======================
    with tab2:
        st.subheader("🗺️ Solapur Division - Click Station to Filter Data")
        
        if filtered_df.empty or 'STATION' not in filtered_df.columns:
            st.warning("No data available for map.")
        else:
            # Aggregate data for map
            map_data = filtered_df.groupby('STATION')['FCOUNT'].sum().reset_index()
            map_data = map_data.merge(
                pd.DataFrame.from_dict(station_coords, orient='index').reset_index(),
                left_on='STATION', right_on='index', how='left'
            ).rename(columns={'index': 'STATION'}).dropna(subset=['lat'])

            # Create Map
            m = folium.Map(location=[17.85, 75.8], zoom_start=7.5, tiles="CartoDB positron")

            # Color scale
            max_count = map_data['FCOUNT'].max()
            for _, row in map_data.iterrows():
                intensity = row['FCOUNT'] / max_count if max_count > 0 else 0
                color = 'darkred' if intensity > 0.7 else 'red' if intensity > 0.4 else 'orange'

                popup_html = f"""
                <h4>{row['STATION']}</h4>
                <b>Total FCOUNT:</b> {row['FCOUNT']:,}<br>
                <b>Records:</b> {len(filtered_df[filtered_df['STATION'] == row['STATION']])}
                """

                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=10 + intensity * 15,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{row['STATION']} ({row['FCOUNT']:,})",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85,
                    weight=2
                ).add_to(m)

            # Render Map
            map_return = st_folium(m, width=1300, height=720, returned_objects=["last_object_clicked"])

            # Handle Station Click
            if map_return and map_return.get("last_object_clicked"):
                clicked_lat = map_return["last_object_clicked"]["lat"]
                clicked_lon = map_return["last_object_clicked"]["lng"]

                # Find closest station
                map_data['distance'] = ((map_data['lat'] - clicked_lat)**2 + 
                                      (map_data['lon'] - clicked_lon)**2)**0.5
                selected_station = map_data.loc[map_data['distance'].idxmin(), 'STATION']

                st.success(f"✅ **Filtered to Station: {selected_station}**")
                filtered_df = filtered_df[filtered_df['STATION'] == selected_station]

    # ====================== TAB 3: CHARTS ======================
    with tab3:
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
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Records='count'
                ).sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                            use_container_width=True)

    # ====================== TAB 4: DETAILED RECORDS ======================
    with tab4:
        st.subheader("📋 Detailed Records")
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date
            st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}), 
                        use_container_width=True, hide_index=True)

            # Download Button (same as before)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                # ... (add other sheets as in your original code)
            output.seek(0)
            st.download_button("⬇️ Download Excel Report", 
                              data=output.getvalue(),
                              file_name=f"Datalogger_Report_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              type="primary", use_container_width=True)

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
