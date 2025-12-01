import streamlit as st
import pandas as pd
import requests
import time
import re
import urllib.parse
from datetime import datetime, date
import plotly.express as px
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(
    page_title="PO Saha Yönetim",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ÖZEL CSS (PO KURUMSAL TASARIM) ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            background-color: #f8f9fa;
        }
        
        .top-header {
            background: linear-gradient(135deg, #e30613 0%, #b3000b 100%);
            padding: 20px;
            border-radius: 0 0 20px 20px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 10px rgba(227, 6, 19, 0.2);
            margin-bottom: 20px;
        }
        .header-title {
            font-size: 1.8rem;
            font-weight: 700;
            margin: 0;
        }
        .header-subtitle {
            font-size: 0.9rem;
            opacity: 0.9;
            font-weight: 400;
        }
        
        .price-link-container {
            background-color: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid #e5e7eb;
        }
        
        .kpi-card {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            text-align: center;
            border-top: 4px solid #e30613;
        }
        .kpi-number {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1f2937;
        }
        .kpi-label {
            font-size: 0.85rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
# Kendi API Anahtarını buraya yapıştır:
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og" 

# --- ARAMA KATEGORİLERİ ---
SEKTORLER = {
    "🚛 Lojistik": "Lojistik Firmaları",
    "📦 Nakliye": "Yurt İçi Nakliye Firmaları",
    "🌍 Uluslararası": "Uluslararası Transport",
    "🤝 Kooperatifler": "Kamyoncular Kooperatifi",
    "🏭 Fabrikalar (OSB)": "Organize Sanayi Bölgesi Fabrikaları",
    "🚌 Servis/Turizm": "Personel Taşımacılığı",
    "🏗️ İnşaat": "İnşaat Malzemeleri Toptancıları",
    "🏥 Sağlık/Rehab": "Özel Eğitim ve Rehabilitasyon",
    "🥕 Gıda Toptancı": "Gıda Toptancıları"
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
        beklenen_sutunlar = ["Firma", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih"]
        if not data:
            sheet.append_row(beklenen_sutunlar)
            return pd.DataFrame(columns=beklenen_sutunlar)
        df = pd.DataFrame(data)
        for col in beklenen_sutunlar:
            if col not in df.columns: df[col] = ""
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email"]
        for col in text_cols:
            if col in df.columns: df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame(columns=["Firma", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih"])

def veriyi_kaydet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        df_save = df.copy()
        
        # 1. Önce Tarihleri Çevir (Bu işlem yeni NaN'lar oluşturabilir)
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 2. KRİTİK DÜZELTME: Temizliği EN SONDA yapıyoruz.
        # Böylece tarih çevriminden gelen NaN'lar da temizleniyor.
        df_save = df_save.fillna("") 
        
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")

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

def mail_linki_yap(email, firma_adi):
    if not email or "@" not in str(email): return None
    konu = urllib.parse.quote(f"{firma_adi} - Yakıt/Lojistik Çözümleri")
    icerik = urllib.parse.quote(f"Sayın Yetkili,\n\nPetrol Ofisi güvencesiyle çözüm ortağınız olmak isteriz.\n\nSaygılar.")
    return f"mailto:{email}?subject={konu}&body={icerik}"

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

def detay_getir(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {'place_id': place_id, 'fields': 'formatted_phone_number,website', 'key': API_KEY}
    try:
        res = requests.get(url, params=params).json()
        r = res.get('result', {})
        return r.get('formatted_phone_number', ''), r.get('website', '')
    except: return "", ""

# --- ARAYÜZ ---

# 1. BAŞLIK
st.markdown("""
<div class="top-header">
