import streamlit as st
import pandas as pd
import requests
import time
import re
import urllib.parse
from datetime import datetime, date
import plotly.express as px

# Google Sheets Kütüphaneleri
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Lojistik Pro", 
    page_icon="🚛", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri" 
# SENİN API ANAHTARIN (Buraya yerleştirildi):
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og"

# --- ARAMA KATEGORİLERİ ---
SEKTORLER = {
    "🚛 Lojistik Firmaları": "Lojistik Firmaları",
    "📦 Yurt İçi Nakliye": "Yurt İçi Nakliye Firmaları",
    "🌍 Uluslararası Lojistik": "Uluslararası Transport",
    "🤝 Kamyoncular Koop.": "Kamyoncular Kooperatifi",
    "🚌 Personel Servisi": "Personel Taşımacılığı",
    "🎫 Otobüs/Turizm": "Turizm ve Otobüs İşletmeleri",
    "🏭 Gıda Toptancıları": "Gıda Toptancıları ve Üreticileri",
    "🏥 Rehabilitasyon Merkezleri": "Özel Eğitim ve Rehabilitasyon",
    "🏗️ İnşaat Malzemeleri": "İnşaat Malzemeleri Toptancıları",
    "🏭 Organize Sanayi": "Organize Sanayi Bölgesi Fabrikaları"
}

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Secrets içindeki bilgileri al
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # Eğer 'info' diye tek bir satırda yapıştırdıysan (JSON string yöntemi)
    if "info" in creds_dict:
        import json
        creds_dict = json.loads(creds_dict["info"])
        
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def veri_tabanini_yukle():
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        data = sheet.get_all_records()
        
        if not data:
            # Tablo boşsa başlıkları oluştur
            basliklar = ["Firma", "Telefon", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Tuketim_Bilgisi", "Hatirlatici_Tarih"]
            sheet.append_row(basliklar)
            return pd.DataFrame(columns=basliklar)
            
        df = pd.DataFrame(data)
        
        # Veri tiplerini düzelt (Hata önleyici)
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        
        # Tarih formatlarını düzelt
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                
        return df
        
    except Exception as e:
        st.error(f"Google Sheets Bağlantı Hatası: {e}")
        # Hata durumunda boş tablo döndür ki uygulama çökmesin
        return pd.DataFrame(columns=["Firma", "Telefon", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Tuketim_Bilgisi", "Hatirlatici_Tarih"])

def veriyi_kaydet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        
        # Tarihleri string formatına çevir (Excel anlasın diye)
        df_save = df.copy()
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = df_save[col].dt.strftime('%Y-%m-%d').replace("NaT", "")
        
        # Sayfayı temizle ve yeniden yaz
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")

# --- YARDIMCI FONKSİYONLAR ---
def whatsapp_linki_yap(telefon):
    if pd.isna(telefon) or not telefon or len(str(telefon)) < 5: return None
    temiz_no = re.sub(r'\D', '', str(telefon))
    if len(temiz_no) < 10: return None
    if temiz_no.startswith("0"): temiz_no = "90" + temiz_no[1:]
    elif not temiz_no.startswith("90") and len(temiz_no) == 10: temiz_no = "90" + temiz_no
    return f"https://wa.me/{temiz_no}"

def arama_linki_yap(telefon):
    if pd.isna(telefon) or not telefon or len(str(telefon)) < 5: return None
    return f"tel:{telefon}"

def harita_linki_yap(adres):
    if pd.isna(adres) or not adres: return None
    safe_address = urllib.parse.quote(str(adres))
    return f"https://www.google.com/maps/dir/?api=1&destination={safe_address}"

def detay_getir(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {'place_id': place_id, 'fields': 'formatted_phone_number', 'key': API_KEY}
    try:
        res = requests.get(url, params=params).json()
        return res.get('result', {}).get('formatted_phone_number', 'Telefon Yok')
    except:
        return "Hata"

# --- YAN MENÜ ---
with st.sidebar:
    st.title("🚛 Lojistik Asistanı")
    st.markdown("---")
    
    secim = st.radio(
        "Menü",
        ["🏠 Dashboard", "🗺️ Firma Arama", "📂 Portföy (Kalıcı)"],
        index=0
    )
    
    st.markdown
