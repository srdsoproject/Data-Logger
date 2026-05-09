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
    .subtitle { font-size: 1.4rem; color: #003087; text-align: center; font-weight: 500; margin-top: -0.4rem; }
    .section-header { font-size: 1.6rem; font-weight: 600; color: #003087; margin: 1.2rem 0 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ====================== CONFIG ======================
IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/testing/main/Central%20Railway%20Logo.png"
SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== STATION COORDINATES ======================
station_coords = {
    "WADI": {"lat": 17.05303569516522, "lon": 76.99204755925912},
    "SDB": {"lat": 17.12207211329687, "lon": 76.94370232393466},
    "MR": {"lat": 17.199884316888113, "lon": 76.90242140933267},
    "HQR": {"lat": 17.258329320477387, "lon": 76.87213360102963},
    "KLBG": {"lat": 17.31464128074813, "lon": 76.82539943154254},
    "TJSP": {"lat": 17.38155787142842, "lon": 76.83078651026582},
    "BBD": {"lat": 17.336940866375414, "lon":76.7792743961494},
    "SVG": {"lat": 17.33968072788599, "lon":76.71139619013732},
    "HHD": {"lat": 17.352700945672176, "lon":76.64674999614954},
    "GUR": {"lat": 17.340847607132325, "lon":76.5895995384797},
    "KUI": {"lat": 17.357481126320312, "lon":76.47050033971526},
    "DUD": {"lat": 17.36262542350625, "lon":76.38023255381961},
    "NGS": {"lat": 17.429201164736277, "lon":76.18296853848099},
    "BOT": {"lat": 17.395116057678774, "lon":76.25531964887394},
    "AKOR": {"lat": 17.450540923674154, "lon": 76.13878780964653},
    "TLT": {"lat": 17.529150347297044, "lon": 76.03601785680922},
    "HG STN": {"lat": 17.565461287426693, "lon": 75.9894306025621},
    "HG-A": {"lat": 17.555916499098096, "lon": 76.00138432588585},
    "TKWD": {"lat": 17.615367249178764, "lon": 75.93344533709772},
    "SUR": {"lat": 17.66461685325021, "lon": 75.8934378261056},
    "BALE": {"lat": 17.67603540641838, "lon": 75.84576721149409},
    "PK": {"lat": 17.725604941699864, "lon": 75.77920258081592},
    "MVE": {"lat": 17.742039265808994, "lon": 75.70628187232433},
    "MO": {"lat": 17.805775747199327, "lon": 75.67562640965197},
    "MKPT": {"lat": 17.876348021475454, "lon": 75.63508125440458},
    "AAG": {"lat": 17.928577532396076, "lon": 75.60830992499343},
    "WKA": {"lat": 17.98027395125776, "lon": 75.58849669615935},
    "MA": {"lat": 18.030290184953223, "lon": 75.54656926732524},
    "WDS": {"lat": 18.06648098233323, "lon": 75.4889207249956},
    "KWV": {"lat": 18.09222393527959, "lon": 75.41722014404814},
    "DHS": {"lat": 18.12955847910344, "lon": 75.33424703664774},
    "KEM": {"lat": 18.176853463202423, "lon": 75.27468572499728},
    "BLNI": {"lat": 18.210581627334815, "lon": 75.20717558551391},
    "JEUR": {"lat": 18.260861679574607, "lon": 75.16233780965912},
    "PPJ": {"lat": 18.291563656218496, "lon": 75.09802889616424},
    "WSB": {"lat": 18.280298357551207, "lon":75.01623199616414},
    "KEU": {"lat": 18.290095464926527, "lon":74.95250352348742},
    "JNTR": {"lat": 18.324947721792178, "lon":74.8776102384951},
    "BGVN": {"lat": 18.316891480050153, "lon":74.77494537837337},
    "MLM": {"lat": 18.368948833491366, "lon":74.72444118537874},
    "BRB": {"lat": 18.407915112523582, "lon":74.6490078310967},
    "MRJ": {"lat": 16.81963598398112, "lon": 74.63884656730691},
    "BLWD": {"lat": 16.816450353858315, "lon": 74.6848784309091},
    "BDK": {"lat": 16.82260514883158, "lon": 74.73242941035451},
    "ARAG": {"lat": 16.822915416337786, "lon": 74.78885649248846},
    "BLNK": {"lat": 16.851881572150898, "lon": 74.87035305369132},
    "SGRE": {"lat": 16.89299615360604, "lon": 74.90379065076426},
    "AGDl": {"lat": 16.95511622318343, "lon": 74.9217523566787},
    "KVK": {"lat": 16.993451321113707, "lon": 74.93640413701563},
    "LNP": {"lat": 17.08409186087585, "lon": 74.96648999614565},
    "DLGN": {"lat": 17.12248941189781, "lon": 74.99090321680957},
    "GLV": {"lat": 17.172780301899458, "lon": 75.05616359877327},
    "JTRD": {"lat": 17.218097953252496, "lon": 75.11167313571244},
    "MSDG": {"lat": 17.269767344711966, "lon": 75.13869487464056},
    "JVA": {"lat": 17.29927168818127, "lon": 75.15831072498368},
    "WSD": {"lat": 17.37772780658702, "lon": 75.14796632741995},
    "SGLA": {"lat": 17.436927805442046, "lon": 75.18841716855994},
    "BMNI": {"lat": 17.510679238270942, "lon": 75.23653144358765},
    "BHLI": {"lat": 17.588890463817744, "lon": 75.27444374355429},
    "PVR": {"lat": 17.66895109379127, "lon": 75.31975306090992},
    "BBV": {"lat": 17.76904752111648, "lon": 75.39791698431098},
    "AHI": {"lat": 17.845027674667048, "lon": 75.40338896837972},
    "MLB": {"lat": 17.91701602096594, "lon": 75.40538340426733},
    "PSS": {"lat": 18.000856885777456, "lon": 75.38989817631149},
    "LAUL": {"lat": 18.03355629204764, "lon": 75.39532863007801},
    "CNHL": {"lat": 18.099881017907574, "lon": 75.45785352269934},
    "MGO": {"lat": 18.1096021568062, "lon": 75.49542122315127},
    "SEI": {"lat": 18.149389148247096, "lon": 75.59026142499687},
    "UPI": {"lat": 18.179945557118465, "lon": 75.6356972899416},
    "BTW": {"lat": 18.240970610084844, "lon": 75.71804892625418},
    "KCB": {"lat": 18.279056755382747, "lon": 75.78166860372836},
    "PJR": {"lat": 18.283948752266966, "lon": 75.86723131577448},
    "DRSV": {"lat": 18.247878328931048, "lon": 76.02287892615388},
    "YSI": {"lat": 18.317606171075578, "lon": 75.97700896898456},
    "KRMD": {"lat": 18.371892606761342, "lon": 76.04928088248217},
    "DKY": {"lat": 18.353691655460597, "lon": 76.10311836170408},
    "TER": {"lat": 18.35266581335599, "lon": 76.15005236994277},
    "PCP": {"lat": 18.3584179274254, "lon": 76.19327000536276},
    "MRX": {"lat": 18.380274853550898, "lon": 76.25111538019095},
    "NEI": {"lat": 18.3873686007519, "lon": 76.31091170451272},
    "OSA": {"lat": 18.378479646870694, "lon": 76.40761212644625},
    "HGL": {"lat": 18.390199985034297, "lon": 76.49591856320265},
    "LUR": {"lat": 18.429426709423403, "lon": 76.5560806337212},
    "BANL": {"lat": 18.44605226022196, "lon": 76.67840203837198},
    "GANI": {"lat": 18.479267109518492, "lon": 76.76394964918596},
    "DD": {"lat": 18.46377428753149, "lon": 74.57928783698621},
}

# ====================== SESSION STATE ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "map_selected_station" not in st.session_state:
    st.session_state.map_selected_station = None

# ====================== LOGIN & LOAD DATA ======================
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

@st.cache_data(ttl=600, show_spinner="Loading latest data from Google Sheets...")
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
            df['Month'] = df['Date'].dt.strftime('%B')
       
        return df
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.stop()

def refresh_data():
    st.cache_data.clear()
    st.session_state.map_selected_station = None
    st.success("✅ Data refreshed successfully!")
    st.rerun()

# ====================== MAIN APP ======================
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

    # ====================== LIVE FILTERS ======================
    st.markdown("### 🔍 Live Filters")
    col_f1 = st.columns([2, 2, 2, 2])
    with col_f1[0]:
        stations = sorted(df_original['STATION'].dropna().unique().tolist()) if 'STATION' in df_original.columns else []
        selected_stations = st.multiselect("STATION", options=stations, default=[], key="stn_key")
    with col_f1[1]:
        errors = sorted(df_original['Error'].dropna().unique().tolist()) if 'Error' in df_original.columns else []
        selected_errors = st.multiselect("Error", options=errors, default=[], key="err_key")
    with col_f1[2]:
        categories = sorted(df_original['Category'].dropna().unique().tolist()) if 'Category' in df_original.columns else []
        selected_categories = st.multiselect("Category", options=categories, default=[], key="cat_key")
    with col_f1[3]:
        months = sorted(df_original['Month'].dropna().unique().tolist()) if 'Month' in df_original.columns else []
        selected_months = st.multiselect("Month", options=months, default=[], key="month_key")

    col_f2 = st.columns([2, 2, 2, 2])
    with col_f2[0]:
        fcount_list = sorted(df_original['FCOUNT'].dropna().unique().tolist()) if 'FCOUNT' in df_original.columns else []
        selected_fcount = st.multiselect("FCOUNT", options=fcount_list, default=[], key="fcount_key")
    with col_f2[1]:
        fault_list = sorted(df_original['FAULT MESSAGE'].dropna().unique().tolist()) if 'FAULT MESSAGE' in df_original.columns else []
        selected_fault = st.multiselect("FAULT MESSAGE", options=fault_list, default=[], key="fault_key")
    with col_f2[2]:
        remark_list = sorted(df_original['REMARK'].dropna().unique().tolist()) if 'REMARK' in df_original.columns else []
        selected_remark = st.multiselect("REMARK", options=remark_list, default=[], key="remark_key")
    with col_f2[3]:
        time_list = sorted(df_original['TIMEDETAILS'].dropna().unique().tolist()) if 'TIMEDETAILS' in df_original.columns else []
        selected_time = st.multiselect("TIMEDETAILS", options=time_list, default=[], key="time_key")

    col_date = st.columns([2, 2, 1])
    with col_date[0]:
        from_date = st.date_input("From Date", 
                                  value=df_original['Date'].min().date() if not df_original.empty else pd.Timestamp.now().date(), 
                                  key="from_date_key")
    with col_date[1]:
        to_date = st.date_input("To Date", 
                                value=df_original['Date'].max().date() if not df_original.empty else pd.Timestamp.now().date(), 
                                key="to_date_key")

    st.divider()

    # ====================== APPLY FILTERS ======================
    filtered_df = df_original.copy()

    if 'Date' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['Date'].dt.date >= from_date) &
            (filtered_df['Date'].dt.date <= to_date)
        ]

    if selected_stations:
        filtered_df = filtered_df[filtered_df['STATION'].isin(selected_stations)]
    if selected_errors and 'Error' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Error'].isin(selected_errors)]
    if selected_categories and 'Category' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Category'].isin(selected_categories)]
    if selected_months and 'Month' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Month'].isin(selected_months)]
    if selected_fcount and 'FCOUNT' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['FCOUNT'].isin(selected_fcount)]
    if selected_fault and 'FAULT MESSAGE' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['FAULT MESSAGE'].isin(selected_fault)]
    if selected_remark and 'REMARK' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['REMARK'].isin(selected_remark)]
    if selected_time and 'TIMEDETAILS' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['TIMEDETAILS'].isin(selected_time)]

    # Map Selection Override
    if st.session_state.map_selected_station:
        filtered_df = filtered_df[filtered_df['STATION'] == st.session_state.map_selected_station]

    st.divider()

    # ====================== TABS ======================
    tab_overview, tab_map = st.tabs(["📊 Overview Dashboard", "🗺️ Map View"])

    with tab_overview:
        st.subheader("📊 Overview Dashboard")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Records", f"{len(filtered_df):,}")
        with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
        with c3:
            if not filtered_df.empty and 'STATION' in filtered_df.columns and not filtered_df['FCOUNT'].empty:
                top_row = filtered_df.loc[filtered_df['FCOUNT'].idxmax()]
                st.metric("Top Station", top_row['STATION'], f"{top_row['FCOUNT']:,}")
        with c4: st.metric("Max FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).max():,}")

        st.markdown("---")
        col_g1, col_g2 = st.columns([3, 2])
        with col_g1:
            st.markdown('<p class="section-header">Top 15 Stations by FCOUNT</p>', unsafe_allow_html=True)
            if not filtered_df.empty:
                top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
                fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT',
                             color='FCOUNT', color_continuous_scale='RdYlGn_r')
                fig.update_layout(height=520, xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

        with col_g2:
            st.markdown('<p class="section-header">Station Summary</p>', unsafe_allow_html=True)
            if not filtered_df.empty:
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Records='count'
                ).sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                            use_container_width=True)

        # Error & Category Summary
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if 'Error' in filtered_df.columns and not filtered_df.empty:
                st.markdown('<p class="section-header">Error Summary</p>', unsafe_allow_html=True)
                error_sum = filtered_df.groupby('Error').agg(
                    Total_FCOUNT=('FCOUNT', 'sum'), Occurrences=('FCOUNT', 'count')
                ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                st.dataframe(error_sum.style.format({"Total_FCOUNT": "{:,}", "Occurrences": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='Reds'), use_container_width=True)
        with col_s2:
            if 'Category' in filtered_df.columns and not filtered_df.empty:
                st.markdown('<p class="section-header">Category Summary</p>', unsafe_allow_html=True)
                cat_sum = filtered_df.groupby('Category').agg(
                    Total_FCOUNT=('FCOUNT', 'sum'), Occurrences=('FCOUNT', 'count')
                ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                st.dataframe(cat_sum.style.format({"Total_FCOUNT": "{:,}", "Occurrences": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='Oranges'), use_container_width=True)

        st.markdown("---")
        st.markdown('<p class="section-header">Detailed Records</p>', unsafe_allow_html=True)
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date
            st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

            # Download Section
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 3, 1])
            with col_btn2:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                    station_summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                        Total_FCOUNT='sum', Record_Count='count'
                    ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                    station_summary.to_excel(writer, index=False, sheet_name='Station_Summary')
                    if 'Error' in filtered_df.columns:
                        error_sum.to_excel(writer, index=False, sheet_name='Error_Summary')
                    if 'Category' in filtered_df.columns:
                        cat_sum.to_excel(writer, index=False, sheet_name='Category_Summary')

                    for sheet_name, df_sheet in [('Filtered_Records', display_df), ('Station_Summary', station_summary)]:
                        if sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            header_format = writer.book.add_format({
                                'bold': True, 'bg_color': '#003087', 'font_color': 'white',
                                'border': 1, 'align': 'center', 'valign': 'vcenter'
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
                    file_name=f"Datalogger_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

    with tab_map:
        st.subheader("🗺️ Interactive Map View - Click on Station to Filter")

        # Clear Selection Button
        if st.session_state.map_selected_station:
            col_clear1, col_clear2 = st.columns([1, 5])
            with col_clear1:
                if st.button("🔄 Clear Station Selection", type="secondary", use_container_width=True):
                    st.session_state.map_selected_station = None
                    st.rerun()
            st.success(f"📍 Currently viewing: **{st.session_state.map_selected_station}**")

        col_m1, col_m2 = st.columns([3, 2])
       
        with col_m1:
            if filtered_df.empty or 'STATION' not in filtered_df.columns:
                st.warning("No data available.")
            else:
                map_agg = filtered_df.groupby('STATION')['FCOUNT'].sum().reset_index()
                map_data = []
               
                for _, row in map_agg.iterrows():
                    station_name = str(row['STATION']).strip().upper()
                    best_match = next((info for name, info in station_coords.items()
                                     if name.upper() == station_name or name.upper() in station_name), None)
                    if best_match:
                        map_data.append({
                            'STATION': row['STATION'],
                            'FCOUNT': row['FCOUNT'],
                            'lat': best_match['lat'],
                            'lon': best_match['lon']
                        })
               
                map_df = pd.DataFrame(map_data)
               
                if not map_df.empty:
                    m = folium.Map(location=[17.85, 75.80], zoom_start=7.2, tiles=None)
                   
                    folium.TileLayer("CartoDB positron", name="Light (Default)", control=True).add_to(m)
                    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", control=True).add_to(m)
                    folium.TileLayer(
                        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                        attr="Esri World Imagery", name="🌐 Satellite (Esri)", control=True
                    ).add_to(m)
                    folium.TileLayer(
                        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
                        attr="Google Hybrid", name="🛰️ Google Satellite + Labels", control=True
                    ).add_to(m)
                    folium.TileLayer(
                        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                        attr="Google Satellite", name="🛰️ Google Satellite (No Labels)", control=True
                    ).add_to(m)
                   
                    folium.LayerControl(position="topright", collapsed=False).add_to(m)
                    folium.plugins.Fullscreen(position="topleft", title="Expand Map", title_cancel="Exit Fullscreen").add_to(m)
                   
                    max_f = map_df['FCOUNT'].max() or 1
                    for _, row in map_df.iterrows():
                        intensity = row['FCOUNT'] / max_f
                        color = "darkred" if intensity > 0.7 else "red" if intensity > 0.4 else "orange"
                       
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']],
                            radius=12 + intensity * 18,
                            popup=f"<h4>{row['STATION']}</h4><b>FCOUNT:</b> {int(row['FCOUNT']):,}",
                            tooltip=f"{row['STATION']} ({int(row['FCOUNT']):,})",
                            color=color, fill=True, fill_color=color, fill_opacity=0.85
                        ).add_to(m)
                   
                    map_return = st_folium(m, width=900, height=650, key="folium_key")
                   
                    if map_return and map_return.get("last_object_clicked"):
                        lat = map_return["last_object_clicked"]["lat"]
                        lon = map_return["last_object_clicked"]["lng"]
                        map_df['dist'] = ((map_df['lat'] - lat)**2 + (map_df['lon'] - lon)**2)**0.5
                        selected_station = map_df.loc[map_df['dist'].idxmin(), 'STATION']
                       
                        if st.session_state.map_selected_station != selected_station:
                            st.session_state.map_selected_station = selected_station
                            st.rerun()

        with col_m2:
            st.subheader("Station Summary")
            if not filtered_df.empty:
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                    Total_FCOUNT='sum', Records='count'
                ).sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'),
                            use_container_width=True)

        st.markdown("---")
        st.subheader("Detailed Records")
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date
            st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

            # Download Section for Map Tab
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 3, 1])
            with col_btn2:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                    station_summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                        Total_FCOUNT='sum', Record_Count='count'
                    ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                    station_summary.to_excel(writer, index=False, sheet_name='Station_Summary')

                    if 'Error' in filtered_df.columns:
                        error_sum = filtered_df.groupby('Error').agg(
                            Total_FCOUNT=('FCOUNT', 'sum'), Occurrences=('FCOUNT', 'count')
                        ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                        error_sum.to_excel(writer, index=False, sheet_name='Error_Summary')
                    if 'Category' in filtered_df.columns:
                        cat_sum = filtered_df.groupby('Category').agg(
                            Total_FCOUNT=('FCOUNT', 'sum'), Occurrences=('FCOUNT', 'count')
                        ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                        cat_sum.to_excel(writer, index=False, sheet_name='Category_Summary')

                    for sheet_name, df_sheet in [('Filtered_Records', display_df), ('Station_Summary', station_summary)]:
                        if sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            header_format = writer.book.add_format({
                                'bold': True, 'bg_color': '#003087', 'font_color': 'white',
                                'border': 1, 'align': 'center', 'valign': 'vcenter'
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
                    file_name=f"Map_Filtered_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
