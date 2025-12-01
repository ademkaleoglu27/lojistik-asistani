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
    page_title="Lojistik Pro (Bulut)", 
    page_icon="☁️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SABİTLER ---
SHEET_ADI = "Lojistik_Verileri" # Google'da açtığın tablonun adı
# API KEY (Harita için) - Secrets'dan da çekilebilir ama buraya yazalım
API_KEY = "BURAYA_API_KEYINI_YAPISTIR" 

# --- ARAMA KATEGORİLERİ ---
SEKTORLER = {
    "🚛 Lojistik Firmaları": "Lojistik Firmaları",
    "📦 Yurt İçi Nakliye": "Yurt İçi Nakliye Firmaları",
    "🌍 Uluslararası Lojistik": "Uluslararası Transport",
    "🤝 Kamyoncular Koop.": "Kamyoncular Kooperatifi",
    "🚌 Personel Servisi": "Personel Taşımacılığı",
    "🏭 Gıda Toptancıları": "Gıda Toptancıları ve Üreticileri",
    "🏥 Rehabilitasyon Merkezleri": "Özel Eğitim ve Rehabilitasyon",
    "🏗️ İnşaat Malzemeleri": "İnşaat Malzemeleri Toptancıları",
    "🏭 Organize Sanayi": "Organize Sanayi Bölgesi Fabrikaları"
}

# --- GOOGLE SHEETS BAĞLANTISI ---
def get_google_sheet_client():
    """Secrets'daki anahtarı kullanarak Google'a bağlanır"""
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
    """Google Sheets'ten verileri çeker"""
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
        
        # Veri tiplerini düzelt
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
        
        # Tarih formatları
        for col in ["Hatirlatici_Tarih", "Sozlesme_Tarihi"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                
        return df
        
    except Exception as e:
        # Bağlantı hatası olursa (örneğin ilk açılışta tablo bulunamazsa)
        st.error(f"Google Sheets Bağlantı Hatası: {e}")
        st.info("Lütfen Google Drive'da 'Lojistik_Verileri' adında bir tablo olduğundan ve robotla paylaşıldığından emin olun.")
        return pd.DataFrame(columns=["Firma", "Telefon", "Adres", "Durum", "Notlar", "Sozlesme_Tarihi", "Tuketim_Bilgisi", "Hatirlatici_Tarih"])

def veriyi_kaydet(df):
    """Verileri Google Sheets'e yazar (Tamamen silip yeniden yazar)"""
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
        # Başlıkları ve veriyi ekle
        sheet.update([df_save.columns.values.tolist()] + df_save.values.tolist())
        
    except Exception as e:
        st.error(f"Kayıt Başarısız: {e}")

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
    st.caption("Bulut Versiyon v8.0")
    st.markdown("---")
    
    secim = st.radio(
        "Menü",
        ["🏠 Dashboard", "🗺️ Firma Arama", "📂 Portföy (Kalıcı)"],
        index=0
    )
    st.markdown("---")
    
    with st.expander("📝 Hızlı Şablonlar"):
        sablon = st.selectbox("Seç:", ["Tanışma", "Fiyat Teklifi"])
        if sablon == "Tanışma":
            st.code("Merhaba, [Firma] adına yazıyorum. Bölgenizdeki yükleriniz için tanışmak isteriz.", language="text")
        else:
            st.code("Sayın Yetkili, talep ettiğiniz güzergah için fiyat çalışmamız ektedir.", language="text")

# --- SAYFA 1: DASHBOARD ---
if secim == "🏠 Dashboard":
    st.title("📊 Yönetim Paneli")
    
    with st.spinner("Google E-Tablo'dan veriler çekiliyor..."):
        df = veri_tabanini_yukle()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam Firma", len(df), border=True)
    c2.metric("Bekleyen", len(df[df["Durum"] == "Yeni"]), border=True)
    c3.metric("Anlaşılan", len(df[df["Durum"] == "✅ Anlaşıldı"]), border=True)
    
    st.markdown("---")
    
    if not df.empty:
        # Grafikler
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Durum Analizi")
            durum_sayilari = df["Durum"].value_counts().reset_index()
            durum_sayilari.columns = ["Durum", "Adet"]
            fig = px.pie(durum_sayilari, values="Adet", names="Durum", hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        
        with g2:
            st.subheader("🔔 Bugünün İşleri")
            if "Hatirlatici_Tarih" in df.columns:
                bugun = pd.Timestamp.now().normalize()
                hatirlatmalar = df[
                    (df["Hatirlatici_Tarih"] <= bugun) & 
                    (df["Hatirlatici_Tarih"].notnull()) &
                    (df["Durum"] != "✅ Anlaşıldı")
                ]
                if not hatirlatmalar.empty:
                    st.error(f"{len(hatirlatmalar)} adet bekleyen iş var!")
                    st.dataframe(hatirlatmalar[["Firma", "Notlar"]], hide_index=True)
                else:
                    st.success("Bugün için hatırlatma yok.")

# --- SAYFA 2: ARAMA ---
elif secim == "🗺️ Firma Arama":
    st.title("🗺️ Sektörel Tarama")
    
    c1, c2 = st.columns(2)
    sehir = c1.text_input("📍 Şehir", "Gaziantep")
    sektor_key = c2.selectbox("🚛 Sektör", list(SEKTORLER.keys()))
    
    if st.button("🔍 Firmaları Bul", type="primary", use_container_width=True):
        arama_sorgusu = SEKTORLER[sektor_key]
        st.info(f"📡 {sehir} bölgesinde '{arama_sorgusu}' aranıyor...")
        
        tum_firmalar = []
        next_page_token = None
        sayfa = 0
        bar = st.progress(0)
        
        while sayfa < 3:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {'query': f"{sehir} {arama_sorgusu}", 'key': API_KEY, 'language': 'tr'}
            if next_page_token:
                params['pagetoken'] = next_page_token
                time.sleep(2)
            
            try:
                resp = requests.get(url, params=params).json()
                results = resp.get('results', [])
                for f in results:
                    geo = f.get('geometry', {}).get('location', {})
                    tum_firmalar.append({
                        "Firma": f.get('name'),
                        "Telefon": detay_getir(f.get('place_id')),
                        "Adres": f.get('formatted_address'),
                        "lat": geo.get('lat'),
                        "lon": geo.get('lng'),
                        "Durum": "Yeni", "Notlar": "", "Tuketim_Bilgisi": ""
                    })
                    time.sleep(0.05)
                
                next_page_token = resp.get('next_page_token')
                sayfa += 1
                bar.progress(sayfa/3)
                if not next_page_token: break
            except: break
            
        if tum_firmalar:
            df_temp = pd.DataFrame(tum_firmalar)
            df_temp.insert(0, "Seç", False)
            st.session_state['sonuclar'] = df_temp
            st.success(f"✅ {len(tum_firmalar)} firma bulundu.")
        else:
            st.error("Sonuç yok.")
            
    if 'sonuclar' in st.session_state:
        df_res = st.session_state['sonuclar']
        st.map(df_res.dropna(subset=['lat','lon']), latitude='lat', longitude='lon', color='#ff0000')
        
        edited = st.data_editor(df_res, column_config={"Seç": st.column_config.CheckboxColumn("Ekle?", default=False)}, hide_index=True)
        
        if st.button("💾 Google E-Tabloya Kaydet", type="primary"):
            secilenler = edited[edited["Seç"]==True].drop(columns=["Seç", "lat", "lon"], errors='ignore')
            if not secilenler.empty:
                mevcut = veri_tabanini_yukle()
                yeni = pd.concat([mevcut, secilenler], ignore_index=True).drop_duplicates(subset=['Firma'])
                veriyi_kaydet(yeni)
                st.toast("Veriler Buluta Kaydedildi! ☁️", icon="✅")
                time.sleep(1)
            else:
                st.warning("Seçim yapın.")

# --- SAYFA 3: PORTFÖY ---
elif secim == "📂 Portföy (Kalıcı)":
    st.title("📂 Bulut Portföyü")
    
    with st.spinner("Veriler yükleniyor..."):
        df_crm = veri_tabanini_yukle()
    
    if not df_crm.empty:
        if "Sil" not in df_crm.columns: df_crm.insert(0, "Sil", False)
        
        # Linkler
        df_crm["WhatsApp"] = df_crm["Telefon"].apply(whatsapp_linki_yap)
        df_crm["Ara"] = df_crm["Telefon"].apply(arama_linki_yap)
        df_crm["Yol_Tarifi"] = df_crm["Adres"].apply(harita_linki_yap)
        
        edited_crm = st.data_editor(
            df_crm,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil", width="small"),
                "Firma": st.column_config.TextColumn("Firma", disabled=True),
                "Ara": st.column_config.LinkColumn("📞", display_text="Ara", width="small"),
                "WhatsApp": st.column_config.LinkColumn("💬", display_text="Mesaj", width="small"),
                "Yol_Tarifi": st.column_config.LinkColumn("🗺️", display_text="Git", width="small"),
                "Durum": st.column_config.SelectboxColumn("Durum", options=["Yeni", "📞 Arandı", "✅ Anlaşıldı", "❌ Olumsuz"]),
                "Sozlesme_Tarihi": st.column_config.DateColumn("Sözleşme", format="DD.MM.YYYY"),
                "Hatirlatici_Tarih": st.column_config.DateColumn("🔔 Hatırlat", format="DD.MM.YYYY", min_value=date.today()),
                "Telefon": None, "Adres": None
            },
            hide_index=True,
            use_container_width=True
        )
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🗑️ SİL"):
                kalan = edited_crm[edited_crm["Sil"]==False].drop(columns=["Sil", "WhatsApp", "Ara", "Yol_Tarifi"])
                veriyi_kaydet(kalan)
                st.rerun()
        with c2:
            if st.button("💾 GÜNCELLE (Bulut)", type="primary"):
                kayit = edited_crm.drop(columns=["Sil", "WhatsApp", "Ara", "Yol_Tarifi"], errors='ignore')
                veriyi_kaydet(kayit)
                st.toast("Google Sheets Güncellendi!", icon="✅")
                time.sleep(1)
                st.rerun()
    else:
        st.info("Portföy boş. Arama sayfasından ekleme yapın.")
