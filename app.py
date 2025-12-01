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
    initial_sidebar_state="collapsed" # Mobilde menü kapalı başlar, ekran ferah olur
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
        
        /* Üst Başlık - PO Kırmızısı Gradient */
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
        
        /* Fiyat Butonu Alanı */
        .price-link-container {
            background-color: white;
            padding: 15px;
            border-radius: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid #e5e7eb;
        }
        
        /* KPI Kartları */
        .kpi-card {
            background-color: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            text-align: center;
            border-top: 4px solid #e30613; /* PO Kırmızısı Çizgi */
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
        
        /* Streamlit Elementlerini Gizle */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Buton Stili */
        .stButton>button {
            border-radius: 8px;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri"
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
        df_save = df_save.fillna("") 
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = pd.to_datetime(df_save[col], errors='coerce').dt.strftime('%Y-%m-%d').replace("NaT", "")
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

# 1. BAŞLIK (HEADER)
st.markdown("""
<div class="top-header">
    <div class="header-title">⛽ Petrol Ofisi</div>
    <div class="header-subtitle">Bölge Yönetim & Saha Asistanı</div>
</div>
""", unsafe_allow_html=True)

# Sekmeler
tab_home, tab_search, tab_crm = st.tabs(["🏠 DASHBOARD", "🔎 FİRMA BUL", "📂 PORTFÖY"])

# --- TAB 1: DASHBOARD (ANA EKRAN) ---
with tab_home:
    # --- YENİ EKLENEN ÖZELLİK: DEV FİYAT BUTONU ---
    st.markdown('<div class="price-link-container">', unsafe_allow_html=True)
    st.write("👇 **Bölge Fiyatlarını Kontrol Et**")
    st.link_button("⛽ GÜNCEL AKARYAKIT FİYATLARI (İL İL)", "https://www.petrolofisi.com.tr/akaryakit-fiyatlari", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Verileri Yükle
    df = veri_tabanini_yukle()
    
    # KPI Kartları (Yan yana ve şık)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-number">{len(df)}</div><div class="kpi-label">Toplam</div></div>""", unsafe_allow_html=True)
    with col2:
        yeni = len(df[df["Durum"] == "Yeni"])
        st.markdown(f"""<div class="kpi-card" style="border-top-color: #f59e0b;"><div class="kpi-number">{yeni}</div><div class="kpi-label">Bekleyen</div></div>""", unsafe_allow_html=True)
    with col3:
        basari = len(df[df["Durum"] == "✅ Anlaşıldı"])
        st.markdown(f"""<div class="kpi-card" style="border-top-color: #10b981;"><div class="kpi-number">{basari}</div><div class="kpi-label">Anlaşıldı</div></div>""", unsafe_allow_html=True)
    
    st.write("")
    
    # Grafik ve Ajanda
    if not df.empty:
        g1, g2 = st.columns([1, 1.5])
        with g1:
            st.write("##### 📊 Durum Analizi")
            durum_counts = df["Durum"].value_counts().reset_index()
            durum_counts.columns = ["Durum", "Adet"]
            fig = px.pie(durum_counts, values="Adet", names="Durum", hole=0.6, color_discrete_sequence=px.colors.qualitative.Bold)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=200)
            st.plotly_chart(fig, use_container_width=True)
            
        with g2:
            st.write("##### 📅 Bugünün Ajandası")
            bugun = pd.Timestamp.now().normalize()
            if "Hatirlatici_Tarih" in df.columns:
                isler = df[(df["Hatirlatici_Tarih"] == bugun) & (df["Durum"] != "✅ Anlaşıldı")]
                if not isler.empty:
                    st.warning(f"⚠️ **{len(isler)}** önemli arama var!")
                    for i, row in isler.iterrows():
                        st.info(f"📞 {row['Firma']}")
                else:
                    st.success("Bugün için acil iş yok. Sahaya çıkmaya hazırsınız!")

# --- TAB 2: ARAMA ---
with tab_search:
    with st.container():
        st.write("##### 🕵️‍♂️ Hedef Pazar Analizi")
        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        sehir = c1.text_input("Şehir", "Gaziantep", label_visibility="collapsed", placeholder="Şehir")
        sektor_key = c2.selectbox("Sektör", list(SEKTORLER.keys()), label_visibility="collapsed")
        if c3.button("🔍 Tara", type="primary", use_container_width=True):
            st.session_state['arama_basladi'] = True
    
    if st.session_state.get('arama_basladi'):
        arama_sorgusu = SEKTORLER[sektor_key]
        
        if 'sonuclar' not in st.session_state or st.session_state.get('last_city') != sehir:
            st.session_state['last_city'] = sehir
            tum_firmalar = []
            next_page_token = None
            sayfa = 0
            
            with st.status("Veri çekiliyor...", expanded=True) as status:
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
                                "Adres": f.get('formatted_address'), "Durum": "Yeni", "Notlar": "",
                                "lat": f.get('geometry', {}).get('location', {}).get('lat'),
                                "lon": f.get('geometry', {}).get('location', {}).get('lon')
                            })
                        next_page_token = resp.get('next_page_token')
                        sayfa += 1
                        if not next_page_token: break
                    except: break
                status.update(label="✅ Tamamlandı!", state="complete", expanded=False)
            
            if tum_firmalar:
                df_res = pd.DataFrame(tum_firmalar)
                df_res.insert(0, "Seç", False)
                st.session_state['sonuclar'] = df_res
            else:
                st.error("Sonuç bulunamadı.")

    if 'sonuclar' in st.session_state:
        df_res = st.session_state['sonuclar']
        
        if st.toggle("🗺️ Haritayı Aç / Kapat"):
            st.map(df_res.dropna(subset=['lat','lon']), latitude='lat', longitude='lon', color='#ff0000')
        
        st.write(f"### 📋 {len(df_res)} Firma Listelendi")
        
        edited = st.data_editor(
            df_res,
            column_config={
                "Seç": st.column_config.CheckboxColumn("Ekle", width="small", default=False),
                "Firma": st.column_config.TextColumn("Firma", disabled=True),
                "Web": st.column_config.LinkColumn("Web"),
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("💾 SEÇİLENLERİ KAYDET", type="primary", use_container_width=True):
            secilenler = edited[edited["Seç"]==True].drop(columns=["Seç", "lat", "lon"], errors='ignore')
            if not secilenler.empty:
                with st.spinner("İşleniyor..."):
                    for i, r in secilenler.iterrows():
                        if r["Web"] and len(r["Web"]) > 5:
                            secilenler.at[i, "Email"] = siteyi_tara_mail_bul(r["Web"])
                    mevcut = veri_tabanini_yukle()
                    yeni = pd.concat([mevcut, secilenler], ignore_index=True).drop_duplicates(subset=['Firma'])
                    veriyi_kaydet(yeni)
                st.success(f"✅ {len(secilenler)} firma portföye eklendi!")
                time.sleep(1)
            else:
                st.warning("Lütfen seçim yapın.")

# --- TAB 3: PORTFÖY ---
with tab_crm:
    df_crm = veri_tabanini_yukle()
    if not df_crm.empty:
        if "Sil" not in df_crm.columns: df_crm.insert(0, "Sil", False)
        
        df_crm["WhatsApp"] = df_crm["Telefon"].apply(whatsapp_linki_yap)
        df_crm["Ara"] = df_crm["Telefon"].apply(arama_linki_yap)
        if "Email" not in df_crm.columns: df_crm["Email"] = ""
        df_crm["Mail_At"] = df_crm.apply(lambda x: mail_linki_yap(x.get("Email", ""), x.get("Firma", "")), axis=1)
        
        edited_crm = st.data_editor(
            df_crm,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil", width="small"),
                "Firma": st.column_config.TextColumn("Firma", disabled=True),
                "Ara": st.column_config.LinkColumn("📞", display_text="Ara", width="small"),
                "WhatsApp": st.column_config.LinkColumn("💬", display_text="WP", width="small"),
                "Mail_At": st.column_config.LinkColumn("📧", display_text="Mail", width="small"),
                "Web": st.column_config.LinkColumn("Web"),
                "Email": st.column_config.TextColumn("Email"),
                "Durum": st.column_config.SelectboxColumn("Durum", options=["Yeni", "📞 Arandı", "✅ Anlaşıldı", "❌ Olumsuz", "⏳ Teklif Verildi"], width="medium"),
                "Hatirlatici_Tarih": st.column_config.DateColumn("🔔 Tarih", format="DD.MM.YYYY", min_value=date.today()),
                "Telefon": None, "Adres": None
            },
            hide_index=True, use_container_width=True
        )
        
        if not df.empty and len(edited_crm[edited_crm["Durum"] == "✅ Anlaşıldı"]) > len(df[df["Durum"] == "✅ Anlaşıldı"]):
            st.balloons()
            st.toast("Tebrikler! Yeni bir anlaşma! 🎉", icon="🔥")

        c_del, c_upd = st.columns([1, 2])
        if c_del.button("🗑️ Sil", use_container_width=True):
            kalan = edited_crm[edited_crm["Sil"]==False].drop(columns=["Sil", "WhatsApp", "Ara", "Mail_At"], errors='ignore')
            veriyi_kaydet(kalan)
            st.rerun()
            
        if c_upd.button("💾 GÜNCELLE", type="primary", use_container_width=True):
            kayit = edited_crm.drop(columns=["Sil", "WhatsApp", "Ara", "Mail_At"], errors='ignore')
            veriyi_kaydet(kayit)
            st.toast("Veritabanı güncellendi", icon="✅")
            time.sleep(1)
            st.rerun()
    else:
        st.info("Portföyünüz boş.")

# --- SIDEBAR EKSTRALAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/2/2e/Petrol_Ofisi_logo.svg", width=150)
    st.write("")
    if not df_crm.empty:
        csv = df_crm.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Excel Rapor İndir", csv, "PO_Rapor.csv", "text/csv", use_container_width=True)
