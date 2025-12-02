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
from docxtpl import DocxTemplate
from fpdf import FPDF
import io

# --- 1. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. BOLT-STYLE CSS TASARIMI (PREMIUM UI) ---
def local_css():
    st.markdown("""
    <style>
        /* Modern Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6; /* Çok açık gri-mavi */
            color: #111827;
        }
        
        /* Giriş Kutusu */
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 24px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            text-align: center;
            max-width: 400px;
            margin: 50px auto;
        }
        
        /* Hero Card (Ana Başlık) */
        .hero-card {
            background: linear-gradient(135deg, #e30613 0%, #991b1b 100%);
            padding: 32px;
            border-radius: 24px;
            color: white;
            box-shadow: 0 10px 15px -3px rgba(227, 6, 19, 0.3);
            margin-bottom: 30px;
            text-align: left;
            position: relative;
            overflow: hidden;
        }
        .hero-title { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.5px; margin: 0; }
        .hero-subtitle { font-size: 1rem; opacity: 0.9; font-weight: 400; margin-top: 8px; }
        
        /* KPI Kartları (Dashboard) */
        .kpi-card {
            background: white;
            padding: 24px;
            border-radius: 20px;
            border: 1px solid #e5e7eb;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
            text-align: center;
        }
        .kpi-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
            border-color: #e30613;
        }
        .kpi-value { font-size: 2.2rem; font-weight: 800; color: #111827; }
        .kpi-label { font-size: 0.875rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }
        
        /* Müşteri Kartı (Liste) */
        .customer-card {
            background: white;
            padding: 20px;
            border-radius: 16px;
            border-left: 6px solid #e30613;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 15px;
        }
        
        /* Input Alanları */
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {
            border-radius: 12px !important;
            border: 1px solid #d1d5db !important;
            padding: 12px !important;
            font-size: 1rem !important;
        }
        .stTextInput input:focus {
            border-color: #e30613 !important;
            box-shadow: 0 0 0 2px rgba(227, 6, 19, 0.2) !important;
        }
        
        /* Butonlar */
        .stButton>button {
            border-radius: 12px;
            height: 50px;
            font-weight: 600;
            font-size: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: none;
        }
        
        /* Menü */
        .nav-link-selected { background-color: #e30613 !important; border-radius: 12px !important; }
        
        /* Gizle */
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- GÜVENLİK ---
if 'giris_yapildi' not in st.session_state: st.session_state['giris_yapildi'] = False
KULLANICI_ADI = "admin"
SIFRE = "1234"

def giris_ekrani():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("""
        <div class="login-container">
            <img src="https://upload.wikimedia.org/wikipedia/commons/2/2e/Petrol_Ofisi_logo.svg" width="100">
            <h2 style="margin-top:20px; color:#111827;">Personel Girişi</h2>
            <p style="color:#6b7280;">Saha operasyon sistemine hoş geldiniz.</p>
        </div>
        """, unsafe_allow_html=True)
        
        k = st.text_input("Kullanıcı Adı", placeholder="Kullanıcı adınızı girin")
        s = st.text_input("Şifre", type="password", placeholder="Şifrenizi girin")
        
        if st.button("Giriş Yap", type="primary", use_container_width=True):
            if k == KULLANICI_ADI and s == SIFRE:
                st.session_state['giris_yapildi'] = True
                st.rerun()
            else:
                st.error("Giriş bilgileri hatalı.")

if not st.session_state['giris_yapildi']:
    giris_ekrani()
    st.stop()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og"
SABLON_DOSYASI = "teklif_sablonu.docx" 
LOGO_URL = "https://www.ozkaraaslanfilo.com/wp-content/uploads/2021/01/logo.png"

SEKTORLER = {
    "🚛 Lojistik": "Lojistik Firmaları", "📦 Nakliye": "Yurt İçi Nakliye Firmaları", "🌍 Uluslararası": "Uluslararası Transport",
    "🤝 Kooperatifler": "Kamyoncular Kooperatifi", "🏭 Fabrikalar (OSB)": "Organize Sanayi Bölgesi Fabrikaları",
    "🚌 Servis/Turizm": "Personel Taşımacılığı", "🏗️ İnşaat": "İnşaat Malzemeleri Toptancıları",
    "🏥 Sağlık/Rehab": "Özel Eğitim ve Rehabilitasyon", "🥕 Gıda Toptancı": "Gıda Toptancıları"
}

# --- FİYAT ÇEKME MOTORU (V43.0) ---
def turkce_karakter_duzelt(text):
    text = text.lower()
    replacements = {'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c', 'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'}
    for src, target in replacements.items():
        text = text.replace(src, target)
    return text

@st.cache_data(ttl=3600)
def fiyat_cek_garanti(sehir):
    try:
        sehir_slug = turkce_karakter_duzelt(sehir)
        url = f"https://kur.doviz.com/akaryakit-fiyatlari/{sehir_slug}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=4)
        if response.status_code == 200:
            dfs = pd.read_html(response.content)
            for df in dfs:
                if "Petrol Ofisi" in str(df) or "PETROL OFİSİ" in str(df):
                    for index, row in df.iterrows():
                        if "petrol ofisi" in str(row.values).lower():
                            values = [str(x).replace('TL', '').replace(',', '.').strip() for x in row if isinstance(x, (int, float, str))]
                            for val in values:
                                try:
                                    fiyat = float(val)
                                    if 35 < fiyat < 60: return fiyat
                                except: continue
    except: pass
    return 0.0

# --- WORD & PDF FORMATLAMA ---
def tr_upper(text):
    return str(text).replace('i', 'İ').replace('ı', 'I').upper() if text else ""

def tr_title(text):
    if not text: return ""
    return " ".join([w[0].replace('i','İ').replace('ı','I').upper() + w[1:].replace('I','ı').replace('İ','i').lower() for w in str(text).split() if w])

def tr_pdf(text):
    replacements = {'ğ':'g','Ğ':'G','ü':'u','Ü':'U','ş':'s','Ş':'S','ı':'i','İ':'I','ö':'o','Ö':'O','ç':'c','Ç':'C'}
    for k,v in replacements.items(): text = text.replace(k, v)
    return text

def word_teklif_olustur(firma_adi, iskonto_pompa, iskonto_istasyon, odeme_sekli, yetkili):
    try:
        doc = DocxTemplate(SABLON_DOSYASI)
        context = {
            'firma_adi': tr_upper(firma_adi), 'yetkili': tr_title(yetkili),
            'iskonto_pompa': f"% {iskonto_pompa}", 'iskonto_istasyon': f"% {iskonto_istasyon}",
            'odeme_sekli': str(odeme_sekli), 'tarih': datetime.now().strftime("%d.%m.%Y")
        }
        doc.render(context)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()
    except: return None

def pdf_teklif_olustur(firma_adi, iskonto_pompa, iskonto_istasyon, odeme_sekli, yetkili):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        try: pdf.image(LOGO_URL, x=10, y=8, w=50)
        except: pass
        pdf.ln(20)
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "YAKIT TEDARIK TEKLIFI", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"Tarih: {datetime.now().strftime('%d.%m.%Y')}", ln=True, align='R')
        pdf.set_font("Arial", size=12)
        text = tr_pdf(f"Sayin {yetkili} ({firma_adi}),\n\nOzkaraaslan Filo ve Petrol Ofisi guvencesiyle ozel teklifimiz asagidaki gibidir.")
        pdf.multi_cell(0, 7, text)
        pdf.ln(10)
        pdf.set_fill_color(227, 6, 19); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 12)
        pdf.cell(95, 10, "Hizmet", 1, 0, 'C', True); pdf.cell(95, 10, "Kosullar", 1, 1, 'C', True)
        pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", size=12)
        pdf.cell(95, 10, "Pompa Iskontosu", 1, 0); pdf.cell(95, 10, f"% {iskonto_pompa}", 1, 1, 'C')
        pdf.cell(95, 10, "Anlasmali Ist. Iskonto", 1, 0); pdf.cell(95, 10, f"% {iskonto_istasyon}", 1, 1, 'C')
        pdf.cell(95, 10, "Odeme Sekli", 1, 0); pdf.cell(95, 10, tr_pdf(odeme_sekli), 1, 1, 'C')
        pdf.ln(20); pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, "Saygilarimizla,", ln=True, align='R')
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 7, "Ozkaraaslan Filo Yonetimi", ln=True, align='R')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return None

# --- GOOGLE SHEETS ---
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "info" in creds_dict:
        import json
        creds_dict = json.loads(creds_dict["info"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10)
def veri_tabanini_yukle():
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        data = sheet.get_all_records()
        beklenen = ["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", 
                             "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", 
                             "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki", "Iskonto_Orani", "Dosya_Linki"]
        if not data:
            sheet.append_row(beklenen)
            return pd.DataFrame(columns=beklenen)
        df = pd.DataFrame(data)
        for col in beklenen:
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
        df_save = df_save.astype(str).replace("nan", "").replace("NaT", "").replace("None", "")
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.cache_data.clear()
    except Exception as e: st.error(f"Kayıt Hatası: {e}")

# --- YARDIMCI FONKSİYONLAR ---
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
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-title">👋 Merhaba, Müdürüm</div>
        <div class="hero-subtitle">📅 {tarih_str} | Saha Operasyon Paneli</div>
    </div>
    """, unsafe_allow_html=True)
    
    df = veri_tabanini_yukle()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="kpi-card"><div class="kpi-value">{len(df)}</div><div class="kpi-label">Toplam Müşteri</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="kpi-card" style="border-bottom-color: #f59e0b;"><div class="kpi-value" style="color:#f59e0b">{len(df[df["Durum"] == "Yeni"])}</div><div class="kpi-label">Bekleyen</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="kpi-card" style="border-bottom-color: #10b981;"><div class="kpi-value" style="color:#10b981">{len(df[df["Durum"] == "✅ Anlaşıldı"])}</div><div class="kpi-label">Başarılı</div></div>""", unsafe_allow_html=True)
        
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
        st.toast("Aranıyor...", icon="⏳")
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
                            "Firma": f.get('name'), "Yetkili_Kisi": "", "Telefon": tel, "Web": web, "Email": "",
                            "Adres": f.get('formatted_address'), "Durum": "Yeni", "Notlar": "", 
                            "Tuketim_Bilgisi": "", "Arac_Sayisi": "", "Firma_Sektoru": sektor_key,
                            "Konum_Linki": harita_url, "Iskonto_Orani": "", "Dosya_Linki": "",
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
        with st.expander("📍 Harita Görünümü"):
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
            else: st.warning("Lütfen seçim yapın.")

# --- TAB 3: MÜŞTERİLER ---
elif selected == "Müşteriler":
    st.markdown("#### 👥 Müşteri Portföyü")
    df = veri_tabanini_yukle()
    
    if not df.empty:
        with st.expander("🌪️ Filtreleme & Arama", expanded=False):
            c1, c2 = st.columns(2)
            f_durum = c1.multiselect("Durum", df["Durum"].unique()) if not df.empty else []
            f_sektor = c2.multiselect("Sektör", df["Firma_Sektoru"].unique()) if not df.empty else []
    
    df_show = df.copy()
    if f_durum: df_show = df_show[df_show["Durum"].isin(f_durum)]
    if f_sektor: df_show = df_show[df_show["Firma_Sektoru"].isin(f_sektor)]

    mode = st.radio("İşlem:", ["📂 Düzenle", "➕ Yeni Ekle"], horizontal=True, label_visibility="collapsed")
    st.write("")
    
    if mode == "📂 Düzenle":
        if not df_show.empty:
            arama_terimi = st.selectbox("Müşteri Seç:", df_show["Firma"].tolist())
            secilen_veri = df[df["Firma"] == arama_terimi].iloc[0]
            idx = df[df["Firma"] == arama_terimi].index[0]
            
            st.markdown(f"""<div class="customer-card"><h3 style="margin:0; color:#e30613;">🏢 {secilen_veri['Firma']}</h3></div>""", unsafe_allow_html=True)
            
            with st.form("musteri_duzenle"):
                c1, c2 = st.columns(2)
                with c1:
                    yeni_yetkili = st.text_input("👤 Yetkili İsim", value=secilen_veri.get('Yetkili_Kisi', ''))
                    yeni_tel = st.text_input("Telefon", value=secilen_veri['Telefon'])
                    yeni_email = st.text_input("Email", value=secilen_veri['Email'])
                    yeni_arac = st.text_input("🚛 Araç Sayısı", value=secilen_veri.get('Arac_Sayisi', ''))
                with c2:
                    durum_listesi = ["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz"]
                    try: m_idx = durum_listesi.index(secilen_veri['Durum'])
                    except: m_idx = 0
                    yeni_durum = st.selectbox("Durum", durum_listesi, index=m_idx)
                    yeni_tuketim = st.text_input("Tüketim (m3/Ton)", value=secilen_veri.get('Tuketim_Bilgisi', ''))
                    yeni_iskonto = st.text_input("💸 İskonto (%)", value=secilen_veri.get('Iskonto_Orani', ''))
                    
                    st.write("🗓️ **Randevu**")
                    col_d, col_t = st.columns(2)
                    val_hatirlat_tar = secilen_veri.get('Hatirlatici_Tarih')
                    if pd.isna(val_hatirlat_tar): val_hatirlat_tar = None
                    yeni_hatirlat_tar = col_date.date_input("Tarih", value=val_hatirlat_tar)
                    val_hatirlat_saat = secilen_veri.get('Hatirlatici_Saat', '09:00')
                    try: time_obj = datetime.strptime(str(val_hatirlat_saat), '%H:%M').time()
                    except: time_obj = datetime.strptime('09:00', '%H:%M').time()
                    yeni_hatirlat_saat = col_time.time_input("Saat", value=time_obj)

                yeni_adres = st.text_area("Adres", value=secilen_veri['Adres'], height=60)
                yeni_konum = st.text_input("📍 Konum Linki", value=secilen_veri.get('Konum_Linki', ''))
                yeni_dosya = st.text_input("📄 Dosya Linki", value=secilen_veri.get('Dosya_Linki', ''))
                yeni_not = st.text_area("Görüşme Notları", value=secilen_veri['Notlar'])
                
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                if arama_linki_yap(yeni_tel): col_b1.link_button("📞 Ara", arama_linki_yap(yeni_tel), use_container_width=True)
                if whatsapp_linki_yap(yeni_tel): col_b2.link_button("💬 WP", whatsapp_linki_yap(yeni_tel), use_container_width=True)
                nav_link = navigasyon_linki_yap(yeni_adres, yeni_konum)
                if nav_link: col_b3.link_button("🗺️ Yol", nav_link, use_container_width=True)
                cal_link = google_calendar_link(f"Görüşme: {secilen_veri['Firma']}", yeni_hatirlat_tar, yeni_hatirlat_saat.strftime('%H:%M'), yeni_adres, yeni_not)
                if cal_link: col_b4.link_button("📅 Takvim", cal_link, use_container_width=True)
                
                if yeni_dosya and "http" in yeni_dosya:
                    st.link_button("📂 Dosyayı Aç", yeni_dosya, type="secondary", use_container_width=True)
                
                kaydet_btn = st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
            
            if kaydet_btn:
                df.at[idx, 'Yetkili_Kisi'] = yeni_yetkili
                df.at[idx, 'Telefon'] = yeni_tel
                df.at[idx, 'Email'] = yeni_email
                df.at[idx, 'Adres'] = yeni_adres
                df.at[idx, 'Durum'] = yeni_durum
                df.at[idx, 'Tuketim_Bilgisi'] = yeni_tuketim
                df.at[idx, 'Arac_Sayisi'] = yeni_arac
                df.at[idx, 'Konum_Linki'] = yeni_konum
                df.at[idx, 'Iskonto_Orani'] = yeni_iskonto
                df.at[idx, 'Dosya_Linki'] = yeni_dosya
                df.at[idx, 'Hatirlatici_Tarih'] = pd.to_datetime(yeni_hatirlat_tar)
                df.at[idx, 'Hatirlatici_Saat'] = yeni_hatirlat_saat.strftime('%H:%M')
                df.at[idx, 'Notlar'] = yeni_not
                veriyi_kaydet(df)
                st.success("✅ Güncellendi!")
                time.sleep(1)
                st.rerun()

            if st.button("🗑️ Sil", type="secondary", use_container_width=True):
                df = df.drop(idx)
                veriyi_kaydet(df)
                st.rerun()
        else: st.info("Listeniz boş.")

    elif mode == "➕ Yeni Ekle":
        st.markdown("""<div class="customer-card"><h4>✨ Yeni Müşteri</h4></div>""", unsafe_allow_html=True)
        with st.form("yeni_ekle"):
            firma_adi = st.text_input("🏢 Firma Adı (Zorunlu)")
            c1, c2 = st.columns(2)
            with c1:
                yetkili = st.text_input("👤 Yetkili")
                tel = st.text_input("📞 Telefon")
                email = st.text_input("📧 Email")
                sektor = st.text_input("🏭 Sektör")
            with c2:
                adres = st.text_area("Adres", height=100)
                tuketim = st.text_input("Tüketim")
                arac = st.text_input("🚛 Araç")
                iskonto = st.text_input("💸 İskonto (%)")
            
            konum_link = st.text_input("📍 Konum (Link)")
            dosya_link = st.text_input("📄 Dosya Linki")
            
            st.write("📅 **Randevu**")
            col_d, col_t = st.columns(2)
            yeni_tar = col_d.date_input("Tarih", value=None)
            yeni_saat = col_t.time_input("Saat", value=None)
            notlar = st.text_area("Notlar")
            
            kaydet_yeni = st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
        
        if kaydet_yeni:
            if firma_adi:
                hatirlat_str = yeni_tar.strftime('%Y-%m-%d') if yeni_tar else ""
                saat_str = yeni_saat.strftime('%H:%M') if yeni_saat else ""
                yeni_veri = {
                    "Firma": firma_adi, "Yetkili_Kisi": yetkili, "Telefon": tel, "Web": "", "Email": email,
                    "Adres": adres, "Durum": "Yeni", "Notlar": notlar,
                    "Tuketim_Bilgisi": tuketim, "Arac_Sayisi": arac, "Firma_Sektoru": sektor, 
                    "Konum_Linki": konum_link, "Iskonto_Orani": iskonto, "Dosya_Linki": dosya_link,
                    "Sozlesme_Tarihi": "", "Hatirlatici_Tarih": hatirlat_str, "Hatirlatici_Saat": saat_str, "Ziyaret_Tarihi": ""
                }
                df = pd.concat([df, pd.DataFrame([yeni_veri])], ignore_index=True)
                veriyi_kaydet(df)
                st.success(f"{firma_adi} Eklendi!")
                if yeni_tar:
                    cal_link = google_calendar_link(f"PO Görüşme: {firma_adi}", yeni_tar, saat_str, adres, notlar)
                    if cal_link: st.link_button("📅 TAKVİME EKLE", cal_link, type="secondary", use_container_width=True)
                time.sleep(3)
                st.rerun()
            else: st.error("Firma Adı zorunlu.")

# --- YENİ TAB: TEKLİF & HESAP ---
elif selected == "Teklif & Hesap":
    st.markdown("#### 🧮 Hesaplama & Teklif")
    
    # Fiyat Linki (En tepede)
    st.link_button("⛽ RESMİ FİYAT LİSTESİ", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    st.write("")
    
    tab_hesap, tab_pdf = st.tabs(["💰 Tasarruf Hesapla", "📑 Word & PDF Teklif"])
    
    with tab_hesap:
        # MANUEL FİYAT GİRİŞİ
        if 'manual_price' not in st.session_state: st.session_state['manual_price'] = 44.50 
        guncel_fiyat_giris = st.number_input("⛽ BÖLGE POMPA FİYATI (TL):", value=st.session_state['manual_price'], step=0.10)
        st.session_state['manual_price'] = guncel_fiyat_giris 

        st.markdown("---")
        
        c1, c2 = st.columns(2)
        with c1:
            aylik_litre = st.number_input("Aylık Tüketim (Litre)", min_value=0, value=1000)
            guncel_fiyat = st.number_input("Baz Alınan Fiyat", value=st.session_state['manual_price'], disabled=True)
        with c2:
            iskonto_orani = st.number_input("Pompa İskonto (%)", min_value=0.0, max_value=15.0, value=3.0)
            iskonto_anlasmali = st.number_input("Anlaşmalı İstasyon İskonto (%)", min_value=0.0, max_value=15.0, value=0.0)
        
        st.markdown("---")
        if aylik_litre > 0:
            # HESAPLAMALAR
            indirimli_pompa = guncel_fiyat * (1 - (iskonto_orani/100))
            aylik_kazanc_pompa = (guncel_fiyat - indirimli_pompa) * aylik_litre
            yillik_kazanc_pompa = aylik_kazanc_pompa * 12
            
            indirimli_ist = guncel_fiyat * (1 - (iskonto_anlasmali/100))
            aylik_kazanc_ist = (guncel_fiyat - indirimli_ist) * aylik_litre
            yillik_kazanc_ist = aylik_kazanc_ist * 12
            
            col_res1, col_res2 = st.columns(2)
            
            with col_res1:
                st.markdown(f"""
                <div class='compare-box' style='background:#e0f2fe; border:1px solid #7dd3fc;'>
                    <h4>⛽ Pompa (%{iskonto_orani})</h4>
                    <div class='price-tag' style='color:#0369a1;'>{indirimli_pompa:,.2f} TL</div>
                    <small>İndirimli Litre Fiyatı</small>
                    <hr style='margin:10px 0; opacity:0.3;'>
                    <p>Aylık Kazanç: <b>{aylik_kazanc_pompa:,.2f} TL</b></p>
                    <p>Yıllık Kazanç: <b>{yillik_kazanc_pompa:,.2f} TL</b></p>
                </div>
                """, unsafe_allow_html=True)
                
            with col_res2:
                st.markdown(f"""
                <div class='compare-box' style='background:#dcfce7; border:1px solid #86efac;'>
                    <h4>🏪 Anlaşmalı İst. (%{iskonto_anlasmali})</h4>
                    <div class='price-tag' style='color:#15803d;'>{indirimli_ist:,.2f} TL</div>
                    <small>İndirimli Litre Fiyatı</small>
                    <hr style='margin:10px 0; opacity:0.3;'>
                    <p>Aylık Kazanç: <b>{aylik_kazanc_ist:,.2f} TL</b></p>
                    <p>Yıllık Kazanç: <b>{yillik_kazanc_ist:,.2f} TL</b></p>
                </div>
                """, unsafe_allow_html=True)

    with tab_pdf:
        st.info("👇 Word veya PDF Teklif Oluştur")
        with st.form("pdf_form"):
            p_firma = st.text_input("Firma Adı")
            p_yetkili = st.text_input("Yetkili")
            
            col_pdf1, col_pdf2 = st.columns(2)
            p_iskonto_pompa = col_pdf1.number_input("Pompa İskonto (%)", value=3.0)
            p_iskonto_istasyon = col_pdf2.number_input("Anlaşmalı İst. İskonto (%)", value=0.0)
            
            odeme_secenekleri = [
                "Fatura Kesiminden 5 Gün Sonra", 
                "Fatura Kesiminden 10 Gün Sonra", 
                "Fatura Kesiminden 15 Gün Sonra",
                "Ayın 5'i", "Ayın 10'u", "Ayın 15'i", "Ayın 20'si", "Ayın 25'i",
                "Ön Ödeme (Havale/EFT)", "Kredi Kartı ile Ödeme", "DBS (Doğrudan Borçlandırma)"
            ]
            p_odeme = st.selectbox("Ödeme/Vade Şekli", odeme_secenekleri)
            
            generate_btn = st.form_submit_button("📄 Teklif Oluştur (Word & PDF)")
        
        if generate_btn:
            if p_firma:
                col_d1, col_d2 = st.columns(2)
                # Word
                try:
                    word_bytes = word_teklif_olustur(p_firma, p_iskonto_pompa, p_iskonto_istasyon, p_odeme, p_yetkili)
                    if word_bytes: col_d1.download_button("📥 WORD İNDİR", word_bytes, f"{p_firma}_Teklif.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary")
                    else: col_d1.error("Şablon Yok!")
                except: col_d1.error("Word Hatası")

                # PDF
                try:
                    pdf_bytes = pdf_teklif_olustur(p_firma, p_iskonto_pompa, p_iskonto_istasyon, p_odeme, p_yetkili)
                    if pdf_bytes: col_d2.download_button("📥 PDF İNDİR", pdf_bytes, f"{p_firma}_Teklif.pdf", "application/pdf", type="secondary")
                except: col_d2.error("PDF Hatası")
            else: st.error("Firma adı giriniz.")

# --- AJANDA ---
elif selected == "Ajanda":
    st.markdown("#### 📅 Randevular")
    df = veri_tabanini_yukle()
    if not df.empty and "Hatirlatici_Tarih" in df.columns:
        bugun = pd.Timestamp.now().normalize()
        gelecek = df[(df["Hatirlatici_Tarih"] >= bugun) & (df["Durum"] != "✅ Anlaşıldı")].copy()
        if not gelecek.empty:
            gelecek = gelecek.sort_values(by=["Hatirlatici_Tarih", "Hatirlatici_Saat"])
            st.dataframe(gelecek[["Hatirlatici_Tarih", "Hatirlatici_Saat", "Firma", "Yetkili_Kisi", "Notlar"]], 
                         column_config={"Hatirlatici_Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"), "Hatirlatici_Saat": "Saat", "Yetkili_Kisi": "Yetkili"}, 
                         hide_index=True, use_container_width=True)
        else: st.success("Randevu yok.")

# --- BİLDİRİM ---
elif selected == "Bildirim":
    st.markdown("#### 🔔 Acil İşler")
    df = veri_tabanini_yukle()
    if not df.empty and "Hatirlatici_Tarih" in df.columns:
        bugun = pd.Timestamp.now().normalize()
        acil = df[(df["Hatirlatici_Tarih"] <= bugun) & (df["Durum"] != "✅ Anlaşıldı")]
        if not acil.empty:
            for i, r in acil.iterrows(): 
                saat = f"⏰ {r.get('Hatirlatici_Saat', '')}" if r.get('Hatirlatici_Saat') else ""
                st.error(f"⚠️ **{r['Firma']}**: {r['Notlar']} ({saat})")
        else: st.info("Temiz.")
