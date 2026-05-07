# datalogger_streamlit.py
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium

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
</style>
""", unsafe_allow_html=True)

# ====================== CONFIG ======================
IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/testing/main/Central%20Railway%20Logo.png"
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== STATION COORDINATES ======================
station_coords = {
    "SUR": {"lat": 17.66461685325021, "lon": 75.8934378261056, "code": "SUR"},
    "KWV": {"lat": 18.09222393527959, "lon": 75.41722014404814, "code": "KWV"},
    "HG": {"lat": 17.550, "lon": 76.000, "code": "HG"},
    "MO": {"lat": 17.810, "lon": 75.640, "code": "MO"},
    "AKOR": {"lat": 17.520, "lon": 76.200, "code": "AKOR"},
    "BALE": {"lat": 17.680, "lon": 75.950, "code": "BALE"},
    "PK": {"lat": 17.620, "lon": 75.920, "code": "PK"},
    "PVR": {"lat": 17.670, "lon": 75.330, "code": "PVR"},
    "BTW": {"lat": 18.230, "lon": 75.410, "code": "BTW"},
    "LUR": {"lat": 18.400, "lon": 76.570, "code": "LUR"},
    "KLBG": {"lat": 17.330, "lon": 76.830, "code": "KLBG"},,
    "WADI": {"lat": 17.05303569516522, "lon": 76.99204755925912, "code": "WADI"},
    "DD": {"lat": 18.460, "lon": 74.580, "code": "DD"},
    "DRSV": {"lat": 18.180, "lon": 76.040, "code": "UMD"},
    "TKWD": {"lat": 17.700, "lon": 75.880, "code": "TKWD"},
    "MA": {"lat": 18.000, "lon": 75.520, "code": "MA"},
    "KEM": {"lat": 18.150, "lon": 75.350, "code": "KEM"},
    "JEUR": {"lat": 18.300, "lon": 75.250, "code": "JEUR"},
    "PUNE": {"lat": 18.530, "lon": 73.870, "code": "PUNE"},
    "BGVN": {"lat": 18.300, "lon": 74.250, "code": "BGVN"},
}

# ====================== LOGIN ======================
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

    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_data()

    df_original = load_data_from_gsheet()

    tab_overview, tab_map, tab_charts, tab_data = st.tabs([
        "📊 Overview", "🗺️ Interactive Map", "📈 Charts", "📋 Detailed Records"
    ])

    # Live Filters
    with st.expander("🔍 Live Filters", expanded=True):
        search_term = st.text_input("🔎 Global Search", placeholder="Search station, error...", key="global_search")
        filtered_df = df_original.copy()
        if search_term:
            mask = pd.Series(False, index=filtered_df.index)
            for col in filtered_df.columns:
                mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[mask]

        if 'Date' in filtered_df.columns and not filtered_df.empty:
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                from_date = st.date_input("From Date", value=filtered_df['Date'].min().date())
            with col_d2:
                to_date = st.date_input("To Date", value=filtered_df['Date'].max().date())
            filtered_df = filtered_df[
                (filtered_df['Date'].dt.date >= from_date) &
                (filtered_df['Date'].dt.date <= to_date)
            ]

    # TAB 1: OVERVIEW
    with tab_overview:
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Records", f"{len(filtered_df):,}")
        with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
        with c3:
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                top_row = filtered_df.loc[filtered_df['FCOUNT'].idxmax()]
                st.metric("Top Station", top_row['STATION'], f"{top_row['FCOUNT']:,}")
        with c4: st.metric("Max FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}")

    # TAB 2: INTERACTIVE MAP
    with tab_map:
        st.subheader("🗺️ Solapur Division Interactive Map")
        st.caption("Click on any station marker to filter the entire dashboard")

        if filtered_df.empty or 'STATION' not in filtered_df.columns:
            st.warning("No data available.")
        else:
            st.info(f"**Stations in current data:** {filtered_df['STATION'].nunique()}")

            map_agg = filtered_df.groupby('STATION')['FCOUNT'].sum().reset_index()

            map_data = []
            for _, row in map_agg.iterrows():
                station_name = str(row['STATION']).strip()
                station_upper = station_name.upper()
                
                best_match = None
                for coord_name, info in station_coords.items():
                    coord_upper = coord_name.upper()
                    if station_upper == coord_upper:           # Exact match first
                        best_match = info
                        break
                    elif coord_upper in station_upper or station_upper in coord_upper:
                        best_match = info
                
                if best_match:
                    map_data.append({
                        'STATION': station_name,
                        'FCOUNT': row['FCOUNT'],
                        'lat': best_match['lat'],
                        'lon': best_match['lon']
                    })

            map_df = pd.DataFrame(map_data)

            if map_df.empty:
                st.error("No matching stations found.")
                st.write("Stations in data:", sorted(filtered_df['STATION'].unique()[:20]))
            else:
                # Create Map
                m = folium.Map(location=[17.85, 75.80], zoom_start=7.2, tiles="CartoDB positron")

                max_fcount = map_df['FCOUNT'].max() if not map_df.empty else 1
                for _, row in map_df.iterrows():
                    intensity = row['FCOUNT'] / max_fcount if max_fcount > 0 else 0
                    color = "darkred" if intensity > 0.7 else "red" if intensity > 0.4 else "orange"

                    popup_html = f"""
                    <h4>{row['STATION']}</h4>
                    <b>FCOUNT:</b> {int(row['FCOUNT']):,}<br>
                    <b>Records:</b> {len(filtered_df[filtered_df['STATION'] == row['STATION']])}
                    """

                    folium.CircleMarker(
                        location=[row['lat'], row['lon']],
                        radius=12 + intensity * 18,
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=f"{row['STATION']} ({int(row['FCOUNT']):,})",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.85
                    ).add_to(m)

                map_return = st_folium(m, width=1350, height=720, key="solapur_map_final")

                if map_return and map_return.get("last_object_clicked"):
                    lat = map_return["last_object_clicked"]["lat"]
                    lon = map_return["last_object_clicked"]["lng"]

                    map_df['dist'] = ((map_df['lat'] - lat)**2 + (map_df['lon'] - lon)**2)**0.5
                    selected_station = map_df.loc[map_df['dist'].idxmin(), 'STATION']

                    st.success(f"✅ Filtered to Station: **{selected_station}**")
                    filtered_df = filtered_df[filtered_df['STATION'] == selected_station]

    # TAB 3: CHARTS
    with tab_charts:
        col_c1, col_c2 = st.columns([3, 2])
        with col_c1:
            st.subheader("Top 15 Stations by FCOUNT")
            if not filtered_df.empty:
                top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
                fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT',
                             color='FCOUNT', color_continuous_scale='RdYlGn_r')
                fig.update_layout(height=520, xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

        with col_c2:
            st.subheader("Station Summary")
            if not filtered_df.empty:
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Records='count'
                ).sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                            use_container_width=True)

    # TAB 4: DETAILED RECORDS
    with tab_data:
        st.subheader("📋 Detailed Records")
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date
            st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}),
                        use_container_width=True, hide_index=True)

            st.markdown("---")
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Records='count'
                ).reset_index()
                summary.to_excel(writer, index=False, sheet_name='Station_Summary')

            output.seek(0)
            st.download_button(
                label="⬇️ Download Excel Report",
                data=output.getvalue(),
                file_name=f"Datalogger_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
