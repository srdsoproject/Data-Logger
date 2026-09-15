import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen
import re
from difflib import SequenceMatcher

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
    .section-header { 
        font-size: 1.6rem; 
        font-weight: 600; 
        color: #003087; 
        margin: 1.2rem 0 0.5rem 0; 
    }
    .alert-box {
        background-color: #ff4b4b;
        color: white;
        padding: 15px 20px;
        border-radius: 10px;
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 20px;
        text-align: center;
    }

    /* ========== COOL CHATBOT STYLING ========== */
    .chatbot-header {
        background: linear-gradient(135deg, #003087, #0056b3);
        color: white;
        padding: 14px 18px;
        border-radius: 14px 14px 0 0;
        font-size: 1.15rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 0;
        box-shadow: 0 4px 12px rgba(0,48,135,0.25);
    }
    .chatbot-header span {
        background: rgba(255,255,255,0.2);
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .chat-container {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-top: none;
        border-radius: 0 0 14px 14px;
        padding: 16px 14px;
        max-height: 420px;
        overflow-y: auto;
        margin-bottom: 12px;
    }
    .chat-message {
        padding: 12px 16px;
        border-radius: 18px;
        margin-bottom: 12px;
        font-size: 0.95rem;
        line-height: 1.45;
        max-width: 92%;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        position: relative;
    }
    .user-msg {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
        text-align: left;
    }
    .bot-msg {
        background: white;
        color: #1e293b;
        border: 1px solid #e2e8f0;
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }
    .bot-msg b {
        color: #003087;
    }
    .chat-avatar {
        font-size: 1.1rem;
        margin-right: 6px;
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
    "WADI": {"lat": 17.05303569516522, "lon": 76.99204755925912},
    "SDB": {"lat": 17.12207211329687, "lon": 76.94370232393466},
    "MR": {"lat": 17.199884316888113, "lon": 76.90242140933267},
    "HQR": {"lat": 17.258329320477387, "lon": 76.87213360102963},
    "KLBG": {"lat": 17.31464128074813, "lon": 76.82539943154254},
    "TJSP": {"lat": 17.38155787142842, "lon": 76.83078651026582},
    "BBD": {"lat": 17.336940866375414, "lon": 76.7792743961494},
    "SVG": {"lat": 17.33968072788599, "lon": 76.71139619013732},
    "HHD": {"lat": 17.352700945672176, "lon": 76.64674999614954},
    "GUR": {"lat": 17.340847607132325, "lon": 76.5895995384797},
    "KUI": {"lat": 17.357481126320312, "lon": 76.47050033971526},
    "DUD": {"lat": 17.36262542350625, "lon": 76.38023255381961},
    "NGS": {"lat": 17.429201164736277, "lon": 76.18296853848099},
    "BOT": {"lat": 17.395116057678774, "lon": 76.25531964887394},
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
    "WSB": {"lat": 18.280298357551207, "lon": 75.01623199616414},
    "KEU": {"lat": 18.290095464926527, "lon": 74.95250352348742},
    "JNTR": {"lat": 18.324947721792178, "lon": 74.8776102384951},
    "BGVN": {"lat": 18.316891480050153, "lon": 74.77494537837337},
    "MLM": {"lat": 18.368948833491366, "lon": 74.72444118537874},
    "BRB": {"lat": 18.407915112523582, "lon": 74.6490078310967},
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
    "HG": {"lat": 17.565461287426693, "lon": 75.9894306025621},
}

# ====================== JURISDICTION MAPPINGS ======================
ENGG_ADEN = {
    "WADI": "ADEN KLBG", "SDB": "ADEN KLBG", "MR": "ADEN KLBG", "HQR": "ADEN KLBG",
    "KLBG": "ADEN KLBG", "BBD": "ADEN KLBG", "SVG": "ADEN KLBG", "HHD": "ADEN KLBG",
    "GUR": "ADEN KLBG", "KUI": "ADEN KLBG", "TJSP": "ADEN KLBG", "GDGN": "ADEN KLBG",
    "SBD": "ADEN KLBG",
    "AKOR": "ADEN S SUR", "BOT": "ADEN S SUR", "DUD": "ADEN S SUR", "HG": "ADEN S SUR",
    "NGS": "ADEN S SUR", "TKWD": "ADEN S SUR", "TLT": "ADEN S SUR",
    "HG STN": "ADEN S SUR", "HG-A": "ADEN S SUR",
    "AAG": "Sr.ADEN N SUR", "BALE": "Sr.ADEN N SUR", "MA": "Sr.ADEN N SUR", "MKPT": "Sr.ADEN N SUR",
    "MO": "Sr.ADEN N SUR", "MVE": "Sr.ADEN N SUR", "PK": "Sr.ADEN N SUR", "SUR": "Sr.ADEN N SUR",
    "WDS": "Sr.ADEN N SUR", "WKA": "Sr.ADEN N SUR", "MOHOL": "Sr.ADEN N SUR", "PAKNI": "Sr.ADEN N SUR",
    "BGVN": "Sr.ADEN KWV BG", "BLNI": "Sr.ADEN KWV BG", "BRB": "Sr.ADEN KWV BG", "DHS": "Sr.ADEN KWV BG",
    "JEUR": "Sr.ADEN KWV BG", "JNTR": "Sr.ADEN KWV BG", "KEM": "Sr.ADEN KWV BG", "KWV": "Sr.ADEN KWV BG",
    "MLM": "Sr.ADEN KWV BG", "PPJ": "Sr.ADEN KWV BG", "WSB": "Sr.ADEN KWV BG", "KEU": "Sr.ADEN KWV BG",
    "WSD": "Sr.ADEN KWV BG", "DD": "Sr.ADEN KWV BG", "MADHA": "Sr.ADEN KWV BG",
    "PSS": "Sr.ADEN KWV BG", "LAUL": "Sr.ADEN KWV BG", "CNHL": "Sr.ADEN KWV BG", "MGO": "Sr.ADEN KWV BG",
    "ARAG": "ADEN/PVR", "DLGN": "ADEN/PVR", "JTRD": "ADEN/PVR", "KVK": "ADEN/PVR",
    "MLB": "ADEN/PVR", "PVR": "ADEN/PVR", "SGLA": "ADEN/PVR", "SGRE": "ADEN/PVR", "MRJ": "ADEN/PVR",
    "MSDG": "ADEN/PVR", "JVA": "ADEN/PVR", "GLV": "ADEN/PVR", "LNP": "ADEN/PVR", "AGDl": "ADEN/PVR",
    "BLWD": "ADEN/PVR", "BDK": "ADEN/PVR", "BLNK": "ADEN/PVR", "BBV": "ADEN/PVR",
    "AHI": "ADEN/PVR", "BMNI": "ADEN/PVR", "BHLI": "ADEN/PVR",
    "BTW": "ADEN/LUR", "DKY": "ADEN/LUR", "HGL": "ADEN/LUR", "LUR": "ADEN/LUR",
    "OSA": "ADEN/LUR", "PJR": "ADEN/LUR", "SEI": "ADEN/LUR", "YSI": "ADEN/LUR",
    "DRSV": "ADEN/LUR", "MRX": "ADEN/LUR", "LTRR": "ADEN/LUR", "UMD": "ADEN/LUR",
    "UPI": "ADEN/LUR", "KCB": "ADEN/LUR", "TER": "ADEN/LUR", "PCP": "ADEN/LUR",
    "NEI": "ADEN/LUR", "KRMD": "ADEN/LUR", "BANL": "ADEN/LUR", "GANI": "ADEN/LUR",
}

ELECT_G_SSE = {
    "KWV": "SSE/ELECT/KWV", "DHS": "SSE/ELECT/KWV", "KEM": "SSE/ELECT/KWV", "BLNI": "SSE/ELECT/KWV",
    "BTW": "SSE/ELECT/KWV", "SEI": "SSE/ELECT/KWV", "PPJ": "SSE/ELECT/KWV", "WSB": "SSE/ELECT/KWV",
    "KEU": "SSE/ELECT/KWV", "JNTR": "SSE/ELECT/KWV", "BGVN": "SSE/ELECT/KWV", "MLM": "SSE/ELECT/KWV",
    "BRB": "SSE/ELECT/KWV", "DD": "SSE/ELECT/KWV", "MLB": "SSE/ELECT/KWV", "PVR": "SSE/ELECT/KWV",
    "SGLA": "SSE/ELECT/KWV", "DLGN": "SSE/ELECT/KWV", "JTRD": "SSE/ELECT/KWV", "SGRE": "SSE/ELECT/KWV",
    "ARAG": "SSE/ELECT/KWV", "KVK": "SSE/ELECT/KWV", "MRJ": "SSE/ELECT/KWV", "MKPT": "SSE/ELECT/KWV",
    "AAG": "SSE/ELECT/KWV", "WKA": "SSE/ELECT/KWV", "MA": "SSE/ELECT/KWV", "WDS": "SSE/ELECT/KWV",
    "WSD": "SSE/ELECT/KWV", "MADHA": "SSE/ELECT/KWV", "PSS": "SSE/ELECT/KWV", "LAUL": "SSE/ELECT/KWV",
    "CNHL": "SSE/ELECT/KWV", "MGO": "SSE/ELECT/KWV", "MSDG": "SSE/ELECT/KWV", "JVA": "SSE/ELECT/KWV",
    "GLV": "SSE/ELECT/KWV", "LNP": "SSE/ELECT/KWV", "AGDl": "SSE/ELECT/KWV", "BLWD": "SSE/ELECT/KWV",
    "BDK": "SSE/ELECT/KWV", "BLNK": "SSE/ELECT/KWV", "BBV": "SSE/ELECT/KWV", "AHI": "SSE/ELECT/KWV",
    "BMNI": "SSE/ELECT/KWV", "BHLI": "SSE/ELECT/KWV",
    "DUD": "SSE/ELECT/SUR", "NGS": "SSE/ELECT/SUR", "BOT": "SSE/ELECT/SUR", "AKOR": "SSE/ELECT/SUR",
    "SUR": "SSE/ELECT/SUR", "JEUR": "SSE/ELECT/SUR", "PK": "SSE/ELECT/SUR", "BALE": "SSE/ELECT/SUR",
    "MVE": "SSE/ELECT/SUR", "MO": "SSE/ELECT/SUR", "TKWD": "SSE/ELECT/SUR", "HG": "SSE/ELECT/SUR",
    "TLT": "SSE/ELECT/SUR", "HG STN": "SSE/ELECT/SUR", "HG-A": "SSE/ELECT/SUR",
    "MOHOL": "SSE/ELECT/SUR", "PAKNI": "SSE/ELECT/SUR",
    "KUI": "SSE/ELECT/KLBG", "GDGN": "SSE/ELECT/KLBG", "GUR": "SSE/ELECT/KLBG", "SVG": "SSE/ELECT/KLBG",
    "BBD": "SSE/ELECT/KLBG", "KLBG": "SSE/ELECT/KLBG", "TJSP": "SSE/ELECT/KLBG", "HQR": "SSE/ELECT/KLBG",
    "MR": "SSE/ELECT/KLBG", "SDB": "SSE/ELECT/KLBG", "SBD": "SSE/ELECT/KLBG", "WADI": "SSE/ELECT/KLBG",
    "HHD": "SSE/ELECT/KLBG",
    "PJR": "SSE/ELECT/LUR", "YSI": "SSE/ELECT/LUR", "DKY": "SSE/ELECT/LUR", "OSA": "SSE/ELECT/LUR",
    "HGL": "SSE/ELECT/LUR", "LUR": "SSE/ELECT/LUR", "DRSV": "SSE/ELECT/LUR", "MRX": "SSE/ELECT/LUR",
    "LTRR": "SSE/ELECT/LUR", "UMD": "SSE/ELECT/LUR", "UPI": "SSE/ELECT/LUR", "KCB": "SSE/ELECT/LUR",
    "TER": "SSE/ELECT/LUR", "PCP": "SSE/ELECT/LUR", "NEI": "SSE/ELECT/LUR", "KRMD": "SSE/ELECT/LUR",
    "BANL": "SSE/ELECT/LUR", "GANI": "SSE/ELECT/LUR",
}

ELECT_TRD_SSE = {
    "SUR": "SSE/TRD/SUR", "TKWD": "SSE/TRD/SUR", "HG": "SSE/TRD/SUR", "TLT": "SSE/TRD/SUR",
    "AKOR": "SSE/TRD/SUR", "BALE": "SSE/TRD/SUR", "PK": "SSE/TRD/SUR", "MVE": "SSE/TRD/SUR",
    "MO": "SSE/TRD/SUR", "HG STN": "SSE/TRD/SUR", "HG-A": "SSE/TRD/SUR",
    "MOHOL": "SSE/TRD/SUR", "PAKNI": "SSE/TRD/SUR",
    "NGS": "SSE/TRD/DUD", "BOT": "SSE/TRD/DUD", "DUD": "SSE/TRD/DUD", "KUI": "SSE/TRD/DUD",
    "GUR": "SSE/TRD/DUD", "SVG": "SSE/TRD/DUD", "HHD": "SSE/TRD/DUD",
    "BBD": "JE/TRD/KLBG", "KLBG": "JE/TRD/KLBG", "TJSP": "JE/TRD/KLBG", "HQR": "JE/TRD/KLBG",
    "MR": "JE/TRD/KLBG", "SDB": "JE/TRD/KLBG", "SBD": "JE/TRD/KLBG", "GDGN": "JE/TRD/KLBG",
    "WADI": "JE/TRD/WADI",
    "MKPT": "SSE/TRD/KWV", "AAG": "SSE/TRD/KWV", "WKA": "SSE/TRD/KWV", "WDS": "SSE/TRD/KWV",
    "KWV": "SSE/TRD/KWV", "DHS": "SSE/TRD/KWV", "KEM": "SSE/TRD/KWV", "BLNI": "SSE/TRD/KWV",
    "WSD": "SSE/TRD/KWV", "MADHA": "SSE/TRD/KWV", "PSS": "SSE/TRD/KWV", "LAUL": "SSE/TRD/KWV",
    "JEUR": "SSE/TRD/KEU", "PPJ": "SSE/TRD/KEU", "WSB": "SSE/TRD/KEU", "KEU": "SSE/TRD/KEU",
    "JNTR": "SSE/TRD/KEU", "BGVN": "SSE/TRD/KEU", "MLM": "SSE/TRD/KEU", "BRB": "SSE/TRD/KEU", "DD": "SSE/TRD/KEU",
    "SEI": "SSE/TRD/BTW", "BTW": "SSE/TRD/BTW", "PJR": "SSE/TRD/BTW", "CNHL": "SSE/TRD/BTW",
    "MGO": "SSE/TRD/BTW", "UPI": "SSE/TRD/BTW", "KCB": "SSE/TRD/BTW",
    "DRSV": "SSE/TRD/DRSV", "YSI": "SSE/TRD/DRSV", "DKY": "SSE/TRD/DRSV", "KRMD": "SSE/TRD/DRSV",
    "OSA": "SSE/TRD/LUR", "HGL": "SSE/TRD/LUR", "LUR": "SSE/TRD/LUR", "MRX": "SSE/TRD/LUR",
    "LTRR": "SSE/TRD/LUR", "UMD": "SSE/TRD/LUR", "TER": "SSE/TRD/LUR", "PCP": "SSE/TRD/LUR",
    "NEI": "SSE/TRD/LUR", "BANL": "SSE/TRD/LUR", "GANI": "SSE/TRD/LUR",
    "MLB": "SSE/TRD/PVR", "PVR": "SSE/TRD/PVR", "BBV": "SSE/TRD/PVR", "AHI": "SSE/TRD/PVR",
    "SGLA": "SSE/TRD/SGLA", "JTRD": "SSE/TRD/SGLA", "DLGN": "SSE/TRD/SGLA",
    "MSDG": "SSE/TRD/SGLA", "JVA": "SSE/TRD/SGLA", "GLV": "SSE/TRD/SGLA", "BMNI": "SSE/TRD/SGLA", "BHLI": "SSE/TRD/SGLA",
    "KVK": "SSE/TRD/SGRE", "SGRE": "SSE/TRD/SGRE", "ARAG": "SSE/TRD/SGRE",
    "LNP": "SSE/TRD/SGRE", "AGDl": "SSE/TRD/SGRE", "BLNK": "SSE/TRD/SGRE",
    "BLWD": "SSE/TRD/KWV", "BDK": "SSE/TRD/KWV", "MRJ": "SSE/TRD/KWV",
}

OPERATING_TI = {
    "SUR": "TI/SUR/N", "BALE": "TI/SUR/N", "PK": "TI/SUR/N", "MVE": "TI/SUR/N", "MO": "TI/SUR/N",
    "MKPT": "TI/SUR/N", "AAG": "TI/SUR/N", "WKA": "TI/SUR/N", "MOHOL": "TI/SUR/N", "PAKNI": "TI/SUR/N",
    "TKWD": "TI/SUR/S", "HG": "TI/SUR/S", "TLT": "TI/SUR/S", "AKOR": "TI/SUR/S",
    "NGS": "TI/SUR/S", "BOT": "TI/SUR/S", "HG STN": "TI/SUR/S", "HG-A": "TI/SUR/S",
    "DUD": "TI/KLBG", "KUI": "TI/KLBG", "GUR": "TI/KLBG", "SVG": "TI/KLBG",
    "BBD": "TI/KLBG", "KLBG": "TI/KLBG", "TJSP": "TI/KLBG", "HHD": "TI/KLBG", "GDGN": "TI/KLBG",
    "HQR": "TI/WADI", "MR": "TI/WADI", "SDB": "TI/WADI", "WADI": "TI/WADI", "SBD": "TI/WADI",
    "WDS": "TI/KWV", "KWV": "TI/KWV", "DHS": "TI/KWV", "KEM": "TI/KWV",
    "BLNI": "TI/KWV", "JEUR": "TI/KWV", "WSD": "TI/KWV", "MADHA": "TI/KWV", "MA": "TI/KWV",
    "PSS": "TI/KWV", "LAUL": "TI/KWV",
    "PPJ": "TI/BGVN", "WSB": "TI/BGVN", "KEU": "TI/BGVN", "JNTR": "TI/BGVN",
    "BGVN": "TI/BGVN", "MLM": "TI/BGVN", "BRB": "TI/BGVN", "DD": "TI/BGVN",
    "SEI": "TI/LUR", "BTW": "TI/LUR", "PJR": "TI/LUR", "DRSV": "TI/LUR",
    "YSI": "TI/LUR", "DKY": "TI/LUR", "OSA": "TI/LUR", "HGL": "TI/LUR", "LUR": "TI/LUR",
    "MRX": "TI/LUR", "LTRR": "TI/LUR", "UMD": "TI/LUR", "CNHL": "TI/LUR", "MGO": "TI/LUR",
    "UPI": "TI/LUR", "KCB": "TI/LUR", "TER": "TI/LUR", "PCP": "TI/LUR",
    "NEI": "TI/LUR", "KRMD": "TI/LUR", "BANL": "TI/LUR", "GANI": "TI/LUR",
    "MLB": "TI/PVR", "PVR": "TI/PVR", "SGLA": "TI/PVR", "JTRD": "TI/PVR",
    "DLGN": "TI/PVR", "KVK": "TI/PVR", "SGRE": "TI/PVR", "ARAG": "TI/PVR", "MRJ": "TI/PVR",
    "MSDG": "TI/PVR", "JVA": "TI/PVR", "GLV": "TI/PVR", "LNP": "TI/PVR", "AGDl": "TI/PVR",
    "BLWD": "TI/PVR", "BDK": "TI/PVR", "BLNK": "TI/PVR", "BBV": "TI/PVR",
    "AHI": "TI/PVR", "BMNI": "TI/PVR", "BHLI": "TI/PVR",
}

SNT_ADSTE = {
    "WADI": "ADSTE/KLBG (WADI-HG)", "SDB": "ADSTE/KLBG (WADI-HG)", "MR": "ADSTE/KLBG (WADI-HG)",
    "HQR": "ADSTE/KLBG (WADI-HG)", "KLBG": "ADSTE/KLBG (WADI-HG)", "BBD": "ADSTE/KLBG (WADI-HG)",
    "SVG": "ADSTE/KLBG (WADI-HG)", "HHD": "ADSTE/KLBG (WADI-HG)", "GUR": "ADSTE/KLBG (WADI-HG)",
    "KUI": "ADSTE/KLBG (WADI-HG)", "DUD": "ADSTE/KLBG (WADI-HG)", "BOT": "ADSTE/KLBG (WADI-HG)",
    "AKOR": "ADSTE/KLBG (WADI-HG)", "TLT": "ADSTE/KLBG (WADI-HG)", "HG": "ADSTE/KLBG (WADI-HG)",
    "TJSP": "ADSTE/KLBG (WADI-HG)", "HG STN": "ADSTE/KLBG (WADI-HG)", "HG-A": "ADSTE/KLBG (WADI-HG)",
    "SBD": "ADSTE/KLBG (WADI-HG)", "GDGN": "ADSTE/KLBG (WADI-HG)", "NGS": "ADSTE/KLBG (WADI-HG)",
    "TKWD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SUR": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BALE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "PK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MVE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MO": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MKPT": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "AAG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "WKA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MLB": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "PVR": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SGLA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "JTRD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "DLGN": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "KVK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SGRE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "ARAG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MRJ": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MOHOL": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "PAKNI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MSDG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "JVA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "GLV": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "LNP": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "AGDl": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BLWD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BDK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BLNK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BBV": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "AHI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BMNI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BHLI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "KWV": "ADSTE/KWV-I (KWV-BRB)", "DHS": "ADSTE/KWV-I (KWV-BRB)", "KEM": "ADSTE/KWV-I (KWV-BRB)",
    "BLNI": "ADSTE/KWV-I (KWV-BRB)", "JEUR": "ADSTE/KWV-I (KWV-BRB)", "PPJ": "ADSTE/KWV-I (KWV-BRB)",
    "WSB": "ADSTE/KWV-I (KWV-BRB)", "KEU": "ADSTE/KWV-I (KWV-BRB)", "JNTR": "ADSTE/KWV-I (KWV-BRB)",
    "BGVN": "ADSTE/KWV-I (KWV-BRB)", "MLM": "ADSTE/KWV-I (KWV-BRB)", "BRB": "ADSTE/KWV-I (KWV-BRB)",
    "WDS": "ADSTE/KWV-I (KWV-BRB)", "WSD": "ADSTE/KWV-I (KWV-BRB)", "DD": "ADSTE/KWV-I (KWV-BRB)",
    "MADHA": "ADSTE/KWV-I (KWV-BRB)", "PSS": "ADSTE/KWV-I (KWV-BRB)", "LAUL": "ADSTE/KWV-I (KWV-BRB)",
    "SEI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "BTW": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "PJR": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "YSI": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "MRX": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "OSA": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "HGL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "LUR": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "DRSV": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "DKY": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "LTRR": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "UMD": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "CNHL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "MGO": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "UPI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "KCB": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "TER": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "PCP": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "NEI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "KRMD": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "BANL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "GANI": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
}

def get_jurisdiction(station, department):
    if pd.isna(station) or str(station).strip() == "":
        return "Unclassified"
    
    stn = str(station).strip().upper().replace(" ", "")
    
    if stn in ["HGSTN", "HGA", "HG-A"]:
        stn = "HG"
    if stn == "AGDL":
        stn = "AGDl"
    
    dept = str(department).strip().upper() if pd.notna(department) else ""

    if "OPTG" in dept or "OPERATING" in dept:
        return OPERATING_TI.get(stn, OPERATING_TI.get(station, "Unclassified"))
    
    if "ENGG" in dept or "ENGINEERING" in dept or "ADEN" in dept:
        return ENGG_ADEN.get(stn, ENGG_ADEN.get(station, "Unclassified"))
    
    if any(x in dept for x in ["TRD", "TRACTION", "OHE"]):
        return ELECT_TRD_SSE.get(stn, ELECT_TRD_SSE.get(station, "Unclassified"))
    
    if any(x in dept for x in ["ELECT", "ELECTRICAL", "SSE/ELECT"]):
        return ELECT_G_SSE.get(stn, ELECT_G_SSE.get(station, "Unclassified"))
    
    return SNT_ADSTE.get(stn, SNT_ADSTE.get(station, "Unclassified"))

# ====================== IMPROVED AI CHATBOT ======================

import json
import re
import signal
import platform
import pandas as pd
import streamlit as st

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

# Revisit this periodically
MODEL_NAME = "gemini-3.6-flash"


# ==========================================================================
# CLIENT (only cache a successful client)
# ==========================================================================

def _read_gemini_api_key():
    """Try several common secret locations. Returns the key string or None."""
    # Preferred structure used in this app
    try:
        key = st.secrets["gemini"]["api_key"]
        if key and str(key).strip():
            return str(key).strip()
    except Exception:
        pass

    # Fallbacks people often use
    for path in [
        ("gemini", "API_KEY"),
        ("GEMINI_API_KEY",),
        ("GOOGLE_API_KEY",),
        ("gemini_api_key",),
    ]:
        try:
            if len(path) == 1:
                key = st.secrets[path[0]]
            else:
                key = st.secrets[path[0]][path[1]]
            if key and str(key).strip():
                return str(key).strip()
        except Exception:
            continue
    return None


@st.cache_resource
def get_gemini_client():
    if genai is None:
        return None
    api_key = _read_gemini_api_key()
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def clear_gemini_cache():
    """Call this after fixing secrets so a previously-cached None is discarded."""
    get_gemini_client.clear()


def diagnose_gemini_setup():
    """Non-cached — always re-checks from scratch. Returns (ok: bool, message: str)."""
    if genai is None:
        return False, (
            "❌ `google-genai` did not import. "
            "Run `pip install google-genai` in the SAME terminal/venv you use to launch this Streamlit app."
        )

    api_key = _read_gemini_api_key()
    if not api_key:
        return False, (
            "❌ Could not find the API key.\n\n"
            "Add this exact block to `.streamlit/secrets.toml` (or Streamlit Cloud Secrets):\n\n"
            "[gemini]\n"
            'api_key = "AIzaSy..."\n\n'
            "Then click the 'Clear Gemini Cache' button below and refresh."
        )

    try:
        test_client = genai.Client(api_key=api_key)
        resp = test_client.models.generate_content(
            model=MODEL_NAME,
            contents="Say OK"
        )
        return True, f"✅ Working! Gemini replied: {resp.text.strip()[:80]}"
    except Exception as e:
        return False, f"❌ genai.Client() / generate_content raised:\n{type(e).__name__}: {e}"


# ==========================================================================
# BUILD A COMPACT DESCRIPTION OF THE DATA FOR GEMINI
# ==========================================================================

def build_data_context(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "The dataframe `df` is currently empty."

    lines = [f"The dataframe `df` has {len(df):,} rows. Columns and dtypes:"]
    for col in df.columns:
        lines.append(f"  - {col} ({df[col].dtype})")

    lines.append("\nSample of distinct values for key categorical columns (to help you match user wording to real values):")
    for col in ["STATION", "DEPARTMENT", "ERROR MAIN CATEGORY", "JURISDICTION", "MONTH", "DL FAULT MESSAGE"]:
        if col in df.columns:
            uniques = df[col].dropna().unique().tolist()
            shown = uniques[:40]
            more = f" ...and {len(uniques) - 40} more" if len(uniques) > 40 else ""
            lines.append(f"  - {col}: {shown}{more}")

    if "DATE" in df.columns and pd.api.types.is_datetime64_any_dtype(df["DATE"]):
        try:
            lines.append(f"\nDate range covered: {df['DATE'].min().date()} to {df['DATE'].max().date()}")
        except Exception:
            pass

    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """You are a data analyst assistant embedded in a railway safety data-logger dashboard (Central Railway, Solapur Division). You answer questions about the dataframe `df` described below. FCOUNT means the fault/failure count for a record.

{data_context}

You must respond with ONLY a single JSON object (no markdown fences, no prose outside the JSON) with exactly these fields:
{{
  "needs_code": true or false,
  "pandas_code": "<python code or null>",
  "explanation": "<one short sentence describing what you computed, or null if needs_code is false>",
  "answer_text": "<direct natural-language answer, or null if needs_code is true>"
}}

Rules for pandas_code (only used when needs_code is true):
- You may only use the variables `df` (already loaded) and `pd` (pandas).
- Your code must assign the final answer to a variable named `result`. It can be a number, string, pandas Series, or small pandas DataFrame.
- Never use import, open, exec, eval, os, sys, subprocess, network calls, or attempt to write/modify files.
- Never mutate `df` itself — only read from it (copies/groupby/filtering are fine).
- Keep it to a few lines. Prefer groupby/sum/mean/sort_values/head over loops.
- If the question is ambiguous about a time period or station, make the most reasonable interpretation and mention your assumption in "explanation".

Rules for answer_text (only used when needs_code is false):
- Use this for greetings, help requests, or questions that don't require computing over the data.
- Keep it warm, concise, and specific to what this dashboard can do (stations, FCOUNT, departments, jurisdictions, error categories, trends, comparisons, anomalies).

Respond with the JSON object only."""


# ==========================================================================
# CODE SAFETY VALIDATION
# ==========================================================================

FORBIDDEN_PATTERNS = [
    r"\bimport\b", r"\bopen\s*\(", r"\bexec\s*\(", r"\beval\s*\(", r"\bcompile\s*\(",
    r"\bos\.", r"\bsys\.", r"\bsubprocess\b", r"\brequests\b", r"\bsocket\b", r"\bshutil\b",
    r"__\w+__", r"\bglobals\s*\(", r"\blocals\s*\(", r"\bgetattr\s*\(", r"\bsetattr\s*\(",
    r"\bdelattr\s*\(", r"\binput\s*\(", r"\.system\s*\(", r"\bread_csv\s*\(", r"\bread_excel\s*\(",
    r"\bto_csv\s*\(", r"\bto_excel\s*\(", r"\bto_pickle\s*\(", r"\bdf\s*=\s*", r"\bdf\.drop\s*\(.*inplace",
    r"\bdf\[.*\]\s*=", r"\blambda\b.*:.*(os|sys|open|import)",
]


def validate_code(code: str) -> bool:
    if not code or not isinstance(code, str):
        return False
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return False
    return True


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError()


def safe_execute(code: str, df: pd.DataFrame, timeout_seconds: int = 5):
    """Run validated pandas code in a restricted namespace and return `result`."""
    safe_builtins = {
        "len": len, "int": int, "float": float, "str": str, "round": round,
        "sorted": sorted, "list": list, "dict": dict, "set": set, "sum": sum,
        "min": min, "max": max, "abs": abs, "range": range, "enumerate": enumerate,
        "zip": zip, "bool": bool,
    }
    local_ns = {"df": df.copy(), "pd": pd, "result": None}
    global_ns = {"__builtins__": safe_builtins}

    use_alarm = platform.system() != "Windows"
    if use_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout_seconds)
    try:
        exec(code, global_ns, local_ns)
    finally:
        if use_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    return local_ns.get("result")


# ==========================================================================
# RESULT FORMATTING
# ==========================================================================

def format_result(result) -> str:
    if result is None:
        return "<i>(no result returned)</i>"

    if isinstance(result, (int, float)):
        if isinstance(result, float) and not result.is_integer():
            return f"<b>{result:,.2f}</b>"
        return f"<b>{int(result):,}</b>"

    if isinstance(result, str):
        return f"<b>{result}</b>"

    if isinstance(result, pd.Series):
        items = list(result.items())[:20]
        lines = [f"• <b>{idx}</b>: {val:,.2f}" if isinstance(val, float) else f"• <b>{idx}</b>: {val:,}"
                 for idx, val in items]
        more = f"<br>...and {len(result) - 20} more." if len(result) > 20 else ""
        return "<br>".join(lines) + more

    if isinstance(result, pd.DataFrame):
        small = result.head(20)
        try:
            return small.to_html(index=False, border=0, classes="chat-result-table")
        except Exception:
            return small.to_string(index=False)

    return str(result)


# ==========================================================================
# LIGHTWEIGHT OFFLINE FALLBACK
# ==========================================================================

def basic_offline_fallback(question: str, df: pd.DataFrame) -> str:
    q = question.lower()
    if df is None or df.empty:
        return "⚠️ The AI assistant is temporarily unavailable and there is no data loaded to fall back on."
    if "STATION" in df.columns and "FCOUNT" in df.columns and any(w in q for w in ["top", "highest", "most"]):
        totals = df.groupby("STATION")["FCOUNT"].sum().sort_values(ascending=False)
        if not totals.empty:
            return (f"⚠️ AI assistant is temporarily unavailable (this can happen on the free tier under heavy use). "
                    f"Basic offline answer: the station with the highest FCOUNT is "
                    f"<b>{totals.index[0]}</b> with <b>{int(totals.iloc[0]):,}</b>.")
    if "total" in q and "fcount" in q and "FCOUNT" in df.columns:
        return (f"⚠️ AI assistant is temporarily unavailable. Basic offline answer: "
                f"Total FCOUNT: <b>{int(df['FCOUNT'].sum()):,}</b>")
    if "total" in q and ("record" in q or "case" in q):
        return (f"⚠️ AI assistant is temporarily unavailable. Basic offline answer: "
                f"Total records: <b>{len(df):,}</b>")
    return ("⚠️ The AI assistant is temporarily unavailable right now — this is usually a free-tier rate limit "
            "or a network issue. Please wait a few seconds and try again.")


# ==========================================================================
# MAIN ENTRY POINT
# ==========================================================================

def ask_chatbot(question: str, df: pd.DataFrame, force_refresh_callback=None) -> str:
    if not question or not question.strip():
        return "Please type a question — try 'help' to see what I can do."

    q_lower = question.lower()
    if force_refresh_callback and any(w in q_lower for w in ["latest data", "live data", "refresh data", "up to date"]):
        try:
            force_refresh_callback()
        except Exception:
            pass

    client = get_gemini_client()
    if client is None:
        return ("⚠️ The AI assistant isn't configured yet.\n\n"
                "1. Make sure `google-genai` is installed (`pip install google-genai`)\n"
                "2. Add the key to secrets as:\n"
                "   [gemini]\n"
                '   api_key = "AIzaSy..."\n'
                "3. Click the **Clear Gemini Cache** button in the sidebar, then try again.\n\n"
                "Meanwhile, here's a basic offline answer:<br><br>"
                + basic_offline_fallback(question, df))

    data_context = build_data_context(df)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(data_context=data_context)

    parsed = None
    for attempt in range(2):  # one retry for transient 429s
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=question,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text.strip()
            raw_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip())
            parsed = json.loads(raw_text)
            break
        except Exception:
            parsed = None
            continue

    if parsed is None:
        return basic_offline_fallback(question, df)

    needs_code = parsed.get("needs_code", False)

    if not needs_code:
        answer = parsed.get("answer_text") or "I'm not sure how to answer that — try rephrasing, or type 'help'."
        return answer

    code = parsed.get("pandas_code")
    explanation = parsed.get("explanation") or ""

    if not validate_code(code):
        return ("I generated a computation for that but it didn't pass a safety check, so I've skipped it. "
                "Please try rephrasing the question more simply.")

    try:
        result = safe_execute(code, df)
    except _TimeoutError:
        return "That computation took too long to run — please try a narrower question (e.g. add a month or station filter)."
    except Exception as e:
        return (f"I tried to compute that but hit an error ({type(e).__name__}). "
                f"Could you rephrase the question? (e.g. name the exact column or station you mean)")

    formatted = format_result(result)
    if explanation:
        return f"{explanation}<br><br>{formatted}"
    return formatted
 
# ====================== SESSION STATE ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "map_selected_station" not in st.session_state:
    st.session_state.map_selected_station = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

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
        if 'DATE' in df.columns:
            df['DATE'] = pd.to_datetime(df['DATE'], errors='coerce')
            df['MONTH'] = df['DATE'].dt.strftime('%B')
            df['YEAR_MONTH'] = df['DATE'].dt.to_period('M').astype(str)
        if 'STATION' in df.columns and 'DEPARTMENT' in df.columns:
            df['JURISDICTION'] = df.apply(
                lambda row: get_jurisdiction(row['STATION'], row['DEPARTMENT']), axis=1
            )
        else:
            df['JURISDICTION'] = "Unclassified"
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

    df_original = load_data_from_gsheet()

    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.header("🔧 Controls")
        if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
            refresh_data()

        st.markdown("---")

        # Cool Chatbot Header
        st.markdown("""
        <div class="chatbot-header">
            🤖 AI Chatbot
            <span>Spelling tolerant</span>
        </div>
        """, unsafe_allow_html=True)

        # Chat messages
        chat_html = '<div class="chat-container">'
        for chat in st.session_state.chat_history[-12:]:
            if chat["role"] == "user":
                chat_html += f'''
                <div class="chat-message user-msg">
                    <span class="chat-avatar">👤</span>{chat["content"]}
                </div>'''
            else:
                chat_html += f'''
                <div class="chat-message bot-msg">
                    <span class="chat-avatar">🤖</span>{chat["content"]}
                </div>'''
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        user_question = st.chat_input("Ask me anything about the data...")
        if user_question:
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            answer = ask_chatbot(user_question, df_original)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        st.markdown("---")
        st.markdown("**🔧 Gemini Status**")
        if st.button("🔍 Diagnose Gemini", use_container_width=True):
            ok, msg = diagnose_gemini_setup()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        if st.button("🗑️ Clear Gemini Cache", use_container_width=True):
            clear_gemini_cache()
            st.success("Gemini client cache cleared. Try asking a question again.")
            st.rerun()
    # ====================== LIVE FILTERS ======================
    st.markdown("### 🔍 Live Filters")
    col_f1 = st.columns([2, 2, 2, 2])
    with col_f1[0]:
        stations = sorted(df_original['STATION'].dropna().unique().tolist()) if 'STATION' in df_original.columns else []
        selected_stations = st.multiselect("STATION", options=stations, default=[], key="stn_key")
    with col_f1[1]:
        errors = sorted(df_original['ERROR MAIN CATEGORY'].dropna().unique().tolist()) if 'ERROR MAIN CATEGORY' in df_original.columns else []
        selected_errors = st.multiselect("ERROR MAIN CATEGORY", options=errors, default=[], key="err_key")
    with col_f1[2]:
        categories = sorted(df_original['DEPARTMENT'].dropna().unique().tolist()) if 'DEPARTMENT' in df_original.columns else []
        selected_categories = st.multiselect("DEPARTMENT", options=categories, default=[], key="cat_key")
    with col_f1[3]:
        months = sorted(df_original['MONTH'].dropna().unique().tolist()) if 'MONTH' in df_original.columns else []
        selected_months = st.multiselect("MONTH", options=months, default=[], key="month_key")

    col_f2 = st.columns([2, 2, 2, 2])
    with col_f2[0]:
        fcount_list = sorted(df_original['FCOUNT'].dropna().unique().tolist()) if 'FCOUNT' in df_original.columns else []
        selected_fcount = st.multiselect("FCOUNT", options=fcount_list, default=[], key="fcount_key")
    with col_f2[1]:
        fault_list = sorted(df_original['DL FAULT MESSAGE'].dropna().unique().tolist()) if 'DL FAULT MESSAGE' in df_original.columns else []
        selected_fault = st.multiselect("DL FAULT MESSAGE", options=fault_list, default=[], key="fault_key")
    with col_f2[2]:
        remark_list = sorted(df_original['REMARKS GIVEN BY S&T'].dropna().unique().tolist()) if 'REMARKS GIVEN BY S&T' in df_original.columns else []
        selected_remark = st.multiselect("REMARKS GIVEN BY S&T", options=remark_list, default=[], key="remark_key")
    with col_f2[3]:
        jurisdictions = sorted(df_original['JURISDICTION'].dropna().unique().tolist()) if 'JURISDICTION' in df_original.columns else []
        selected_jurisdictions = st.multiselect("JURISDICTION", options=jurisdictions, default=[], key="jur_key")

    col_date = st.columns([2, 2, 1])
    with col_date[0]:
        min_date = df_original['DATE'].min().date() if (not df_original.empty and 'DATE' in df_original.columns and pd.notna(df_original['DATE'].min())) else pd.Timestamp.now().date()
        from_date = st.date_input("FROM DATE", value=min_date, key="from_date_key")
    with col_date[1]:
        max_date = df_original['DATE'].max().date() if (not df_original.empty and 'DATE' in df_original.columns and pd.notna(df_original['DATE'].max())) else pd.Timestamp.now().date()
        to_date = st.date_input("TO DATE", value=max_date, key="to_date_key")

    st.divider()

    # ====================== APPLY FILTERS ======================
    filtered_df = df_original.copy()
    if 'DATE' in filtered_df.columns:
        filtered_df = filtered_df[
            (filtered_df['DATE'].dt.date >= from_date) &
            (filtered_df['DATE'].dt.date <= to_date)
        ]
    if selected_stations:
        filtered_df = filtered_df[filtered_df['STATION'].isin(selected_stations)]
    if selected_errors and 'ERROR MAIN CATEGORY' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['ERROR MAIN CATEGORY'].isin(selected_errors)]
    if selected_categories and 'DEPARTMENT' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['DEPARTMENT'].isin(selected_categories)]
    if selected_months and 'MONTH' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['MONTH'].isin(selected_months)]
    if selected_fcount and 'FCOUNT' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['FCOUNT'].isin(selected_fcount)]
    if selected_fault and 'DL FAULT MESSAGE' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['DL FAULT MESSAGE'].isin(selected_fault)]
    if selected_remark and 'REMARKS GIVEN BY S&T' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['REMARKS GIVEN BY S&T'].isin(selected_remark)]
    if selected_jurisdictions and 'JURISDICTION' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['JURISDICTION'].isin(selected_jurisdictions)]
    if st.session_state.map_selected_station:
        filtered_df = filtered_df[filtered_df['STATION'] == st.session_state.map_selected_station]

    # ====================== PRE-COMPUTE SUMMARIES ======================
    cat_sum = pd.DataFrame()
    error_sum = pd.DataFrame()
    jur_sum = pd.DataFrame()
    if not filtered_df.empty:
        if 'DEPARTMENT' in filtered_df.columns:
            cat_sum = (filtered_df.groupby('DEPARTMENT').size().reset_index(name='Cases').sort_values('Cases', ascending=False))
        if 'ERROR MAIN CATEGORY' in filtered_df.columns:
            error_sum = (filtered_df.groupby('ERROR MAIN CATEGORY').size().reset_index(name='Cases').sort_values('Cases', ascending=False))
        if 'JURISDICTION' in filtered_df.columns:
            jur_sum = (filtered_df.groupby('JURISDICTION').size().reset_index(name='Cases').sort_values('Cases', ascending=False))

    st.divider()

    # ====================== TABS ======================
    tab_overview, tab_map = st.tabs(["📊 Overview Dashboard", "🗺️ Map View"])

    with tab_overview:
        st.subheader("📊 Overview Dashboard")

        # High FCOUNT Alert
        if not filtered_df.empty and 'STATION' in filtered_df.columns and 'FCOUNT' in filtered_df.columns:
            station_fcount = filtered_df.groupby('STATION')['FCOUNT'].sum().sort_values(ascending=False)
            critical_stations = station_fcount[station_fcount >= 1000]
            
            if not critical_stations.empty:
                alert_text = "⚠️ <b>CRITICAL ALERT</b> — High FCOUNT Stations: "
                alert_parts = [f"<b>{stn}</b> ({val:,})" for stn, val in critical_stations.head(5).items()]
                alert_text += " | ".join(alert_parts)
                if len(critical_stations) > 5:
                    alert_text += f" + {len(critical_stations)-5} more"
                st.markdown(f'<div class="alert-box">{alert_text}</div>', unsafe_allow_html=True)

        # KPI Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Records", f"{len(filtered_df):,}")
        with c2:
            st.metric("Total FCOUNT", f"{filtered_df.get('FCOUNT', pd.Series(0)).sum():,}")
        with c3:
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                station_totals = filtered_df.groupby('STATION')['FCOUNT'].sum().sort_values(ascending=False)
                top_station = station_totals.index[0] if not station_totals.empty else "N/A"
                st.metric("⚠️ Top Station", top_station)
            else:
                st.metric("⚠️ Top Station", "N/A")
        with c4:
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                station_totals = filtered_df.groupby('STATION')['FCOUNT'].sum().sort_values(ascending=False)
                top_fcount = station_totals.iloc[0] if not station_totals.empty else 0
                st.metric("Top Station FCOUNT", f"{top_fcount:,}")
            else:
                st.metric("Top Station FCOUNT", "0")

        st.markdown("---")

        # Top 15 + Station Summary
        col_g1, col_g2 = st.columns([3, 2])
        with col_g1:
            st.markdown('<p class="section-header">Top 15 Stations by FCOUNT</p>', unsafe_allow_html=True)
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                top15 = filtered_df.groupby('STATION')['FCOUNT'].sum().nlargest(15).reset_index()
                fig = px.bar(top15, x='STATION', y='FCOUNT', text='FCOUNT', color='FCOUNT',
                             color_continuous_scale='RdYlGn_r')
                fig.update_layout(height=480, xaxis_tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
        with col_g2:
            st.markdown('<p class="section-header">Station Summary</p>', unsafe_allow_html=True)
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(Total_FCOUNT='sum', Records='count').sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"}).background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'), use_container_width=True)

        # Monthly Trend
        st.markdown("---")
        st.markdown('<p class="section-header">📈 Monthly Trend of FCOUNT</p>', unsafe_allow_html=True)
        
        if not filtered_df.empty and 'YEAR_MONTH' in filtered_df.columns:
            monthly = filtered_df.groupby('YEAR_MONTH')['FCOUNT'].sum().reset_index()
            monthly = monthly.sort_values('YEAR_MONTH')
            
            fig_trend = px.line(monthly, x='YEAR_MONTH', y='FCOUNT', markers=True, text='FCOUNT')
            fig_trend.update_traces(textposition="top center", line=dict(width=3), marker=dict(size=10))
            fig_trend.update_layout(height=450, xaxis_title="Month", yaxis_title="Total FCOUNT",
                                    hovermode="x unified", dragmode="zoom",
                                    xaxis=dict(tickangle=-45, type='category'))
            
            st.plotly_chart(fig_trend, use_container_width=True, config={
                'displayModeBar': True, 'scrollZoom': True, 'displaylogo': False
            })
            st.caption("Tip: Click and drag to zoom. Double-click to reset.")
        else:
            st.info("No monthly data available for trend.")

        # Distribution Charts
        st.markdown("---")
        st.markdown('<p class="section-header">📊 Distribution Charts</p>', unsafe_allow_html=True)
        
        col_c1, col_c2, col_c3 = st.columns(3)

        with col_c1:
            st.markdown("**Department-wise**")
            if not cat_sum.empty:
                fig_dept = px.pie(cat_sum, names='DEPARTMENT', values='Cases', hole=0.4,
                                  color_discrete_sequence=px.colors.qualitative.Vivid)
                fig_dept.update_traces(textposition='inside', textinfo='percent+label', textfont_size=13,
                                       marker=dict(line=dict(color='#ffffff', width=2)))
                fig_dept.update_layout(height=400, showlegend=False, margin=dict(t=30, b=30, l=20, r=20))
                st.plotly_chart(fig_dept, use_container_width=True)
            else:
                st.info("No Department data")

        with col_c2:
            st.markdown("**Error Main Category**")
            if not error_sum.empty:
                fig_err = px.pie(error_sum, names='ERROR MAIN CATEGORY', values='Cases', hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Bold)
                fig_err.update_traces(textposition='inside', textinfo='percent+label', textfont_size=12,
                                      marker=dict(line=dict(color='#ffffff', width=2)))
                fig_err.update_layout(height=400, showlegend=False, margin=dict(t=30, b=30, l=20, r=20))
                st.plotly_chart(fig_err, use_container_width=True)
            else:
                st.info("No Error data")

        with col_c3:
            st.markdown("**Jurisdiction-wise**")
            if not jur_sum.empty:
                if len(jur_sum) > 10:
                    top10 = jur_sum.head(10).copy()
                    others = pd.DataFrame({'JURISDICTION': ['Others'], 'Cases': [jur_sum.iloc[10:]['Cases'].sum()]})
                    jur_plot = pd.concat([top10, others], ignore_index=True)
                else:
                    jur_plot = jur_sum

                fig_jur = px.pie(jur_plot, names='JURISDICTION', values='Cases', hole=0.4,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_jur.update_traces(textposition='inside', textinfo='percent+label', textfont_size=11,
                                      marker=dict(line=dict(color='#ffffff', width=2)))
                fig_jur.update_layout(height=400, showlegend=False, margin=dict(t=30, b=30, l=20, r=20))
                st.plotly_chart(fig_jur, use_container_width=True)
            else:
                st.info("No Jurisdiction data")

        # Summary Tables
        st.markdown("---")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            if not cat_sum.empty:
                st.markdown('<p class="section-header">DEPARTMENT</p>', unsafe_allow_html=True)
                st.dataframe(cat_sum.style.format({"Cases": "{:,}"}), use_container_width=True, hide_index=True)
        with col_s2:
            if not error_sum.empty:
                st.markdown('<p class="section-header">ERROR MAIN CATEGORY</p>', unsafe_allow_html=True)
                st.dataframe(error_sum.style.format({"Cases": "{:,}"}), use_container_width=True, hide_index=True)
        with col_s3:
            if not jur_sum.empty:
                st.markdown('<p class="section-header">JURISDICTION</p>', unsafe_allow_html=True)
                st.dataframe(jur_sum.style.format({"Cases": "{:,}"}), use_container_width=True, hide_index=True)

        # Detailed Records
        st.markdown("---")
        st.markdown('<p class="section-header">Detailed Records</p>', unsafe_allow_html=True)
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'DATE' in display_df.columns:
                display_df['DATE'] = display_df['DATE'].dt.date
            preferred_order = ['DATE', 'STATION', 'DEPARTMENT', 'JURISDICTION', 'ERROR MAIN CATEGORY',
                               'DL FAULT MESSAGE', 'FCOUNT', 'REMARKS GIVEN BY S&T', 'TIMEDETAILS']
            cols = [c for c in preferred_order if c in display_df.columns] + [c for c in display_df.columns if c not in preferred_order]
            st.dataframe(display_df[cols].style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 3, 1])
            with col_btn2:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                    if 'STATION' in filtered_df.columns:
                        station_summary = filtered_df.groupby('STATION')['FCOUNT'].agg(
                            Total_FCOUNT='sum', Record_Count='count'
                        ).sort_values('Total_FCOUNT', ascending=False).reset_index()
                        station_summary.to_excel(writer, index=False, sheet_name='Station_Summary')
                    if not error_sum.empty:
                        error_sum.to_excel(writer, index=False, sheet_name='Error_Summary')
                    if not cat_sum.empty:
                        cat_sum.to_excel(writer, index=False, sheet_name='Category_Summary')
                    if not jur_sum.empty:
                        jur_sum.to_excel(writer, index=False, sheet_name='Jurisdiction_Summary')
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
       
        if st.session_state.map_selected_station:
            col_clear1, col_clear2 = st.columns([1, 5])
            with col_clear1:
                if st.button("🔄 Clear Station Selection", type="secondary", use_container_width=True):
                    st.session_state.map_selected_station = None
                    st.rerun()
            st.success(f"📍 Currently viewing: **{st.session_state.map_selected_station}**")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_m1, col_m2 = st.columns([3, 2])
       
        with col_m1:
            if filtered_df.empty or 'STATION' not in filtered_df.columns:
                st.warning("No data available.")
            else:
                map_agg = filtered_df.groupby('STATION')['FCOUNT'].sum().reset_index()
                map_data = []
               
                for _, row in map_agg.iterrows():
                    station_name = str(row['STATION']).strip().upper()
                    best_match = None
                    for name, info in station_coords.items():
                        if name.upper() == station_name or name.upper() in station_name:
                            best_match = info
                            break
                    if best_match:
                        map_data.append({
                            'STATION': row['STATION'],
                            'FCOUNT': row['FCOUNT'],
                            'lat': best_match['lat'],
                            'lon': best_match['lon']
                        })
               
                map_df = pd.DataFrame(map_data)
               
                if not map_df.empty:
                    with st.spinner("Rendering map..."):
                        m = folium.Map(location=[17.85, 75.80], zoom_start=7.2, tiles=None, control_scale=True)
                    
                        carto_key = st.secrets["carto"]["api_key"]
                        folium.TileLayer(
                            tiles=f"https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png?key={carto_key}",
                            name="🗺️ Light Base",
                            attr='© OpenStreetMap © CARTO',
                            control=True, subdomains="abcd", max_zoom=20
                        ).add_to(m)
                    
                        folium.TileLayer("OpenStreetMap", name="🌍 OpenStreetMap", control=True).add_to(m)
                        folium.TileLayer(
                            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                            attr="Esri", name="🌐 Satellite", control=True
                        ).add_to(m)
                    
                        folium.LayerControl(position="topright", collapsed=False).add_to(m)
                        Fullscreen().add_to(m)
                       
                        for _, row in map_df.iterrows():
                            fcount = int(row['FCOUNT'])
                            if fcount < 600:
                                color = "green"
                            elif fcount <= 1200:
                                color = "orange"
                            else:
                                color = "darkred"
                            radius = 8 + min(fcount / 50, 25)
                            
                            folium.CircleMarker(
                                location=[row['lat'], row['lon']],
                                radius=radius,
                                popup=f"<h4>{row['STATION']}</h4><b>Total FCOUNT:</b> {fcount:,}",
                                tooltip=f"{row['STATION']} ({fcount:,})",
                                color=color, fill=True, fill_color=color, fill_opacity=0.85, weight=2
                            ).add_to(m)
                       
                        map_key = f"folium_map_{len(filtered_df)}"
                        map_return = st_folium(m, width=950, height=680, key=map_key, returned_objects=["last_object_clicked"])
                       
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
            if not filtered_df.empty and 'STATION' in filtered_df.columns:
                summary = filtered_df.groupby('STATION')['FCOUNT'].agg(Total_FCOUNT='sum', Records='count').sort_values('Total_FCOUNT', ascending=False)
                st.dataframe(summary.style.format({"Total_FCOUNT": "{:,}", "Records": "{:,}"}).background_gradient(subset=['Total_FCOUNT'], cmap='YlOrRd'), use_container_width=True)
            st.markdown("---")
            st.subheader("Jurisdiction Summary")
            if not jur_sum.empty:
                st.dataframe(jur_sum.style.format({"Cases": "{:,}"}), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("Detailed Records")
        if filtered_df.empty:
            st.warning("No records found.")
        else:
            display_df = filtered_df.copy()
            if 'DATE' in display_df.columns:
                display_df['DATE'] = display_df['DATE'].dt.date
            preferred_order = ['DATE', 'STATION', 'DEPARTMENT', 'JURISDICTION', 'ERROR MAIN CATEGORY', 'DL FAULT MESSAGE', 'FCOUNT', 'REMARKS GIVEN BY S&T']
            cols = [c for c in preferred_order if c in display_df.columns] + [c for c in display_df.columns if c not in preferred_order]
            st.dataframe(display_df[cols].style.format({"FCOUNT": "{:,}"}), use_container_width=True, hide_index=True)

            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 3, 1])
            with col_btn2:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=False, sheet_name='Filtered_Records')
                    if not jur_sum.empty:
                        jur_sum.to_excel(writer, index=False, sheet_name='Jurisdiction_Summary')
                output.seek(0)
                st.download_button(
                    label="⬇️ Download Map Filtered Report",
                    data=output.getvalue(),
                    file_name=f"Map_Filtered_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

    st.caption("🚄 Safety Branch | Central Railway, Solapur Division")
