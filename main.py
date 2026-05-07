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
station_coords = { ... }   # Keep your existing station_coords dictionary here

# ====================== LOGIN & DATA LOAD (unchanged) ======================
def login_page():
    # ... (keep your existing login_page function)
    pass

@st.cache_data(ttl=300)
def load_data_from_gsheet():
    # ... (keep your existing function)
    pass

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

    tab_overview, tab_map = st.tabs(["📊 Overview Dashboard", "🗺️ Map View"])

    # ====================== FILTER FUNCTION (Single Source of Truth) ======================
    def get_filtered_df():
        with st.expander("🔍 Live Filters", expanded=True):
            col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])

            with col_f1:
                search_term = st.text_input("🔎 Global Search", 
                                          placeholder="Search station, error...", 
                                          key="global_search_key")
            with col_f2:
                stations = sorted(df_original['STATION'].dropna().unique().tolist()) if 'STATION' in df_original.columns else []
                selected_stations = st.multiselect("Select Stations", 
                                                 options=stations, 
                                                 default=[], 
                                                 placeholder="All Stations",
                                                 key="station_filter_key")
            with col_f3:
                categories = sorted(df_original['Category'].dropna().unique().tolist()) if 'Category' in df_original.columns else []
                selected_categories = st.multiselect("Select Categories", 
                                                   options=categories, 
                                                   default=[], 
                                                   placeholder="All Categories",
                                                   key="category_filter_key")
            with col_f4:
                if st.button("Clear All Filters", use_container_width=True):
                    for key in ["global_search_key", "station_filter_key", "category_filter_key", "from_date_key", "to_date_key"]:
                        if key in st.session_state:
                            st.session_state[key] = [] if "filter" in key else ""
                    st.rerun()

            filtered = df_original.copy()

            if search_term:
                mask = pd.Series(False, index=filtered.index)
                for col in filtered.columns:
                    mask |= filtered[col].astype(str).str.contains(search_term, case=False, na=False)
                filtered = filtered[mask]

            if selected_stations:
                filtered = filtered[filtered['STATION'].isin(selected_stations)]

            if selected_categories and 'Category' in filtered.columns:
                filtered = filtered[filtered['Category'].isin(selected_categories)]

            if 'Date' in filtered.columns and not filtered.empty:
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    from_date = st.date_input("From Date", 
                                            value=filtered['Date'].min().date(), 
                                            key="from_date_key")
                with col_d2:
                    to_date = st.date_input("To Date", 
                                          value=filtered['Date'].max().date(), 
                                          key="to_date_key")
                
                filtered = filtered[
                    (filtered['Date'].dt.date >= from_date) &
                    (filtered['Date'].dt.date <= to_date)
                ]
            return filtered

    # ====================== TAB 1: OVERVIEW DASHBOARD ======================
    with tab_overview:
        st.subheader("📊 Overview Dashboard")
        filtered_df = get_filtered_df()

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Total Records", f"{len(filtered_df):,}")
        with c2: st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
        with c3:
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
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

        # Error & Category Summaries
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if 'Error' in filtered_df.columns and not filtered_df.empty:
                st.markdown('<p class="section-header">Error Summary</p>', unsafe_allow_html=True)
                error_sum = filtered_df.groupby('Error').agg(
                    Total_FCOUNT=('FCOUNT', 'sum'), 
                    Occurrences=('FCOUNT', 'count')
                ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                st.dataframe(error_sum.style.format({"Total_FCOUNT": "{:,}", "Occurrences": "{:,}"})
                            .background_gradient(subset=['Total_FCOUNT'], cmap='Reds'), use_container_width=True)

        with col_s2:
            if 'Category' in filtered_df.columns and not filtered_df.empty:
                st.markdown('<p class="section-header">Category Summary</p>', unsafe_allow_html=True)
                cat_sum = filtered_df.groupby('Category').agg(
                    Total_FCOUNT=('FCOUNT', 'sum'), 
                    Occurrences=('FCOUNT', 'count')
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

            # Download Button
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

                    # Formatting
                    for sheet_name, df_sheet in [('Filtered_Records', display_df), ('Station_Summary', station_summary)]:
                        if sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            header_format = writer.book.add_format({
                                'bold': True, 'bg_color': '#003087', 'font_color': 'white',
                                'border': 1, 'align': 'center', 'valign': 'vcenter'
                            })
                            for col_num, value in enumerate(df_sheet.columns):
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

    # ====================== TAB 2: MAP VIEW ======================
    with tab_map:
        st.subheader("🗺️ Interactive Map View")
        filtered_df = get_filtered_df()

        col_m1, col_m2 = st.columns([3, 2])
        with col_m1:
            if filtered_df.empty or 'STATION' not in filtered_df.columns:
                st.warning("No data available.")
            else:
                # Map code (same as before)
                map_agg = filtered_df.groupby('STATION')['FCOUNT'].sum().reset_index()
                # ... (keep your existing map creation logic)
                m = folium.Map(location=[17.85, 75.80], zoom_start=7.2, tiles="CartoDB positron")
                # ... add markers
                st_folium(m, width=900, height=650, key="folium_map_key")

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
        if not filtered_df.empty:
            display_df = filtered_df.copy()
            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date
            st.dataframe(display_df.style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
