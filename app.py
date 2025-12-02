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

# --- 1. SAYFA AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BOLT / SHADCN TARZI MODERN CSS ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #f8fafc; /* Slate-50 */
            color: #0f172a; /* Slate-900 */
        }
        
        /* Sidebar Tasarımı (Next.js Sidebar'ı gibi) */
        section[data-testid="stSidebar"] {
            background-color: white;
            border-right: 1px solid #e2e8f0; /* İnce gri çizgi */
        }
        
        /* Üst Header (Breadcrumb Alanı) */
        .top-nav {
            background: white;
            padding: 15px 20px;
            border-bottom: 1px solid #e2e8f0;
            margin-top: -60px; /* Streamlit boşluğunu kapat */
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
            color: #64748b;
        }
        .breadcrumb-active {
            color: #0f172a;
            font-weight: 600;
            background-color: #f1f5f9;
            padding: 5px 10px;
            border-radius: 6px;
        }

        /* Kart Tasarımları (Shadcn Card) */
        .modern-card {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            margin-bottom: 15px;
        }
        
        /* KPI Değerleri */
        .kpi-value {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #0f172a;
        }
        .kpi-label {
            font-size: 13px;
            color: #64748b;
            font-weight: 500;
        }
        
        /* Tablolar */
        [data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* Butonlar */
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
            border: 1px solid #e2e8f0;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            transition: all 0.2s;
        }
        .stButton>button:hover {
            border-color: #cbd5e1;
            background-color: #f8fafc;
        }
        
        /* Gizle */
        #MainMenu {visibility: hidden;} 
        footer {visibility: hidden;} 
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- GÜVENLİK ---
if 'giris_yapildi' not in st.session_state: st.session_state['giris_yapildi'] = False
KULLANICI_ADI = "admin"
SIFRE = "1234"

def giris_ekrani():
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown("""
        <div class="modern-card" style="text-align:center; margin-top:50px;">
            <h2 style="color:#e30613; margin-bottom:5px;">Özkaraaslan</h2>
            <p style="color:#64748b; font-size:14px;">Saha Operasyon Paneli</p>
        </div>
        """, unsafe_allow_html=True)
        k = st.text_input("Kullanıcı Adı")
        s = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap", type="primary", use_container_width=True):
            if k == KULLANICI_ADI and s == SIFRE:
                st.session_state['giris_yapildi'] = True
                st.rerun()
            else: st.error("Hatalı Bilgi")

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

# --- FONKSİYONLAR (AYNI ŞEKİLDE KORUNDU) ---
def turkce_karakter_duzelt(text):
    text = text.lower()
    replacements = {'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c', 'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c'}
    for src, target in replacements.items(): text = text.replace(src, target)
    return text

def tr_pdf(text):
    replacements = {'ğ':'g','Ğ':'G','ü':'u','Ü':'U','ş':'s','Ş':'S','ı':'i','İ':'I','ö':'o','Ö':'O','ç':'c','Ç':'C'}
    for k,v in replacements.items(): text = text.replace(k, v)
    return text

def tr_upper(text): return str(text).replace('i', 'İ').replace('ı', 'I').upper() if text else ""
def tr_title(text):
    if not text: return ""
    return " ".join([w[0].replace('i','İ').replace('ı','I').upper() + w[1:].replace('I','ı').replace('İ','i').lower() for w in str(text).split() if w])

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

# --- SIDEBAR (MODERN MENÜ) ---
with st.sidebar:
    st.image(LOGO_URL, width=150)
    
    selected = option_menu(
        menu_title=None,
        options=["Pano", "Firma Bul", "Müşteriler", "Teklif & Hesap", "Ajanda", "Bildirim"],
        icons=["grid-fill", "search", "people-fill", "file-earmark-text-fill", "calendar-event-fill", "bell-fill"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#64748b", "font-size": "18px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin":"5px 0px", "--hover-color": "#f1f5f9", "color": "#334155"},
            "nav-link-selected": {"background-color": "#e30613", "color": "white", "border-radius": "8px"},
        }
    )
    
    st.markdown("---")
    if st.button("🚪 Çıkış Yap", use_container_width=True, type="secondary"):
        st.session_state['giris_yapildi'] = False
        st.rerun()

# --- HEADER (BREADCRUMB) ---
st.markdown(f"""
<div class="top-nav">
    <span style="color:#94a3b8;">Saha Yönetim</span>
    <span style="color:#cbd5e1;">/</span>
    <span class="breadcrumb-active">{selected}</span>
</div>
""", unsafe_allow_html=True)

# --- İÇERİK ---

# --- PANO ---
if selected == "Pano":
    st.markdown("### 👋 Pano")
    st.link_button("⛽ Fiyat Listesi", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    st.write("")
    
    df = veri_tabanini_yukle()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"""<div class="modern-card"><div class="kpi-value">{len(df)}</div><div class="kpi-label">Toplam Müşteri</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="modern-card"><div class="kpi-value" style="color:#f59e0b">{len(df[df["Durum"] == "Yeni"])}</div><div class="kpi-label">Bekleyen</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="modern-card"><div class="kpi-value" style="color:#10b981">{len(df[df["Durum"] == "✅ Anlaşıldı"])}</div><div class="kpi-label">Anlaşma</div></div>""", unsafe_allow_html=True)
        
        st.markdown("##### 📋 Son Aktiviteler")
        son_5 = df.tail(5)[["Firma", "Durum"]].iloc[::-1]
        st.dataframe(son_5, hide_index=True, use_container_width=True)
    else: st.info("Veri bekleniyor...")

# --- FİRMA BUL ---
elif selected == "Firma Bul":
    st.markdown("### 🗺️ Firma Arama")
    with st.expander("📍 Arama Filtreleri", expanded=True):
        c1, c2 = st.columns(2)
        sehir = c1.text_input("Şehir", "Gaziantep", placeholder="Şehir")
        sektor_key = c2.selectbox("Sektör", list(SEKTORLER.keys()))
        if st.button("🚀 Tara", type="primary", use_container_width=True):
            arama_sorgusu = SEKTORLER[sektor_key]
            st.session_state['sonuclar'] = None # Temizle
            tum_firmalar = []
            next_page_token = None
            sayfa = 0
            with st.status("Taranıyor...", expanded=True):
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
            else: st.error("Sonuç yok.")

    if 'sonuclar' in st.session_state:
        df_res = st.session_state['sonuclar']
        with st.expander("📍 Harita"):
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
                st.success("Kaydedildi!")
                time.sleep(1)
            else: st.warning("Seçim yapın.")

# --- MÜŞTERİLER ---
elif selected == "Müşteriler":
    st.markdown("### 👥 Müşterilerim")
    df = veri_tabanini_yukle()
    
    if not df.empty:
        mode = st.radio("", ["Düzenle", "Yeni Ekle"], horizontal=True)
        st.write("")
        
        if mode == "Düzenle":
            arama = st.selectbox("Müşteri:", df["Firma"].tolist())
            secilen = df[df["Firma"] == arama].iloc[0]
            idx = df[df["Firma"] == arama].index[0]
            
            st.markdown(f"""<div class="modern-card" style="border-left: 4px solid #e30613;"><h4>{secilen['Firma']}</h4></div>""", unsafe_allow_html=True)
            
            with st.form("duzenle"):
                c1, c2 = st.columns(2)
                with c1:
                    yetkili = st.text_input("Yetkili", value=secilen.get('Yetkili_Kisi', ''))
                    tel = st.text_input("Telefon", value=secilen['Telefon'])
                    email = st.text_input("Email", value=secilen['Email'])
                with c2:
                    durum = st.selectbox("Durum", ["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz"], index=["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz"].index(secilen['Durum']) if secilen['Durum'] in ["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz"] else 0)
                    tuketim = st.text_input("Tüketim", value=secilen.get('Tuketim_Bilgisi', ''))
                    
                    val_tar = secilen.get('Hatirlatici_Tarih')
                    if pd.isna(val_tar): val_tar = None
                    hatirlat_tar = st.date_input("Randevu", value=val_tar)
                    
                    val_saat = secilen.get('Hatirlatici_Saat', '09:00')
                    try: t_obj = datetime.strptime(str(val_saat), '%H:%M').time()
                    except: t_obj = datetime.strptime('09:00', '%H:%M').time()
                    hatirlat_saat = st.time_input("Saat", value=t_obj)

                adres = st.text_area("Adres", value=secilen['Adres'])
                notlar = st.text_area("Notlar", value=secilen['Notlar'])
                
                if st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True):
                    df.at[idx, 'Yetkili_Kisi'] = yetkili
                    df.at[idx, 'Telefon'] = tel
                    df.at[idx, 'Email'] = email
                    df.at[idx, 'Adres'] = adres
                    df.at[idx, 'Durum'] = durum
                    df.at[idx, 'Tuketim_Bilgisi'] = tuketim
                    df.at[idx, 'Hatirlatici_Tarih'] = pd.to_datetime(hatirlat_tar)
                    df.at[idx, 'Hatirlatici_Saat'] = hatirlat_saat.strftime('%H:%M')
                    df.at[idx, 'Notlar'] = notlar
                    veriyi_kaydet(df)
                    st.toast("Kaydedildi!", icon="✅")
                    time.sleep(1)
                    st.rerun()
            
            if st.button("Sil", type="secondary", use_container_width=True):
                df = df.drop(idx)
                veriyi_kaydet(df)
                st.rerun()

        elif mode == "Yeni Ekle":
            with st.form("yeni"):
                firma = st.text_input("Firma Adı")
                yetkili = st.text_input("Yetkili")
                tel = st.text_input("Telefon")
                notlar = st.text_area("Notlar")
                if st.form_submit_button("Kaydet", type="primary"):
                    yeni_veri = {"Firma": firma, "Yetkili_Kisi": yetkili, "Telefon": tel, "Durum": "Yeni", "Notlar": notlar}
                    df = pd.concat([df, pd.DataFrame([yeni_veri])], ignore_index=True)
                    veriyi_kaydet(df)
                    st.success("Eklendi!")
                    time.sleep(1)
                    st.rerun()
    else: st.info("Liste boş.")

# --- TEKLİF ---
elif selected == "Teklif & Hesap":
    st.markdown("### 🧮 Teklif Robotu")
    
    st.link_button("⛽ Fiyat Listesi", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", use_container_width=True)
    st.write("")
    
    if 'man_fiyat' not in st.session_state: st.session_state['man_fiyat'] = 44.50
    fiyat = st.number_input("⛽ Pompa Fiyatı (TL)", value=st.session_state['man_fiyat'], step=0.1)
    st.session_state['man_fiyat'] = fiyat
    
    c1, c2 = st.columns(2)
    litre = c1.number_input("Aylık Litre", value=1000)
    isk = c2.number_input("İskonto %", value=3.0)
    
    kazanc = (fiyat * (isk/100)) * litre * 12
    st.markdown(f"""<div class="modern-card" style="background:#ecfccb; border:1px solid #84cc16;"><h3 style="color:#365314">Yıllık Kazanç: {kazanc:,.0f} TL</h3></div>""", unsafe_allow_html=True)
    
    st.write("---")
    st.markdown("#### 📄 PDF/Word Oluştur")
    with st.form("teklif"):
        firma = st.text_input("Firma")
        yetkili = st.text_input("Yetkili")
        vade = st.selectbox("Vade", ["Fatura 10 Gün", "DBS", "Ön Ödeme"])
        btn = st.form_submit_button("Oluştur")
    
    if btn and firma:
        c_d1, c_d2 = st.columns(2)
        w_bytes = word_teklif_olustur(firma, isk, 0, vade, yetkili)
        if w_bytes: c_d1.download_button("📥 WORD", w_bytes, f"{firma}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary", use_container_width=True)
        p_bytes = pdf_teklif_olustur(firma, isk, 0, vade, yetkili)
        if p_bytes: c_d2.download_button("📥 PDF", p_bytes, f"{firma}.pdf", "application/pdf", type="secondary", use_container_width=True)

# --- AJANDA & BİLDİRİM ---
elif selected in ["Ajanda", "Bildirim"]:
    st.markdown(f"### {selected}")
    df = veri_tabanini_yukle()
    if not df.empty and "Hatirlatici_Tarih" in df.columns:
        bugun = pd.Timestamp.now().normalize()
        if selected == "Ajanda":
            veri = df[(df["Hatirlatici_Tarih"] >= bugun)].sort_values("Hatirlatici_Tarih")
        else:
            veri = df[(df["Hatirlatici_Tarih"] <= bugun) & (df["Durum"] != "✅ Anlaşıldı")]
            
        if not veri.empty:
            st.dataframe(veri[["Hatirlatici_Tarih", "Firma", "Notlar"]], hide_index=True, use_container_width=True)
        else: st.info("Kayıt yok.")
