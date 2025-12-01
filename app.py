import streamlit as st
import requests
import pandas as pd
import time
import os
import re
import urllib.parse
import shutil # Yedekleme için
import plotly.express as px # Grafikler için
from datetime import datetime, date

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Lojistik Pro", 
    page_icon="🚛", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SABİTLER ---
CRM_DOSYASI = "crm_data.csv"
YEDEK_KLASORU = "yedekler"
# Kendi API Anahtarını buraya yapıştır:
API_KEY = "AIzaSyCw0bhZ2WTrZtThjgJBMsbjZ7IDh6QN0Og" 

# --- ARAMA KATEGORİLERİ (ÖZEL LİSTE) ---
SEKTORLER = {
    "🚛 Lojistik Firmaları": "Lojistik Firmaları",
    "📦 Yurt İçi Taşıma/Nakliye": "Yurt İçi Nakliye ve Taşımacılık Firmaları",
    "🌍 Uluslararası Lojistik": "Uluslararası Lojistik ve Transport Firmaları",
    "🤝 Taşıyıcılar & Kamyoncular Koop.": "Kamyoncular ve Taşıyıcılar Kooperatifi",
    "🚌 Personel ve Öğrenci Servisi": "Personel ve Öğrenci Taşımacılığı Turizm Firmaları",
    "🎫 Turizm & Otobüs Firmaları": "Turizm ve Otobüs İşletmeleri",
    "🏭 Gıda Firmaları (Potansiyel Müşteri)": "Gıda Üreticileri ve Toptancıları Fabrikaları",
    "🏥 Rehabilitasyon Merkezleri (Servis İçin)": "Özel Eğitim ve Rehabilitasyon Merkezleri",
    "🏗️ İnşaat & Yapı Malzemeleri": "İnşaat ve Yapı Malzemeleri Toptancıları",
    "🏭 Organize Sanayi Fabrikaları": "Organize Sanayi Bölgesi Fabrikaları"
}

# --- YARDIMCI FONKSİYONLAR ---
def veri_tabanini_yukle():
    if os.path.exists(CRM_DOSYASI):
        df = pd.read_csv(CRM_DOSYASI)
        
        # Eksik sütunları tamamla
        yeni_sutunlar = ["Sozlesme_Tarihi", "Tuketim_Bilgisi", "Hatirlatici_Tarih"]
        for col in yeni_sutunlar:
            if col not in df.columns:
                df[col] = None
        
        # Veri tiplerini zorla (Hata önleyici)
        text_cols = ["Notlar", "Telefon", "Tuketim_Bilgisi", "Firma", "Adres", "Durum"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
            
        # Tarih formatlarını düzelt
        df["Hatirlatici_Tarih"] = pd.to_datetime(df["Hatirlatici_Tarih"], errors='coerce')
        df["Sozlesme_Tarihi"] = pd.to_datetime(df["Sozlesme_Tarihi"], errors='coerce')

        return df
    else:
        return pd.DataFrame(columns=[
            "Firma", "Telefon", "Adres", "Durum", "Notlar", 
            "Sozlesme_Tarihi", "Tuketim_Bilgisi", "Hatirlatici_Tarih"
        ])

def veriyi_kaydet(df):
    # 1. Önce Yedek Al
    if not os.path.exists(YEDEK_KLASORU):
        os.makedirs(YEDEK_KLASORU)
    
    tarih_damgasi = datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists(CRM_DOSYASI):
        shutil.copy(CRM_DOSYASI, f"{YEDEK_KLASORU}/yedek_{tarih_damgasi}.csv")

    # 2. Kaydet
    df.to_csv(CRM_DOSYASI, index=False)

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
    st.write("Saha Satış Yönetim Paneli v7.0")
    st.markdown("---")
    
    secim = st.radio(
        "Menü",
        ["🏠 Dashboard & Analiz", "🗺️ Gelişmiş Arama", "📂 Portföy & İşlemler"],
        index=0
    )
    
    st.markdown("---")
    
    # TEKLİF SİHİRBAZI (YENİ)
    with st.expander("📝 Hızlı Mesaj Şablonları"):
        sablon_turu = st.selectbox("Şablon Seç", ["Tanışma", "Fiyat Teklifi", "Randevu Talebi"])
        if sablon_turu == "Tanışma":
            mesaj = "Merhaba, [Firma] adına yazıyorum. Bölgenizdeki lojistik/servis ihtiyaçlarınız için firmanızla tanışmak isteriz. Müsaitliğinizde görüşmek dileğiyle."
        elif sablon_turu == "Fiyat Teklifi":
            mesaj = "Sayın Yetkili, talep ettiğiniz güzergah/hizmet için güncel fiyat çalışmamızı hazırladık. Detayları ne zaman konuşabiliriz?"
        else:
            mesaj = "Merhaba, hizmetlerimizle ilgili size kısa bir sunum yapmak için 10 dakikanızı rica ediyoruz. Haftaya hangi gün uygun olursunuz?"
        
        st.code(mesaj, language="text")
        st.caption("Kopyalamak için sağ üstteki ikona basın.")

# --- SAYFA 1: DASHBOARD & ANALİZ ---
if secim == "🏠 Dashboard & Analiz":
    st.title("📊 Yönetim Paneli")
    df = veri_tabanini_yukle()
    
    # Üst İstatistikler
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Firma", len(df), border=True)
    with col2:
        yeni = len(df[df["Durum"] == "Yeni"])
        st.metric("Aranacak (Yeni)", yeni, border=True)
    with col3:
        teklif = len(df[df["Durum"] == "⏳ Teklif Verildi"])
        st.metric("Teklif Aşamasında", teklif, border=True)
    with col4:
        anlasma = len(df[df["Durum"] == "✅ Anlaşıldı"])
        st.metric("Kazanılan Müşteri", anlasma, delta="Başarılı", border=True)

    st.markdown("---")
    
    # GRAFİKLER (YENİ)
    if not df.empty:
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("📈 Portföy Durum Dağılımı")
            durum_sayilari = df["Durum"].value_counts().reset_index()
            durum_sayilari.columns = ["Durum", "Adet"]
            fig1 = px.pie(durum_sayilari, values="Adet", names="Durum", hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
            
        with g2:
            st.subheader("🔔 Bugünün Ajandası")
            bugun = pd.Timestamp.now().normalize()
            if "Hatirlatici_Tarih" in df.columns:
                hatirlatmalar = df[
                    (df["Hatirlatici_Tarih"] <= bugun) & 
                    (df["Hatirlatici_Tarih"].notnull()) &
                    (df["Durum"] != "✅ Anlaşıldı")
                ]
                if not hatirlatmalar.empty:
                    st.error(f"Bugün ilgilenmen gereken {len(hatirlatmalar)} iş var!")
                    st.dataframe(
                        hatirlatmalar[["Firma", "Telefon", "Notlar"]],
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.success("Bugün için planlanmış acil bir işiniz yok. Sahaya çıkma zamanı! 🚗")
    else:
        st.info("Henüz veri yok. Arama menüsünden firma ekleyerek başlayın.")

# --- SAYFA 2: GELİŞMİŞ ARAMA ---
elif secim == "🗺️ Gelişmiş Arama":
    st.title("🗺️ Sektörel Firma Tarama")
    
    col1, col2 = st.columns([2, 2])
    with col1:
        sehir = st.text_input("📍 Şehir", "Gaziantep")
    with col2:
        # Gelişmiş Sektör Listesi
        secilen_etiket = st.selectbox("🎯 Aranacak Sektör/Firma Türü", list(SEKTORLER.keys()))
        arama_sorgusu = SEKTORLER[secilen_etiket] # Arka planda Google'a gidecek gerçek sorgu
    
    if st.button("🔍 Firmaları Bul", type="primary", use_container_width=True):
        st.info(f"📡 '{sehir}' bölgesinde '{arama_sorgusu}' aranıyor...")
        
        tum_firmalar = []
        next_page_token = None
        sayfa_sayisi = 0
        bar = st.progress(0)
        
        while sayfa_sayisi < 3: 
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            # Burada 'arama_sorgusu' kullanıyoruz
            params = {'query': f"{sehir} {arama_sorgusu}", 'key': API_KEY, 'language': 'tr'}
            if next_page_token:
                params['pagetoken'] = next_page_token
                time.sleep(2)
            
            try:
                resp = requests.get(url, params=params).json()
                results = resp.get('results', [])
                
                for firma in results:
                    ad = firma.get('name')
                    geo = firma.get('geometry', {}).get('location', {})
                    tel = detay_getir(firma.get('place_id'))
                    
                    tum_firmalar.append({
                        "Firma": ad,
                        "Telefon": tel,
                        "Adres": firma.get('formatted_address'),
                        "lat": geo.get('lat'),
                        "lon": geo.get('lng'),
                        "Durum": "Yeni", 
                        "Notlar": "",
                        "Tuketim_Bilgisi": ""
                    })
                    time.sleep(0.05)
                
                next_page_token = resp.get('next_page_token')
                sayfa_sayisi += 1
                bar.progress(sayfa_sayisi/3)
                if not next_page_token: break
            
            except Exception as e:
                st.error(f"Hata: {e}")
                break
        
        if tum_firmalar:
            df_temp = pd.DataFrame(tum_firmalar)
            df_temp.insert(0, "Seç", False)
            st.session_state['arama_sonuclari'] = df_temp
            st.success(f"✅ {len(tum_firmalar)} potansiyel müşteri bulundu.")
        else:
            st.error("Sonuç bulunamadı.")

    if 'arama_sonuclari' in st.session_state:
        df_sonuc = st.session_state['arama_sonuclari']
        
        st.write("### 📍 Konum Haritası")
        map_data = df_sonuc.dropna(subset=['lat', 'lon'])
        if not map_data.empty:
            st.map(map_data, latitude='lat', longitude='lon', size=20, color='#ff0000')
        
        st.write("### 📋 Sonuç Listesi")
        edited_df = st.data_editor(
            df_sonuc,
            column_config={
                "Seç": st.column_config.CheckboxColumn("Ekle?", default=False),
                "Firma": st.column_config.TextColumn("Firma", disabled=True),
                "Telefon": st.column_config.TextColumn("Telefon", disabled=True),
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("💾 SEÇİLENLERİ PORTFÖYE EKLE", type="primary"):
            secilenler = edited_df[edited_df["Seç"] == True].copy()
            if not secilenler.empty:
                kayit_icin = secilenler.drop(columns=["Seç", "lat", "lon"], errors='ignore')
                mevcut = veri_tabanini_yukle()
                yeni = pd.concat([mevcut, kayit_icin], ignore_index=True).drop_duplicates(subset=['Firma'])
                veriyi_kaydet(yeni)
                st.toast(f"{len(secilenler)} firma eklendi! Otomatik yedek alındı.", icon="✅")
                time.sleep(1)
            else:
                st.warning("Seçim yapın.")

# --- SAYFA 3: PORTFÖY ---
elif secim == "📂 Portföy & İşlemler":
    st.title("📂 Detaylı Müşteri Portföyü")
    
    df_crm = veri_tabanini_yukle()
    
    # Rapor İndirme Butonu (Buraya da koydum)
    csv = df_crm.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Excel Raporu İndir", csv, f"Saha_Raporu_{time.strftime('%d_%m')}.csv", "text/csv")
    
    if not df_crm.empty:
        if "Sil" not in df_crm.columns: df_crm.insert(0, "Sil", False)
        
        # Linkleri Oluştur
        df_crm["WhatsApp"] = df_crm["Telefon"].apply(whatsapp_linki_yap)
        df_crm["Ara"] = df_crm["Telefon"].apply(arama_linki_yap)
        df_crm["Yol_Tarifi"] = df_crm["Adres"].apply(harita_linki_yap)
        
        edited_crm = st.data_editor(
            df_crm,
            column_config={
                "Sil": st.column_config.CheckboxColumn("Sil", width="small"),
                "Firma": st.column_config.TextColumn("Firma Adı", disabled=True),
                
                # İKONLAR
                "Ara": st.column_config.LinkColumn("📞", display_text="Ara", width="small"),
                "WhatsApp": st.column_config.LinkColumn("💬", display_text="Mesaj", width="small"),
                "Yol_Tarifi": st.column_config.LinkColumn("🗺️", display_text="Git", width="small"),
                
                # VERİLER
                "Durum": st.column_config.SelectboxColumn("Durum", options=["Yeni", "📞 Arandı", "⏳ Teklif Verildi", "✅ Anlaşıldı", "❌ Olumsuz", "📅 Randevu"], width="medium"),
                "Tuketim_Bilgisi": st.column_config.TextColumn("Potansiyel (m3/Ton)", width="medium"),
                "Sozlesme_Tarihi": st.column_config.DateColumn("Sözleşme Tarihi", format="DD.MM.YYYY", width="medium"),
                "Hatirlatici_Tarih": st.column_config.DateColumn("🔔 Hatırlatıcı", format="DD.MM.YYYY", min_value=date.today(), width="medium"),
                "Notlar": st.column_config.TextColumn("Görüşme Notları", width="large"),
                
                "Telefon": None, "Adres": None # Gizle
            },
            hide_index=True,
            use_container_width=True
        )
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🗑️ SİL"):
                kalan = edited_crm[edited_crm["Sil"]==False].drop(columns=["Sil", "WhatsApp", "Ara", "Yol_Tarifi"])
                if len(edited_crm) > len(kalan):
                    veriyi_kaydet(kalan)
                    st.rerun()
        with c2:
            if st.button("💾 GÜNCELLE", type="primary"):
                kayit_df = edited_crm.drop(columns=["Sil", "WhatsApp", "Ara", "Yol_Tarifi"], errors='ignore')
                veriyi_kaydet(kayit_df)
                st.toast("Veriler güncellendi ve yedeklendi!", icon="💾")
                time.sleep(1)
                st.rerun()
    else:
        st.info("Listeniz boş.")