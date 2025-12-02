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
import io

# --- 1. SAYFA VE PERFORMANS AYARLARI ---
st.set_page_config(
    page_title="Özkaraaslan Saha",
    page_icon="⛽", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. OPTİMİZE EDİLMİŞ CSS ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #f4f6f9; }
        
        /* Kartlar ve Kutular */
        .hero-card { background: linear-gradient(135deg, #e30613 0%, #8a040b 100%); padding: 20px; border-radius: 12px; color: white; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .kpi-container { background: white; padding: 10px; border-radius: 10px; text-align: center; border-bottom: 3px solid #e30613; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .kpi-val { font-size: 1.3rem; font-weight: 700; color: #1f2937; }
        .customer-card { background: white; padding: 20px; border-radius: 12px; border-top: 4px solid #e30613; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .compare-box { padding: 15px; border-radius: 10px; text-align: center; color: #333; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        
        /* Genel Elementler */
        .stButton>button { border-radius: 8px; height: 45px; font-weight: 600; width: 100%; }
        #MainMenu, footer, header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
local_css()

# --- GÜVENLİK ---
if 'giris_yapildi' not in st.session_state: st.session_state['giris_yapildi'] = False
KULLANICI_ADI = "admin"
SIFRE = "1234"

def giris_ekrani():
    st.markdown("<br><h2 style='text-align:center; color:#e30613;'>🔐 Giriş</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            k = st.text_input("Kullanıcı")
            s = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap", type="primary"):
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
SABLON_DOSYASI = "teklif_sablonu.docx" 
LOGO_URL = "https://www.ozkaraaslanfilo.com/wp-content/uploads/2021/01/logo.png"

SEKTORLER = {
    "🚛 Lojistik": "Lojistik Firmaları", "📦 Nakliye": "Yurt İçi Nakliye Firmaları", "🌍 Uluslararası": "Uluslararası Transport",
    "🤝 Kooperatifler": "Kamyoncular Kooperatifi", "🏭 Fabrikalar (OSB)": "Organize Sanayi Bölgesi Fabrikaları",
    "🚌 Servis/Turizm": "Personel Taşımacılığı", "🏗️ İnşaat": "İnşaat Malzemeleri Toptancıları",
    "🏥 Sağlık/Rehab": "Özel Eğitim ve Rehabilitasyon", "🥕 Gıda Toptancı": "Gıda Toptancıları"
}

# --- GOOGLE SHEETS BAĞLANTISI (CACHED - HIZLANDIRILMIŞ) ---
@st.cache_resource(ttl=3600) # Bağlantıyı 1 saat hafızada tut
def init_connection():
    """Google Sheets bağlantısını bir kere kurar ve hafızada tutar"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "info" in creds_dict:
        import json
        creds_dict = json.loads(creds_dict["info"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10) # Veriyi 10 saniye önbellekte tut (Sürekli yenilemesin)
def veri_tabanini_yukle():
    try:
        client = init_connection()
        sheet = client.open(SHEET_ADI).sheet1
        data = sheet.get_all_records()
        beklenen = ["Firma", "Yetkili_Kisi", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", 
                             "Sozlesme_Tarihi", "Hatirlatici_Tarih", "Hatirlatici_Saat", 
                             "Tuketim_Bilgisi", "Ziyaret_Tarihi", "Arac_Sayisi", "Firma_Sektoru", "Konum_Linki", "Iskonto_Orani", "Dosya_Linki"]
        
        if not data:
            # Eğer boşsa başlıkları basmamız gerekebilir ama cache_data bunu handle eder genelde
            return pd.DataFrame(columns=beklenen)
            
        df = pd.DataFrame(data)
        # Eksik sütun kontrolü
        for col in beklenen:
            if col not in df.columns: df[col] = ""
        
        # Veri tiplerini temizle
        df = df.astype(str).replace("nan", "").replace("None", "")
        
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
        return df
    except Exception as e:
        st.error(f"Veri hatası: {e}")
        return pd.DataFrame()

def veriyi_kaydet(df):
    try:
        client = init_connection() # Cached bağlantıyı kullan
        sheet = client.open(SHEET_ADI).sheet1
        df_save = df.copy()
        
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi", "Ziyaret_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d')
        
        df_save = df_save.astype(str).replace("nan", "").replace("NaT", "").replace("None", "")
        
        sheet.clear()
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        st.cache_data.clear() # Kayıt yapınca önbelleği temizle ki yeni veri görünsün
    except Exception as e: st.error(f"Kayıt Hatası: {e}")

# --- FİYAT ÇEKME (HATA KORUMALI) ---
def fiyat_cek_manuel(sehir):
    """Döviz.com'dan fiyat çeker - Hata verirse 0 döner, çökmez"""
    try:
        url = f"https://kur.doviz.com/akaryakit-fiyatlari/{sehir.lower().replace('ı','i').replace('ğ','g').replace('ü','u').replace('ş','s').replace('ö','o').replace('ç','c')}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=4) # 4 saniye bekle, gelmezse bırak
        if response.status_code == 200:
            dfs = pd.read_html(response.content)
            for df in dfs:
                if "Petrol Ofisi" in str(df):
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

# --- DİĞER FONKSİYONLAR ---
def word_teklif_olustur(firma_adi, iskonto_pompa, iskonto_istasyon, odeme_sekli, yetkili):
    try:
        doc = DocxTemplate(SABLON_DOSYASI)
        context = {
            'firma_adi': firma_adi, 'yetkili': yetkili, 'iskonto_pompa': iskonto_pompa, 
            'iskonto_istasyon': iskonto_istasyon, 'odeme_sekli': odeme_sekli, 'tarih': datetime.now().strftime("%d.%m.%Y")
        }
        doc.render(context)
        bio = io.BytesIO()
        doc.save(bio)
        return bio.getvalue()
    except: return None

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
        res = requests.get(url, params=params, timeout=3).json() # 3 sn timeout
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
        options=["Pano", "Firma Bul", "Müşteriler", "Teklif", "Ajanda"],
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
    st.markdown(f"""<div class="hero-card"><h3>👋 Merhaba, Müdürüm</h3><p>{tarih_str} | Saha Paneli</p></div>""", unsafe_allow_html=True)
    
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
        with st.expander("🌪️ Filtreleme", expanded=False):
            c1, c2 = st.columns(2)
            f_durum = c1.multiselect("Durum", df["Durum"].unique())
            f_sektor = c2.multiselect("Sektör", df["Firma_Sektoru"].unique())
            
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
                        
                        st.write("🗓️ **Randevu**")
                        col_date, col_time = st.columns(2)
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
                    df.at[idx, 'Firma_Sektoru'] = yeni_sektor
                    df.at[idx, 'Konum_Linki'] = yeni_konum
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
    else: st.info("Veri yok.")

# --- TEKLİF ---
elif selected == "Teklif":
    st.markdown("#### 🧮 Hesaplama & Teklif")
    tab_hesap, tab_pdf = st.tabs(["💰 Tasarruf Hesapla", "📑 Word Teklif"])
    
    with tab_hesap:
        # GÜNCEL FİYAT BUTONU
        st.link_button("⛽ Güncel Fiyat Listesi (PO)", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="secondary", use_container_width=True)
        
        # Manuel Fiyat Girişi (En Sağlıklı Yöntem)
        col_fiyat, col_litre = st.columns(2)
        guncel_fiyat = col_fiyat.number_input("⛽ Pompa Fiyatı (TL)", value=44.50, step=0.1)
        aylik_litre = col_litre.number_input("Aylık Tüketim (Litre)", value=1000)
        
        c1, c2 = st.columns(2)
        iskonto_pompa = c1.number_input("Pompa İskonto (%)", value=3.0)
        iskonto_ist = c2.number_input("İstasyon İskonto (%)", value=0.0)
        
        st.markdown("---")
        if aylik_litre > 0:
            ind_pompa = guncel_fiyat * (1 - (iskonto_pompa/100))
            kar_pompa = (guncel_fiyat - ind_pompa) * aylik_litre * 12
            
            ind_ist = guncel_fiyat * (1 - (iskonto_ist/100))
            kar_ist = (guncel_fiyat - ind_ist) * aylik_litre * 12
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.markdown(f"""<div class='compare-box' style='background:#e0f2fe; border:1px solid #7dd3fc;'><h4>⛽ Pompa (%{iskonto_pompa})</h4><div class='price-tag'>{ind_pompa:.2f} TL</div><p>Yıllık Kazanç: <b>{kar_pompa:,.0f} TL</b></p></div>""", unsafe_allow_html=True)
            with col_r2:
                st.markdown(f"""<div class='compare-box' style='background:#dcfce7; border:1px solid #86efac;'><h4>🏪 İstasyon (%{iskonto_ist})</h4><div class='price-tag'>{ind_ist:.2f} TL</div><p>Yıllık Kazanç: <b>{kar_ist:,.0f} TL</b></p></div>""", unsafe_allow_html=True)

    with tab_pdf:
        with st.form("pdf_form"):
            p_firma = st.text_input("Firma")
            p_yetkili = st.text_input("Yetkili")
            c1, c2 = st.columns(2)
            p_isk_pompa = c1.number_input("Pompa %", value=3.0)
            p_isk_ist = c2.number_input("İstasyon %", value=0.0)
            p_vade = st.selectbox("Vade", ["Fatura 10 Gün", "DBS", "Ön Ödeme"])
            btn_pdf = st.form_submit_button("📄 Oluştur")
        
        if btn_pdf and p_firma:
            wb = word_teklif_olustur(p_firma, p_isk_pompa, p_isk_ist, p_vade, p_yetkili)
            if wb: st.download_button("📥 İNDİR", wb, f"{p_firma}_Teklif.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", type="primary")
            else: st.error("Şablon yok.")

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
                         column_config={"Hatirlatici_Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY")}, 
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
            for i, r in acil.iterrows(): st.error(f"⚠️ **{r['Firma']}**: {r['Notlar']}")
        else: st.info("Temiz.")
