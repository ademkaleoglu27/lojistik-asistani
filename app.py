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

# --- 1. SAYFA AYARLARI ---
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
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
            background-color: #f8f9fa;
        }
        
        /* Menü Stili İyileştirmesi */
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
        
        /* KPI Kartları (Dashboard) */
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
        .kpi-title {
            font-size: 0.9rem;
            color: #6c757d;
            font-weight: 500;
            margin-bottom: 5px;
        }
        .kpi-value {
            font-size: 2rem;
            font-weight: 700;
            color: #212529;
        }
        
        /* Müşteri Kartı */
        .customer-card { 
            background-color: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); 
            border-left: 5px solid #e30613; 
            margin-bottom: 20px; 
        }
        
        /* Butonlar */
        .stButton>button { 
            border-radius: 12px; 
            height: 50px; 
            font-weight: 600; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        /* Gizleme */
        #MainMenu {visibility: hidden;} 
        footer {visibility: hidden;} 
        header {visibility: hidden;}
        
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
        beklenen_sutunlar = ["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", 
                             "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", 
                             "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki"]
        if not data:
            sheet.append_row(beklenen_sutunlar)
            return pd.DataFrame(columns=beklenen_sutunlar)
        df = pd.DataFrame(data)
        for col in beklenen_sutunlar:
            if col not in df.columns: df[col] = ""
        
        # Veri temizliği
        text_cols = ["Notlar", "Telefon", "Yetkili_Kisi", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email", "Hatirlatici_Saat", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki"]
        for col in text_cols:
            if col in df.columns: df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
            
        # Tarih formatları
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

# --- ANA EKRAN VE MENÜ ---

# Logo Kaldırıldı (İstek üzerine)
# st.image(LOGO_URL, width=150) -> SİLİNDİ

# 🌟 MODERN YATAY MENÜ
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

st.write("") # Boşluk

# --- SAYFA 1: PANO ---
if selected == "Pano":
    tarih_str = datetime.now().strftime("%d %B %Y")
    st.markdown(f"<h4 style='color:#333; margin-bottom:5px;'>👋 Merhaba, Hoşgeldin</h4><p style='color:#888; font-size:14px;'>{tarih_str}</p>", unsafe_allow_html=True)
    
    st.link_button("⛽ GÜNCEL AKARYAKIT FİYATLARI", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    st.write("")

    df = veri_tabanini_yukle()
    if not df.empty:
        # PREMIUM KPI KARTLARI
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

# --- SAYFA 2: FİRMA BUL ---
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
    mode = st.radio("İşlem:", ["📂 Düzenle", "➕ Yeni Ekle"], horizontal=True, label_visibility="collapsed")
    st.write("")
    
    if mode == "📂 Düzenle":
        if not df.empty:
            arama_terimi = st.selectbox("Müşteri Seç:", df["Firma"].tolist())
            secilen_veri = df[df["Firma"] == arama_terimi].iloc[0]
            idx = df[df["Firma"] == arama_terimi].index[0]
            
            st.markdown(f"""<div class="customer-card"><h4>🏢 {secilen_veri['Firma']}</h4></div>""", unsafe_allow_html=True)
            
            with st.form("musteri_duzenle"):
                c1, c2 = st.columns(2)
                with c1:
                    yeni_yetkili = st.text_input("👤 Yetkili İsim", value=secilen_veri.get('Yetkili_Kisi', ''))
                    yeni_tel = st.text_input("Telefon", value=secilen_veri['Telefon'])
                    yeni_email = st.text_input("Email", value=secilen_veri['Email'])
                    yeni_arac = st.text_input("🚛 Araç Sayısı", value=secilen_veri.get('Arac_Sayisi', ''))
                    yeni_sektor = st.text_input("🏭 Sektör", value=secilen_veri.get('Firma_Sektoru', ''))
                with c2:
                    durum_listesi = ["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz"]
                    try: m_idx = durum_listesi.index(secilen_veri['Durum'])
                    except: m_idx = 0
                    yeni_durum = st.selectbox("Durum", durum_listesi, index=m_idx)
                    yeni_tuketim = st.text_input("Tüketim (m3/Ton)", value=secilen_veri.get('Tuketim_Bilgisi', ''))
                    st.write("🗓️ **Randevu & Bildirim**")
                    col_date, col_time = st.columns(2)
                    val_hatirlat_tar = secilen_veri.get('Hatirlatici_Tarih')
                    if pd.isna(val_hatirlat_tar): val_hatirlat_tar = None
                    yeni_hatirlat_tar = col_date.date_input("Tarih", value=val_hatirlat_tar)
                    val_hatirlat_saat = secilen_veri.get('Hatirlatici_Saat', '09:00')
                    try: time_obj = datetime.strptime(str(val_hatirlat_saat), '%H:%M').time()
                    except: time_obj = datetime.strptime('09:00', '%H:%M').time()
                    yeni_hatirlat_saat = col_time.time_input("Saat", value=time_obj)

                yeni_adres = st.text_area("Adres", value=secilen_veri['Adres'], height=60)
                yeni_konum = st.text_input("📍 Konum (Link)", value=secilen_veri.get('Konum_Linki', ''))
                yeni_not = st.text_area("Görüşme Notları", value=secilen_veri['Notlar'])
                
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                if arama_linki_yap(yeni_tel): col_b1.link_button("📞", arama_linki_yap(yeni_tel), use_container_width=True)
                if whatsapp_linki_yap(yeni_tel): col_b2.link_button("💬", whatsapp_linki_yap(yeni_tel), use_container_width=True)
                nav_link = navigasyon_linki_yap(yeni_adres, yeni_konum)
                if nav_link: col_b3.link_button("🗺️", nav_link, use_container_width=True)
                cal_link = google_calendar_link(f"Görüşme: {secilen_veri['Firma']}", yeni_hatirlat_tar, yeni_hatirlat_saat.strftime('%H:%M'), yeni_adres, yeni_not)
                if cal_link: col_b4.link_button("📅", cal_link, use_container_width=True)
                
                kaydet_btn = st.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
            
            if kaydet_btn:
                df.at[idx, 'Yetkili_Kisi'] = yeni_yetkili
                df.at[idx, 'Telefon'] = yeni_tel
                df.at[idx, 'Email'] = yeni_email
                df.at[idx, 'Adres'] = yeni_adres
                df.at[idx, 'Durum'] = yeni_durum
                df.at[idx, 'Tuketim_Bilgisi'] = yeni_tuketim
                df.at[idx, 'Arac_Sayisi'] = yeni_arac
                df.at[idx, 'Firma_Sektoru'] = yeni_sektor
                df.at[idx, 'Konum_Linki'] = yeni_konum
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
                st.success("Silindi.")
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
            konum_link = st.text_input("📍 Konum (Link)")
            st.markdown("---")
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
                    "Tuketim_Bilgisi": tuketim, "Arac_Sayisi": arac, "Firma_Sektoru": sektor, "Konum_Linki": konum_link,
                    "Sozlesme_Tarihi": "", "Hatirlatici_Tarih": hatirlat_str, "Hatirlatici_Saat": saat_str, "Ziyaret_Tarihi": ""
                }
                df = pd.concat([df, pd.DataFrame([yeni_veri])], ignore_index=True)
                veriyi_kaydet(df)
                st.success(f"{firma_adi} Eklendi!")
                if yeni_tar:
                    cal_link = google_calendar_link(f"Görüşme: {firma_adi}", yeni_tar, saat_str, adres, notlar)
                    if cal_link: st.link_button("📅 TAKVİME EKLE", cal_link, type="secondary", use_container_width=True)
                time.sleep(3)
                st.rerun()
            else: st.error("Firma Adı zorunlu.")

# --- SAYFA 4: AJANDA ---
elif selected == "Ajanda":
    st.markdown("#### 📅 Randevular")
    df = veri_tabanini_yukle()
    if not df.empty and "Hatirlatici_Tarih" in df.columns:
        bugun = pd.Timestamp.now().normalize()
        gelecek = df[(df["Hatirlatici_Tarih"] >= bugun) & (df["Durum"] != "✅ Anlaşıldı")].copy()
        if not gelecek.empty:
            gelecek = gelecek.sort_values(by=["Hatirlatici_Tarih", "Hatirlatici_Saat"])
            st.info("Yaklaşan Görüşmeleriniz:")
            st.dataframe(gelecek[["Hatirlatici_Tarih", "Hatirlatici_Saat", "Firma", "Yetkili_Kisi", "Notlar"]], 
                         column_config={"Hatirlatici_Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"), "Hatirlatici_Saat": "Saat", "Yetkili_Kisi": "Yetkili"}, 
                         hide_index=True, use_container_width=True)
        else: st.success("Planlanmış bir görüşmeniz yok.")

# --- SAYFA 5: BİLDİRİM ---
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
