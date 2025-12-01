import streamlit as st
import pandas as pd
import requests
import time
import re
import urllib.parse
from datetime import datetime, date, timedelta
import plotly.express as px
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_option_menu import option_menu

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="🚛", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. PREMIUM CSS TASARIMI ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            background-color: #f4f6f9;
        }
        
        /* Karşılama Kartı (Hero) */
        .hero-card {
            background: linear-gradient(135deg, #e30613 0%, #8a040b 100%);
            padding: 25px;
            border-radius: 15px;
            color: white;
            box-shadow: 0 10px 20px rgba(227, 6, 19, 0.2);
            margin-bottom: 20px;
        }
        .hero-title { font-size: 1.5rem; font-weight: 700; margin: 0; }
        .hero-date { font-size: 0.9rem; opacity: 0.8; margin-top: 5px; }
        
        /* KPI Kutuları */
        .kpi-container {
            background-color: white;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border-bottom: 3px solid #e30613;
        }
        .kpi-val { font-size: 1.6rem; font-weight: 700; color: #1f2937; }
        .kpi-txt { font-size: 0.8rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
        
        /* Liste Kartı */
        .list-card {
            background: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        
        /* Müşteri Kartı */
        .customer-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 5px solid #e30613; margin-bottom: 20px; }
        
        /* Butonlar */
        .stButton>button { border-radius: 10px; height: 50px; font-weight: 500; width: 100%; }
        
        /* Menü */
        .nav-link-selected { background-color: #e30613 !important; }
        
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og" 
# LOGO URL (Google Favicon Servisi ile Siteden Çekiliyor)
LOGO_URL = "https://www.google.com/s2/favicons?domain=www.ozkaraaslanfilo.com&sz=256"

# --- ARAMA KATEGORİLERİ ---
SEKTORLER = {
    "🚛 Lojistik": "Lojistik Firmaları", "📦 Nakliye": "Yurt İçi Nakliye Firmaları", "🌍 Uluslararası": "Uluslararası Transport",
    "🤝 Kooperatifler": "Kamyoncular Kooperatifi", "🏭 Fabrikalar (OSB)": "Organize Sanayi Bölgesi Fabrikaları",
    "🚌 Servis/Turizm": "Personel Taşımacılığı", "🏗️ İnşaat": "İnşaat Malzemeleri Toptancıları",
    "🏥 Sağlık/Rehab": "Özel Eğitim ve Rehabilitasyon", "🥕 Gıda Toptancı": "Gıda Toptancıları"
}

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "info" in creds_dict:
        import json
        creds_dict = json.loads(creds_dict["info"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=10)
def veri_tabanini_yukle():
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        data = sheet.get_all_records()
        beklenen_sutunlar = ["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", 
                             "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", 
                             "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki"]
        if not data:
            sheet.append_row(beklenen_sutunlar)
            return pd.DataFrame(columns=beklenen_sutunlar)
        df = pd.DataFrame(data)
        for col in beklenen_sutunlar:
            if col not in df.columns: df[col] = ""
        text_cols = ["Notlar", "Telefon", "Yetkili_Kisi", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email", "Hatirlatici_Saat", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki"]
        for col in text_cols:
            if col in df.columns: df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except: return pd.DataFrame(columns=["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki"])

def veriyi_kaydet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        df_save = df.copy()
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d')
        df_save = df_save.fillna("")
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.cache_data.clear()
    except Exception as e: st.error(f"Kayıt Hatası: {e}")

# --- FONKSİYONLAR ---
def siteyi_tara_mail_bul(website_url):
    if not website_url or "http" not in website_url: return ""
    try:
        response = requests.get(website_url, timeout=3)
        soup = BeautifulSoup(response.text, 'html.parser')
        mailler = set(re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", soup.text, re.I))
        if mailler: return list(mailler)[0]
    except: return ""
    return ""

def whatsapp_linki_yap(telefon):
    if pd.isna(telefon) or len(str(telefon)) < 5: return None
    temiz_no = re.sub(r'\D', '', str(telefon))
    if len(temiz_no) < 10: return None
    if temiz_no.startswith("0"): temiz_no = "90" + temiz_no[1:]
    elif not temiz_no.startswith("90") and len(temiz_no) == 10: temiz_no = "90" + temiz_no
    return f"https://wa.me/{temiz_no}"

def arama_linki_yap(telefon):
    if pd.isna(telefon) or len(str(telefon)) < 5: return None
    return f"tel:{telefon}"

def navigasyon_linki_yap(adres, konum_linki):
    if konum_linki and len(str(konum_linki)) > 5: return str(konum_linki)
    if pd.isna(adres) or not adres: return None
    safe_address = urllib.parse.quote(str(adres))
    return f"https://www.google.com/maps/dir/?api=1&destination={safe_address}"

def google_calendar_link(baslik, tarih_obj, saat_str, adres, aciklama):
    if not tarih_obj or not saat_str: return None
    try:
        time_obj = datetime.strptime(str(saat_str), '%H:%M').time()
        start_dt = datetime.combine(tarih_obj, time_obj)
        end_dt = start_dt + timedelta(hours=1)
        fmt = "%Y%m%dT%H%M%S"
        dates = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"
        base = "https://www.google.com/calendar/render?action=TEMPLATE"
        link = f"{base}&text={urllib.parse.quote(baslik)}&dates={dates}&details={urllib.parse.quote(aciklama)}&location={urllib.parse.quote(adres)}"
        return link
    except: return None

def detay_getir(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {'place_id': place_id, 'fields': 'formatted_phone_number,website,url', 'key': API_KEY}
    try:
        res = requests.get(url, params=params).json()
        r = res.get('result', {})
        return r.get('formatted_phone_number', ''), r.get('website', ''), r.get('url', '')
    except: return
# test
