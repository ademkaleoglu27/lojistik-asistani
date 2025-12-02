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

# --- 1. GÜVENLİK AYARLARI (BURAYI DEĞİŞTİR) ---
KULLANICI_ADI = "admin"
SIFRE = "1234"

# --- 2. SAYFA VE TASARIM AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="🚛", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 3. PREMIUM CSS TASARIMI ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            background-color: #f8f9fa;
        }
        
        /* Giriş Ekranı Tasarımı */
        .login-box {
            padding: 30px;
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            text-align: center;
            border-top: 5px solid #e30613;
            margin-top: 50px;
        }
        
        /* Menü Stili */
        .nav-link {
            font-size: 14px !important;
            text-align: center !important;
            margin: 0px !important;
            padding: 10px !important;
            border-radius: 10px !important;
        }
        .nav-link:hover {
            background-color: #f0f2f6 !important;
            color: #e30613 !important;
        }
        
        /* KPI Kartları */
        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            text-align: center;
            border-bottom: 4px solid #e30613;
            transition: transform 0.2s;
        }
        .kpi-card:hover {
            transform: translateY(-5px);
        }
        .kpi-title { font-size: 0.9rem; color: #6c757d; font-weight: 500; margin-bottom: 5px; }
        .kpi-value { font-size: 2rem; font-weight: 700; color: #212529; }
        
        /* Müşteri Kartı Başlığı */
        .customer-card-header {
            background: linear-gradient(to right, #ffffff, #f8f9fa);
            padding: 20px 25px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.12); 
            border-left: 8px solid #e30613;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
        }
        .customer-card-icon { font-size: 2.2rem; margin-right: 15px; }
        .customer-card-title { margin: 0; color: #111827; font-weight: 800; font-size: 1.6rem; letter-spacing: -0.5px; text-transform: uppercase; }
        
        /* Müşteri Kartı */
        .customer-card { background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 5px solid #e30613; margin-bottom: 20px; }
        
        /* Butonlar */
        .stButton>button { border-radius: 12px; height: 50px; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- GİRİŞ KONTROLÜ (Login Check) ---
if 'giris_yapildi' not in st.session_state:
    st.session_state['giris_yapildi'] = False

def giris_ekrani():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-box">
            <h2 style="color:#e30613;">🔐 Personel Girişi</h2>
            <p style="color:#666;">Lütfen bilgilerinizi giriniz.</p>
        </div>
        """, unsafe_allow_html=True)
        
        kullanici = st.text_input("Kullanıcı Adı")
        sifre = st.text_input("Şifre", type="password")
        
        if st.button("Giriş Yap", type="primary", use_container_width=True):
            if kullanici == KULLANICI_ADI and sifre == SIFRE:
                st.session_state['giris_yapildi'] = True
                st.success("Giriş Başarılı! Yönlendiriliyorsunuz...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Hatalı kullanıcı adı veya şifre!")

# Eğer giriş yapılmadıysa sadece giriş ekranını göster ve kodu durdur
if not st.session_state['giris_yapildi']:
    giris_ekrani()
    st.stop() # Kodun geri kalanını okuma

# --- BURADAN AŞAĞISI SADECE GİRİŞ YAPILINCA ÇALIŞIR ---

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
    except: return "", "", ""

# --- ARAYÜZ (GİRİŞ YAPILDIYSA BURASI ÇALIŞIR) ---

# Çıkış Yap Butonu (Sağ Üst)
col_head1, col_head2 = st.columns([5, 1])
with col_head1:
    st.markdown('<div class="main-header">🚛 Lojistik Asistanı</div>', unsafe_allow_html=True)
with col_head2:
    if st.button("Çıkış Yap"):
        st.session_state['giris_yapildi'] = False
        st.rerun()

# Menü
selected = option_menu(
    menu_title=None,
    options=["Pano", "Firma Bul", "Müşteriler", "Ajanda", "Bildirim"],
    icons=["speedometer2", "search", "person-badge", "calendar-week", "bell"],
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {"padding": "5px", "background-color": "white", "border-radius": "15px", "box-shadow": "0 2px 10px rgba(0,0,0,0.05)"},
        "icon": {"color": "#e30613", "font-size": "18px"}, 
        "nav-link": {"font-size": "13px", "text-align": "center", "margin":"2px", "color": "#444"},
        "nav-link-selected": {"background-color": "#e30613", "color": "white", "border-radius": "10px"},
    }
)

st.write("") 

# --- TAB 1: PANO ---
if selected == "Pano":
    tarih_str = datetime.now().strftime("%d %B %Y")
    st.markdown(f"<h4 style='color:#333; margin-bottom:5px;'>👋 Hoşgeldin</h4><p style='color:#888; font-size:14px;'>{tarih_str}</p>", unsafe_allow_html=True)
    st.link_button("⛽ GÜNCEL AKARYAKIT FİYATLARI", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    st.write("")

    df = veri_tabanini_yukle()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="kpi-card"><div class="kpi-title">Toplam Kayıt</div><div class="kpi-value">{len(df)}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="kpi-card" style="border-bottom-color: #f59e0b;"><div class="kpi-title">Bekleyen</div><div class="kpi-value" style="color:#f59e0b">{len(df[df["Durum"] == "Yeni"])}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="kpi-card" style="border-bottom-color: #10b981;"><div class="kpi-title">Anlaşıldı</div><div class="kpi-value" style="color:#10b981">{len(df[df["Durum"] == "✅ Anlaşıldı"])}</div></div>""", unsafe_allow_html=True)
        
        st.write("")
        st.write("")
        
        tab_g1, tab_g2 = st.tabs(["📊 Satış Analizi", "📋 Son Eklenenler"])
        with tab_g1:
            durum_counts = df["Durum"].value_counts().reset_index()
            durum_counts.columns = ["Durum", "Adet"]
            fig = px.pie(durum_counts, values="Adet", names="Durum", hole=0.7, color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=250)
            st.plotly_chart(fig, use_container_width=True)
            
        with tab_g2:
            son_5 = df.tail(5)[["Firma", "Durum", "Yetkili_Kisi"]].iloc[::-1]
            st.dataframe(son_5, hide_index=True, use_container_width=True)
    else:
        st.info("Veri yükleniyor veya liste boş...")

# --- TAB 2: FİRMA BUL ---
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
                            "Firma": f.get('name'), "Yetkili_Kisi": "", "Telefon": tel, "Web": web, "Email": "",
                            "Adres": f.get('formatted_address'), "Durum": "Yeni", "Notlar": "", 
                            "Tuketim_Bilgisi": "", "Arac_Sayisi": "", "Firma_Sektoru": sektor_key,
                            "Konum_Linki": harita_url,
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
        edited = st.data_editor(df_res, column_config={"Seç": st.column_config.CheckboxColumn("Ekle", default
