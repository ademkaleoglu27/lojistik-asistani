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
    page_title="Lojistik Pro",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. ÖZEL CSS ---
def local_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #f8f9fa;
        }
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1e3a8a;
            text-align: center;
            margin-bottom: 20px;
        }
        .stButton>button {
            border-radius: 12px;
            font-weight: 600;
            border: none;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            height: 50px;
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.15);
        }
        div[data-testid="stMetric"] {
            background-color: white;
            padding: 15px;
            border-radius: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border: 1px solid #e5e7eb;
        }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
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
            if col not in df.columns:
                df[col] = ""
        
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum", "Web", "Email"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                
        return df
    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")
        return pd.DataFrame(columns=["Firma", "Telefon", "Web", "Email", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Hatirlatici_Tarih"])

def veriyi_kaydet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_ADI).sheet1
        df_save = df.copy()
        
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df_save.columns:
                df_save[col] = df_save[col].dt.strftime('%Y-%m-%d').replace("NaT", "")
        
        for col in ["Web", "Email"]:
            if col not in df_save.columns:
                df_save[col] = ""
                
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
    konu = urllib.parse.quote(f"{firma_adi} - İş Birliği")
    icerik = urllib.parse.quote(f"Merhaba,\n\nFirmanızla lojistik/servis süreçlerinde çalışmak isteriz.\n\nSaygılar.")
    return f"mailto:{email}?subject={konu}&body={icerik}"

def whatsapp_linki_yap(telefon):
    if pd.isna(telefon) or len(str(telefon)) < 5: return None
    temiz_no = re.sub(r'\D', '', str(telefon))
    if len(temiz_no) < 10: return None
    if temiz_no.startswith("0"): 
        temiz_no = "90" + temiz_no[1:]
    elif not temiz_no.startswith("90") and len(temiz_no) == 10: 
        temiz_no = "90" + temiz_no
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
st.markdown('<div class="main-header">🚛 Lojistik Asistanı</div>', unsafe_allow_html=True)
tab_home, tab_search, tab_crm = st.tabs(["🏠 ÖZET", "🔍 FİRMA BUL", "📂 PORTFÖY"])

# --- TAB 1: DASHBOARD ---
with tab_home:
    df = veri_tabanini_yukle()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Kayıt", len(df))
    c2.metric("Yeni / Bekleyen", len(df[df["Durum"] == "Yeni"]))
    c3.metric("Anlaşma", len(df[df["Durum"] == "✅ Anlaşıldı"]))
    
    st.markdown("---")
    
    bugun = pd.Timestamp.now().normalize()
    if "Hatirlatici_Tarih" in df.columns:
        isler = df[(df["Hatirlatici_Tarih"] == bugun) & (df["Durum"] != "✅ Anlaşıldı")]
        if not isler.empty:
            st.warning(f"🔔 Bugün araman gereken {len(isler)} müşteri var!")
            st.dataframe(isler[["Firma", "Notlar"]], hide_index=True, use_container_width=True)
        else:
            st.success("✅ Bugün için acil bir hatırlatma yok.")

# --- TAB 2: ARAMA ---
with tab_search:
    with st.container():
        col_city, col_cat = st.columns([1, 1.5])
        sehir = col_city.text_input("📍 Şehir", "Gaziantep")
        sektor_key = col_cat.selectbox("Kategori", list(SEKTORLER.keys()))
        search_btn = st.button("🚀 Firmaları Tara", type="primary", use_container_width=True)
    
    if search_btn:
        arama_sorgusu = SEKTORLER[sektor_key]
        st.toast(f"📡 {sehir} taranıyor...", icon="⏳")
        
        tum_firmalar = []
        next_page_token = None
        sayfa = 0
        
        with st.status("Veriler Google'dan çekiliyor...", expanded=True) as status:
            while sayfa < 3:
                status.write(f"Sayfa {sayfa+1} taranıyor...")
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
                            "Adres": f.get('formatted_address'), "Durum": "Yeni", "Notlar": ""
                        })
                    next_page_token = resp.get('next_page_token')
                    sayfa += 1
                    if not next_page_token: break
                except: break
            status.update(label="✅ Tarama Tamamlandı!", state="complete", expanded=False)
            
        if tum_firmalar:
            df_res = pd.DataFrame(tum_firmalar)
            df_res.insert(0, "Seç", False)
            st.session_state['sonuclar'] = df_res
            st.balloons()
        else:
            st.error("Sonuç bulunamadı.")
            
    if 'sonuclar' in st.session_state:
        st.info("👇 Listeden eklemek istediklerinizi seçip en alttaki 'Kaydet' butonuna basın.")
        
        edited = st.data_editor(
            st.session_state['sonuclar'],
            column_config={
                "Seç": st.column_config.CheckboxColumn("Ekle", width="small", default=False),
                "Firma": st.column_config.TextColumn("Firma Adı", disabled=True),
                "Web": st.column_config.LinkColumn("Web"),
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("💾 SEÇİLENLERİ KAYDET", type="primary", use_container_width=True):
            secilenler = edited[edited["Seç"]==True].drop(columns=["Seç"], errors='ignore')
            if not secilenler.empty:
                with st.spinner("Mail adresleri aranıyor ve kaydediliyor..."):
                    for i, r in secilenler.iterrows():
                        if r["Web"] and len(r["Web"]) > 5:
                            secilenler.at[i, "Email"] = siteyi_tara_mail_bul(r["Web"])
                            
                    mevcut = veri_tabanini_yukle()
                    yeni = pd.concat([mevcut, secilenler], ignore_index=True).drop_duplicates(subset=['Firma'])
                    veriyi_kaydet(yeni)
                st.success(f"✅ {len(secilenler)} firma eklendi!")
                time.sleep(1)
            else:
                st.warning("Seçim yapmadınız.")

# --- TAB 3: PORTFÖY ---
with tab_crm:
    df_crm = veri_tabanini_yukle()
    if not df_crm.empty:
        if "Sil" not in df_crm.columns: df_crm.insert(0, "Sil", False)
        
        df_crm["WhatsApp"] = df_crm["Telefon"].apply(whatsapp_linki_yap)
        df_crm["Ara"] = df_crm["Telefon"].apply(arama_linki_yap)
        
        # Email kontrolü ve lambda düzeltmesi
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
        
        c_del, c_upd = st.columns([1, 2])
        if c_del.button("🗑️ Sil", use_container_width=True):
            kalan = edited_crm[edited_crm["Sil"]==False].drop(columns=["Sil", "WhatsApp", "Ara", "Mail_At"], errors='ignore')
            veriyi_kaydet(kalan)
            st.rerun()
            
        if c_upd.button("💾 GÜNCELLE", type="primary", use_container_width=True):
            kayit = edited_crm.drop(columns=["Sil", "WhatsApp", "Ara", "Mail_At"], errors='ignore')
            veriyi_kaydet(kayit)
            st.toast("Veriler Güncellendi", icon="✅")
            time.sleep(1)
            st.rerun()
    else:
        st.info("Listeniz boş.")
