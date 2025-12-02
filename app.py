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
from fpdf import FPDF # PDF Kütüphanesi

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CSS TASARIMI ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Roboto', sans-serif;
            background-color: #f4f6f9;
        }
        
        /* Karşılama Kartı */
        .hero-card {
            background: linear-gradient(135deg, #e30613 0%, #8a040b 100%);
            padding: 20px;
            border-radius: 15px;
            color: white;
            box-shadow: 0 8px 15px rgba(227, 6, 19, 0.2);
            margin-bottom: 20px;
        }
        
        /* Filtre Kutusu */
        .filter-box {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #e5e7eb;
            margin-bottom: 15px;
        }
        
        /* Müşteri Kartı */
        .customer-card { 
            background-color: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
            border-top: 5px solid #e30613; 
            margin-bottom: 20px; 
        }
        
        /* KPI */
        .kpi-container {
            background-color: white;
            padding: 10px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-bottom: 3px solid #e30613;
        }
        .kpi-val { font-size: 1.4rem; font-weight: 700; color: #1f2937; }
        
        /* Butonlar */
        .stButton>button { border-radius: 8px; height: 45px; font-weight: 600; width: 100%; }
        
        /* Menü */
        .nav-link-selected { background-color: #e30613 !important; }
        
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- GÜVENLİK ---
if 'giris_yapildi' not in st.session_state: st.session_state['giris_yapildi'] = False
KULLANICI_ADI = "admin"
SIFRE = "1234"

def giris_ekrani():
    st.markdown("<br><br><h2 style='text-align:center; color:#e30613;'>🔐 Özkaraaslan Giriş</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        k = st.text_input("Kullanıcı")
        s = st.text_input("Şifre", type="password")
        if st.button("Giriş", type="primary"):
            if k == KULLANICI_ADI and s == SIFRE:
                st.session_state['giris_yapildi'] = True
                st.rerun()
            else: st.error("Hatalı!")

if not st.session_state['giris_yapildi']:
    giris_ekrani()
    st.stop()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og"
LOGO_URL = "https://www.ozkaraaslanfilo.com/wp-content/uploads/2021/01/logo.png"

SEKTORLER = {
    "🚛 Lojistik": "Lojistik Firmaları", "📦 Nakliye": "Yurt İçi Nakliye Firmaları", "🌍 Uluslararası": "Uluslararası Transport",
    "🤝 Kooperatifler": "Kamyoncular Kooperatifi", "🏭 Fabrikalar (OSB)": "Organize Sanayi Bölgesi Fabrikaları",
    "🚌 Servis/Turizm": "Personel Taşımacılığı", "🏗️ İnşaat": "İnşaat Malzemeleri Toptancıları",
    "🏥 Sağlık/Rehab": "Özel Eğitim ve Rehabilitasyon", "🥕 Gıda Toptancı": "Gıda Toptancıları"
}

# --- PDF OLUŞTURMA ---
def teklif_pdf_olustur(firma_adi, iskonto, vade, yetkili):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Logo
    try: pdf.image(LOGO_URL, x=10, y=8, w=50)
    except: pass
    pdf.ln(20)
    
    # Başlık
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "YAKIT TEDARIK TEKLIFI", ln=True, align='C')
    pdf.ln(10)
    
    # Tarih
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Tarih: {datetime.now().strftime('%d.%m.%Y')}", ln=True, align='R')
    
    # İçerik
    pdf.set_font("Arial", size=12)
    text = f"""
    Sayin {firma_adi} Yetkilisi ({yetkili}),
    
    Ozkaraaslan Filo ve Petrol Ofisi guvencesiyle, firmanizin akaryakit ihtiyaclarini 
    karsilamak adina hazirladigimiz ozel teklifimiz asagidaki gibidir.
    
    Filo Yonetim Sistemi (AutoMatic) ile araclariniz istasyonlarimizda 
    ucret odemeden yakit alabilir, tum tuketimlerinizi tek faturada yonetebilirsiniz.
    """
    pdf.multi_cell(0, 7, text)
    pdf.ln(10)
    
    # Tablo
    pdf.set_fill_color(227, 6, 19)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(95, 10, "Hizmet", 1, 0, 'C', True)
    pdf.cell(95, 10, "Teklif Kosullari", 1, 1, 'C', True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=12)
    pdf.cell(95, 10, "Iskonto Orani (Pompa Fiyati)", 1, 0)
    pdf.cell(95, 10, f"% {iskonto}", 1, 1, 'C')
    
    pdf.cell(95, 10, "Odeme Vadesi", 1, 0)
    pdf.cell(95, 10, f"{vade} Gun", 1, 1, 'C')
    
    pdf.cell(95, 10, "Sistem Kullanimi", 1, 0)
    pdf.cell(95, 10, "Ucretsiz", 1, 1, 'C')
    
    pdf.ln(20)
    
    # İmza
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, "Saygilarimizla,", ln=True, align='R')
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, "Ozkaraaslan Filo Yonetimi", ln=True, align='R')
    pdf.cell(0, 7, "Bolge Mudurlugu", ln=True, align='R')
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- GOOGLE SHEETS ---
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
                             "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki", "Iskonto_Orani", "Dosya_Linki"]
        if not data:
            sheet.append_row(beklenen_sutunlar)
            return pd.DataFrame(columns=beklenen_sutunlar)
        df = pd.DataFrame(data)
        for col in beklenen_sutunlar:
            if col not in df.columns: df[col] = ""
        text_cols = ["Notlar", "Telefon", "Yetkili_Kisi", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email", "Hatirlatici_Saat", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki", "Iskonto_Orani", "Dosya_Linki"]
        for col in text_cols:
            if col in df.columns: df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except: return pd.DataFrame(columns=["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki", "Iskonto_Orani", "Dosya_Linki"])

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
    return f"https://wa.me/{temiz_no}" if len(temiz_no) >= 10 else None

def arama_linki_yap(telefon):
    return f"tel:{telefon}" if (not pd.isna(telefon) and len(str(telefon)) > 5) else None

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
        return f"{base}&text={urllib.parse.quote(baslik)}&dates={dates}&details={urllib.parse.quote(aciklama)}&location={urllib.parse.quote(adres)}"
    except: return None

def detay_getir(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {'place_id': place_id, 'fields': 'formatted_phone_number,website,url', 'key': API_KEY}
    try:
        res = requests.get(url, params=params).json()
        r = res.get('result', {})
        return r.get('formatted_phone_number', ''), r.get('website', ''), r.get('url', '')
    except: return "", "", ""

# --- ANA EKRAN ---
col_logo, col_menu = st.columns([1, 6])
with col_logo:
    st.image(LOGO_URL, width=60)
with col_menu:
    selected = option_menu(
        menu_title=None,
        options=["Pano", "Firma Bul", "Müşteriler", "Teklif & Hesap", "Ajanda"],
        icons=["speedometer2", "search", "person-badge", "file-earmark-text", "calendar-week"],
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "white", "border-radius": "10px"},
            "icon": {"color": "#e30613", "font-size": "14px"}, 
            "nav-link": {"font-size": "12px", "text-align": "center", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#e30613", "color": "white"},
        }
    )

st.write("") 

# --- PANO ---
if selected == "Pano":
    tarih_str = datetime.now().strftime("%d %B %Y")
    st.markdown(f"""<div class="hero-card"><h3>👋 Merhaba, Müdürüm</h3><p>{tarih_str} | Saha Operasyon Paneli</p></div>""", unsafe_allow_html=True)
    st.link_button("⛽ GÜNCEL AKARYAKIT FİYATLARI", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    
    df = veri_tabanini_yukle()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="kpi-container"><div class="kpi-val">{len(df)}</div><p>Müşteri</p></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="kpi-container"><div class="kpi-val" style="color:#f59e0b">{len(df[df["Durum"] == "Yeni"])}</div><p>Bekleyen</p></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="kpi-container"><div class="kpi-val" style="color:#10b981">{len(df[df["Durum"] == "✅ Anlaşıldı"])}</div><p>Başarılı</p></div>""", unsafe_allow_html=True)
        
        st.write("")
        st.markdown("##### 📋 Son Hareketler")
        son_5 = df.tail(5)[["Firma", "Durum", "Yetkili_Kisi"]].iloc[::-1]
        st.dataframe(son_5, hide_index=True, use_container_width=True)
    else: st.info("Veri yükleniyor...")

# --- FİRMA BUL ---
elif selected == "Firma Bul":
    st.markdown("#### 🗺️ Pazar Taraması")
    with st.expander("📍 Arama Ayarları", expanded=True):
        c1, c2 = st.columns(2)
        sehir = c1.text_input("Şehir", "Gaziantep", placeholder="Şehir")
        sektor_key = c2.selectbox("Sektör", list(SEKTORLER.keys()))
        tara_btn = st.button("🚀 Firmaları Tara", type="primary", use_container_width=True)

    if tara_btn:
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
                        tel, web, harita_url = detay_getir(f.get('place_id'))
                        tum_firmalar.append({
                            "Firma": f.get('name'), "Yetkili_Kisi": "", "Telefon": tel, "Web": web, "
