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
from streamlit_option_menu import option_menu

# --- 1. SAYFA AYARLARI ---
st.set_page_config(
    page_title="PO Saha",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS TASARIMI ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #f0f2f5; }
        .customer-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 5px solid #e30613; margin-bottom: 20px; }
        .kpi-box { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align: center; border: 1px solid #e5e7eb; }
        .stButton>button { border-radius: 8px; height: 45px; font-weight: 600; }
        .nav-link-selected { background-color: #e30613 !important; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og" 

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
        beklenen_sutunlar = ["Firma", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Tuketim_Bilgisi", "Ziyaret_Tarihi"]
        if not data:
            sheet.append_row(beklenen_sutunlar)
            return pd.DataFrame(columns=beklenen_sutunlar)
        df = pd.DataFrame(data)
        for col in beklenen_sutunlar:
            if col not in df.columns: df[col] = ""
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email"]
        for col in text_cols:
            if col in df.columns: df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except: return pd.DataFrame(columns=["Firma", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Tuketim_Bilgisi", "Ziyaret_Tarihi"])

def veriyi_kaydet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        df_save = df.copy()
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df_save.columns: df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d')
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

def detay_getir(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {'place_id': place_id, 'fields': 'formatted_phone_number,website', 'key': API_KEY}
    try:
        res = requests.get(url, params=params).json()
        r = res.get('result', {})
        return r.get('formatted_phone_number', ''), r.get('website', '')
    except: return "", ""

# --- ÜST MENÜ ---
st.image("https://upload.wikimedia.org/wikipedia/commons/2/2e/Petrol_Ofisi_logo.svg", width=120)

selected = option_menu(
    menu_title=None,
    options=["Pano", "Firma Bul", "Müşterilerim", "Ajanda", "Bildirimler"],
    icons=["house", "search", "people", "calendar", "bell"],
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#fafafa"},
        "icon": {"color": "black", "font-size": "14px"}, 
        "nav-link": {"font-size": "12px", "text-align": "center", "margin":"0px", "--hover-color": "#eee"},
        "nav-link-selected": {"background-color": "#e30613", "color": "white"},
    }
)

# --- SAYFA 1: PANO ---
if selected == "Pano":
    st.markdown("### 📊 Bölge Durum Özeti")
    st.link_button("⛽ Güncel Fiyatlar", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    df = veri_tabanini_yukle()
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"""<div class="kpi-box"><h3>{len(df)}</h3><small>Toplam</small></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div class="kpi-box" style="border-bottom: 4px solid #f59e0b;"><h3>{len(df[df["Durum"] == "Yeni"])}</h3><small>Bekleyen</small></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div class="kpi-box" style="border-bottom: 4px solid #10b981;"><h3>{len(df[df["Durum"] == "✅ Anlaşıldı"])}</h3><small>Anlaşılan</small></div>""", unsafe_allow_html=True)
    st.write("")
    if not df.empty:
        durum_counts = df["Durum"].value_counts().reset_index()
        durum_counts.columns = ["Durum", "Adet"]
        fig = px.pie(durum_counts, values="Adet", names="Durum", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
        st.plotly_chart(fig, use_container_width=True)

# --- SAYFA 2: FİRMA BUL ---
elif selected == "Firma Bul":
    st.markdown("### 🗺️ Hedef Pazar Analizi")
    with st.container():
        c1, c2 = st.columns(2)
        sehir = c1.text_input("Şehir", "Gaziantep", placeholder="Şehir")
        sektor_key = c2.selectbox("Sektör", list(SEKTORLER.keys()))
        if st.button("🚀 Taramayı Başlat", type="primary", use_container_width=True):
            arama_sorgusu = SEKTORLER[sektor_key]
            st.toast("Veriler çekiliyor...", icon="⏳")
            tum_firmalar = []
            next_page_token = None
            sayfa = 0
            with st.status("Haritalar taranıyor...", expanded=True):
                while sayfa < 3:
                    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
                    params = {'query': f"{sehir} {arama_sorgusu}", 'key': API_KEY, 'language': 'tr'}
                    if next_page_token: params['pagetoken'] = next_page_token; time.sleep(2)
                    try:
                        resp = requests.get(url, params=params).json()
                        results = resp.get('results', [])
                        for f in results:
                            tel, web = detay_getir(f.get('place_id'))
                            tum_firmalar.append({
                                "Firma": f.get('name'), "Telefon": tel, "Web": web, "Email": "",
                                "Adres": f.get('formatted_address'), "Durum": "Yeni", "Notlar": "", "Tuketim_Bilgisi": "",
                                "lat": f.get('geometry', {}).get('location', {}).get('lat'),
                                "lon": f.get('geometry', {}).get('location', {}).get('lon')
                            })
                        next_page_token = resp.get('next_page_token')
                        sayfa += 1
                        if not next_page_token: break
                    except: break
            if tum_firmalar:
                df_res = pd.DataFrame(tum_firmalar)
                df_res.insert(0, "Seç", False)
                st.session_state['sonuclar'] = df_res
            else: st.error("Sonuç bulunamadı.")

    if 'sonuclar' in st.session_state:
        df_res = st.session_state['sonuclar']
        with st.expander("📍 Haritada Gör"):
            st.map(df_res.dropna(subset=['lat','lon']), latitude='lat', longitude='lon', color='#ff0000')
        edited = st.data_editor(df_res, column_config={"Seç": st.column_config.CheckboxColumn("Ekle", default=False)}, hide_index=True, use_container_width=True)
        if st.button("💾 SEÇİLENLERİ KAYDET", type="primary", use_container_width=True):
            secilenler = edited[edited["Seç"]==True].drop(columns=["Seç", "lat", "lon"], errors='ignore')
            if not secilenler.empty:
                with st.spinner("Kaydediliyor..."):
                    for i, r in secilenler.iterrows():
                        if r["Web"] and len(r["Web"]) > 5: secilenler.at[i, "Email"] = siteyi_tara_mail_bul(r["Web"])
                    mevcut = veri_tabanini_yukle()
                    yeni = pd.concat([mevcut, secilenler], ignore_index=True).drop_duplicates(subset=['Firma'])
                    veriyi_kaydet(yeni)
                st.success(f"✅ {len(secilenler)} firma eklendi!")
                time.sleep(1)

# --- SAYFA 3: MÜŞTERİLERİM (YENİ SİSTEM) ---
elif selected == "Müşterilerim":
    st.markdown("### 👥 Müşteri Portföyü")
    df = veri_tabanini_yukle()
    
    # 1. MOD SEÇİMİ (MEVCUT MU, YENİ Mİ?)
    mode = st.radio("İşlem Seçiniz:", ["📂 Mevcut Müşteriyi Düzenle", "➕ Yeni Müşteri Ekle"], horizontal=True)
    
    st.markdown("---")
    
    # A) MEVCUT MÜŞTERİ DÜZENLEME
    if mode == "📂 Mevcut Müşteriyi Düzenle":
        if not df.empty:
            arama_terimi = st.selectbox("Müşteri Seçin:", df["Firma"].tolist())
            secilen_veri = df[df["Firma"] == arama_terimi].iloc[0]
            idx = df[df["Firma"] == arama_terimi].index[0]
            
            st.markdown(f"""<div class="customer-card"><h4>🏢 {secilen_veri['Firma']}</h4></div>""", unsafe_allow_html=True)
            
            with st.form("musteri_duzenle"):
                c1, c2 = st.columns(2)
                with c1:
                    yeni_tel = st.text_input("Telefon", value=secilen_veri['Telefon'])
                    yeni_email = st.text_input("Email", value=secilen_veri['Email'])
                    yeni_web = st.text_input("Web Sitesi", value=secilen_veri['Web'])
                    yeni_adres = st.text_area("Adres", value=secilen_veri['Adres'], height=80)
                with c2:
                    durum_listesi = ["Yeni",
