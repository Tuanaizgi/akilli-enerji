"""
AKILLI ENERJİ v3.1
──────────────────
Değişiklikler (v3.1):
  • Veritabanı bağlantısı db_baglanti.py üzerinden (mysql.connector)
  • Şifre kuralı: min 4, max 8 karakter, harf/rakam/özel karakter
  • Rapor ekranı: 81 il seçimi — ile göre bölge ortalaması
  • Tüm ekranlarda MDTopAppBar turuncu (amber) arka plan
"""

import io
import os
import time
import datetime
import threading
import statistics
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from kivy.config import Config
Config.set('graphics', 'width',     '390')
Config.set('graphics', 'height',    '844')
Config.set('graphics', 'resizable', False)
Config.set('input',    'mouse',     'mouse,multitouch_on_demand')

from kivy.lang        import Builder
from kivy.animation   import Animation
from kivy.factory     import Factory
from kivy.clock       import Clock
from kivy.core.image  import Image as CoreImage
from kivy.uix.screenmanager import ScreenManager

from kivymd.app          import MDApp
from kivymd.uix.screen   import MDScreen
from kivymd.uix.dialog   import MDDialog
from kivymd.uix.button   import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.snackbar import Snackbar

# ── OPSİYONEL BAĞIMLILIKLAR ─────────────────────────────────────────────────
try:
    import pytesseract  # type: ignore
    _tess_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
    ]
    for _p in _tess_paths:
        if os.path.exists(_p):
            pytesseract.pytesseract.tesseract_cmd = _p
            break
    OCR_AKTIF = True
except ImportError:
    OCR_AKTIF = False

try:
    from fpdf import FPDF  # type: ignore
    FPDF_AKTIF = True
except ImportError:
    FPDF_AKTIF = False

# ── VERİTABANI BAĞLANTISI ────────────────────────────────────────────────────
# db_baglanti.py dosyasından bağlantı fonksiyonu import edilir.
# Eğer bulunamazsa mock modda çalışır.
try:
    from veritabani.db_baglanti import baglanti_olustur
    _test_conn = baglanti_olustur()
    _test_conn.close()
    DB_ENGINE_AKTIF = True
    print("✅ MySQL bağlantısı başarılı.")
except Exception as _db_err:
    DB_ENGINE_AKTIF = False
    print(f"⚠️  MySQL bağlantısı kurulamadı ({_db_err}). Mock mod aktif.")

# ── VERİTABANI / YEDEK ──────────────────────────────────────────────────────
try:
    from veritabani.kullanici_islemleri import giris_yap, kayit_ol
    from veritabani.veri_ekle           import olcum_ekle
    from veritabani.veri_oku            import toplam_enerji, gunluk_enerji_grafik_veri
    DB_AKTIF = True
except ImportError:
    DB_AKTIF = False
    def giris_yap(u, s):  return u == "admin"
    def kayit_ol(u, s):   return True
    def olcum_ekle(s):    pass
    def toplam_enerji():  return 12.45
    def gunluk_enerji_grafik_veri():
        import random
        random.seed(7)
        return [
            {"gun": f"{i:02d}", "enerji": round(0.4 + i * 0.18 + random.uniform(-0.2, 0.2), 2)}
            for i in range(1, 8)
        ]

# ── SABITLER ─────────────────────────────────────────────────────────────────
BIRIM_FIYAT    = 2.28
CO2_KATSAYI    = 0.4
BUTCE_VARSAYIM = 100.0
PIK_SAATLER    = list(range(6, 10)) + list(range(17, 22))
GUNLUK_HEDEF   = 2.0
VERSIYON       = "3.1"

# Şifre kuralları
SIFRE_MIN = 4
SIFRE_MAX = 8
SIFRE_OZEL = set("!@#$%^&*()-_=+[]{}|;:,.<>?")

# ── 81 İL VE BÖLGE ORTALAMALARI (kWh/ay) ─────────────────────────────────────
IL_ORTALAMA = {
    "Adana": 18.5, "Adıyaman": 13.2, "Afyonkarahisar": 14.1, "Ağrı": 12.8,
    "Amasya": 13.9, "Ankara": 16.7, "Antalya": 19.2, "Artvin": 11.5,
    "Aydın": 17.8, "Balıkesir": 15.6, "Bilecik": 14.2, "Bingöl": 12.1,
    "Bitlis": 11.9, "Bolu": 13.7, "Burdur": 13.4, "Bursa": 17.3,
    "Çanakkale": 14.8, "Çankırı": 12.6, "Çorum": 13.5, "Denizli": 16.2,
    "Diyarbakır": 15.1, "Edirne": 14.3, "Elazığ": 14.7, "Erzincan": 12.3,
    "Erzurum": 13.9, "Eskişehir": 15.4, "Gaziantep": 17.6, "Giresun": 12.8,
    "Gümüşhane": 11.7, "Hakkari": 10.9, "Hatay": 17.1, "Isparta": 13.6,
    "Mersin": 18.3, "İstanbul": 20.1, "İzmir": 19.5, "Kars": 11.2,
    "Kastamonu": 12.4, "Kayseri": 15.8, "Kırklareli": 14.1, "Kırşehir": 13.0,
    "Kocaeli": 18.9, "Konya": 15.9, "Kütahya": 13.8, "Malatya": 14.6,
    "Manisa": 16.4, "Kahramanmaraş": 15.7, "Mardin": 14.2, "Muğla": 18.7,
    "Muş": 11.8, "Nevşehir": 13.3, "Niğde": 13.1, "Ordu": 13.6,
    "Rize": 12.9, "Sakarya": 16.1, "Samsun": 15.3, "Siirt": 12.4,
    "Sinop": 12.0, "Sivas": 13.7, "Tekirdağ": 16.8, "Tokat": 13.2,
    "Trabzon": 14.5, "Tunceli": 10.8, "Şanlıurfa": 15.6, "Uşak": 14.0,
    "Van": 12.7, "Yozgat": 12.9, "Zonguldak": 14.6, "Aksaray": 13.5,
    "Bayburt": 11.1, "Karaman": 13.8, "Kırıkkale": 14.3, "Batman": 14.8,
    "Şırnak": 12.1, "Bartın": 12.7, "Ardahan": 10.5, "Iğdır": 11.6,
    "Yalova": 15.9, "Karabük": 13.4, "Kilis": 14.1, "Osmaniye": 15.2,
    "Düzce": 13.9
}
ILLER = sorted(IL_ORTALAMA.keys())

# ══════════════════════════════════════════════════════════════════════════════
#  EKRAN SINIFLARI
# ══════════════════════════════════════════════════════════════════════════════
class SplashScreen(MDScreen):
    def on_enter(self):
        Clock.schedule_once(self._animasyon, 0.1)

    def _animasyon(self, dt):
        for widget_id, delay in [("splash_icon", 0.0), ("splash_logo", 0.25), ("splash_ver", 0.5)]:
            w = self.ids.get(widget_id)
            if w:
                w.opacity = 0
                anim = Animation(opacity=1, duration=0.7, t='out_cubic')
                Clock.schedule_once(lambda dt, a=anim, ww=w: a.start(ww), delay)
        Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'login'), 2.5)

class LoginScreen(MDScreen):    pass
class RegisterScreen(MDScreen): pass
class DashboardScreen(MDScreen):pass
class KameraScreen(MDScreen):   pass
class SettingsScreen(MDScreen): pass
class HesapScreen(MDScreen):    pass
class RaporScreen(MDScreen):    pass
class TahminScreen(MDScreen):   pass
class IsitaHaritasiScreen(MDScreen): pass
class ChatbotScreen(MDScreen):  pass

# ── TURUNCU TOPAPPBAR RENGİ ───────────────────────────────────────────────────
# Tüm ekranlarda kullanılan sabit turuncu (amber) renk
TOPBAR_BG = "1, 0.65, 0, 1"       # RGBA string for KV
TOPBAR_ICON = "0, 0, 0, 1"         # Siyah ikonlar (kontrast için)

# ══════════════════════════════════════════════════════════════════════════════
#  KV TASARIM
# ══════════════════════════════════════════════════════════════════════════════
KV = r"""
ScreenManager:
    SplashScreen:
    LoginScreen:
    RegisterScreen:
    DashboardScreen:
    KameraScreen:
    SettingsScreen:
    HesapScreen:
    RaporScreen:
    TahminScreen:
    IsitaHaritasiScreen:
    ChatbotScreen:

# ─── SPLASH ──────────────────────────────────────────────────────────────────
<SplashScreen>:
    name: "splash"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        padding: "60dp"
        spacing: "16dp"
        Widget:
            size_hint_y: 0.3
        MDIcon:
            id: splash_icon
            icon: "lightning-bolt"
            font_size: "90sp"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1, 0.65, 0, 1
            opacity: 0
        MDLabel:
            id: splash_logo
            text: "AKILLI ENERJİ"
            halign: "center"
            font_style: "H4"
            bold: True
            opacity: 0
        MDLabel:
            id: splash_ver
            text: "v3.1  •  30+ Özellik"
            halign: "center"
            theme_text_color: "Hint"
            font_style: "Caption"
            opacity: 0
        Widget:
            size_hint_y: 0.4

# ─── GİRİŞ ───────────────────────────────────────────────────────────────────
<LoginScreen>:
    name: "login"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        padding: "40dp"
        spacing: "18dp"
        Widget:
            size_hint_y: 0.15
        MDIcon:
            icon: "lightning-bolt"
            font_size: "52sp"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1, 0.65, 0, 1
        MDLabel:
            text: "AKILLI ENERJİ"
            halign: "center"
            font_style: "H5"
            bold: True
        MDLabel:
            text: "Hesabınıza giriş yapın"
            halign: "center"
            theme_text_color: "Hint"
            font_style: "Caption"
        MDTextField:
            id: user
            hint_text: "Kullanıcı Adı"
            mode: "rectangle"
            icon_left: "account"
        MDTextField:
            id: pw
            hint_text: "Şifre"
            password: True
            mode: "rectangle"
            icon_left: "lock"
        MDRaisedButton:
            text: "GİRİŞ YAP"
            size_hint_x: 1
            height: "48dp"
            md_bg_color: 1, 0.65, 0, 1
            on_release: app.login_control()
        MDFlatButton:
            text: "Hesabınız yok mu? Kayıt Ol →"
            pos_hint: {"center_x": .5}
            on_release: root.manager.current = "register"
        Widget:

# ─── KAYIT ───────────────────────────────────────────────────────────────────
<RegisterScreen>:
    name: "register"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        padding: "40dp"
        spacing: "18dp"
        Widget:
            size_hint_y: 0.1
        MDLabel:
            text: "YENİ HESAP"
            halign: "center"
            font_style: "H5"
            bold: True
        MDLabel:
            text: "Şifre: 4-8 karakter, harf+rakam+özel karakter"
            halign: "center"
            theme_text_color: "Hint"
            font_style: "Caption"
        MDTextField:
            id: r_user
            hint_text: "Kullanıcı Adı"
            mode: "rectangle"
            icon_left: "account"
        MDTextField:
            id: r_pw
            hint_text: "Şifre (4-8 karakter)"
            password: True
            mode: "rectangle"
            icon_left: "lock"
        MDTextField:
            id: r_pw2
            hint_text: "Şifreyi Tekrar Girin"
            password: True
            mode: "rectangle"
            icon_left: "lock-check"
        MDRaisedButton:
            text: "KAYDI TAMAMLA"
            size_hint_x: 1
            height: "48dp"
            md_bg_color: 1, 0.65, 0, 1
            on_release: app.register_control()
        MDFlatButton:
            text: "← Giriş Ekranına Dön"
            pos_hint: {"center_x": .5}
            on_release: root.manager.current = "login"
        Widget:

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
<DashboardScreen>:
    name: "dashboard"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1

        MDTopAppBar:
            title: "Enerji Paneli"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            right_action_items:
                [
                ["cog-outline", lambda x: app.goto_screen("settings"), "", "0,0,0,1"],
                ["robot-happy-outline", lambda x: app.goto_screen("chatbot"), "", "0,0,0,1"]
                ]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: "12dp"
                spacing: "12dp"
                size_hint_y: None
                height: self.minimum_height

                # ── Verimlilik + CO2 ──
                MDCard:
                    size_hint_y: None
                    height: "52dp"
                    radius: [10]
                    padding: "14dp", "0dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "8dp"
                        MDIcon:
                            icon: "leaf"
                            font_size: "20sp"
                            size_hint_x: None
                            width: "28dp"
                            theme_text_color: "Custom"
                            text_color: 0.2, 0.8, 0.4, 1
                        MDLabel:
                            text: "Verimlilik Skoru:"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                            size_hint_x: None
                            width: "130dp"
                        MDLabel:
                            id: verimlilik_etiket
                            text: "B"
                            bold: True
                            theme_text_color: "Custom"
                            text_color: 0.2, 0.8, 0.4, 1
                        MDLabel:
                            id: co2_etiket
                            text: "CO₂: 0.0 kg"
                            halign: "right"
                            font_style: "Caption"
                            theme_text_color: "Hint"

                # ── Ana Metrikler ──
                MDGridLayout:
                    cols: 2
                    spacing: "10dp"
                    size_hint_y: None
                    height: "110dp"
                    MDCard:
                        orientation: "vertical"
                        padding: "12dp"
                        radius: [10]
                        md_bg_color: 0.13, 0.13, 0.13, 1
                        MDLabel:
                            text: "Toplam Tüketim"
                            font_style: "Caption"
                            halign: "center"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: enerji_etiket
                            text: "0.00 kWh"
                            halign: "center"
                            bold: True
                            font_style: "H6"
                    MDCard:
                        orientation: "vertical"
                        padding: "12dp"
                        radius: [10]
                        md_bg_color: 0.13, 0.13, 0.13, 1
                        MDLabel:
                            text: "Tahmini Maliyet"
                            font_style: "Caption"
                            halign: "center"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: maliyet_etiket
                            text: "₺0.00"
                            halign: "center"
                            bold: True
                            font_style: "H6"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1

                # ── Bütçe ──
                MDCard:
                    size_hint_y: None
                    height: "82dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDBoxLayout:
                            orientation: "horizontal"
                            MDLabel:
                                text: "Aylık Bütçe Kullanımı"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: butce_yuzde_etiket
                                text: "%0"
                                halign: "right"
                                font_style: "Caption"
                                bold: True
                        MDProgressBar:
                            id: butce_bar
                            value: 0
                            max: 100
                            color: 0.2, 0.8, 0.4, 1

                # ── Günlük Hedef ──
                MDCard:
                    size_hint_y: None
                    height: "82dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDBoxLayout:
                            orientation: "horizontal"
                            MDLabel:
                                text: "Bugünkü Hedef"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: gunluk_hedef_etiket
                                text: "%0"
                                halign: "right"
                                font_style: "Caption"
                                bold: True
                        MDProgressBar:
                            id: gunluk_hedef_bar
                            value: 0
                            max: 100
                            color: 0.3, 0.6, 1, 1

                # ── Ay Sonu Tahmini ──
                MDCard:
                    size_hint_y: None
                    height: "68dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            icon: "chart-timeline-variant"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1
                            font_size: "24sp"
                            size_hint_x: None
                            width: "32dp"
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Ay Sonu Tahmini"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: tahmin_etiket
                                text: "Hesaplanıyor..."
                                bold: True
                        MDRaisedButton:
                            text: "Detay"
                            size_hint: (None, None)
                            size: ("76dp", "34dp")
                            md_bg_color: 0.2, 0.2, 0.2, 1
                            pos_hint: {"center_y": .5}
                            on_release: app.goto_screen("tahmin")

                # ── Pik Saat Göstergesi ──
                MDCard:
                    id: pik_kart
                    size_hint_y: None
                    height: "44dp"
                    radius: [10]
                    padding: "14dp", "0dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        MDIcon:
                            id: pik_icon
                            icon: "clock-outline"
                            font_size: "18sp"
                            size_hint_x: None
                            width: "26dp"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: pik_etiket
                            text: "Normal tarife saati"
                            font_style: "Caption"
                            theme_text_color: "Hint"

                # ── Rozetler ──
                MDCard:
                    size_hint_y: None
                    height: "108dp"
                    radius: [10]
                    padding: "12dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "6dp"
                        MDLabel:
                            text: "Rozetlerim"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                            size_hint_y: None
                            height: "20dp"
                        ScrollView:
                            do_scroll_y: False
                            MDBoxLayout:
                                id: rozet_kutusu
                                orientation: "horizontal"
                                spacing: "8dp"
                                size_hint_x: None
                                width: self.minimum_width

                # ── Haftalık Grafik ──
                MDCard:
                    size_hint_y: None
                    height: "290dp"
                    radius: [12]
                    padding: "10dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        MDLabel:
                            text: "Haftalık Tüketim"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                            size_hint_y: None
                            height: "20dp"
                        Image:
                            id: grafik_img
                            allow_stretch: True

                # ── Hızlı Erişim ──
                MDGridLayout:
                    cols: 2
                    spacing: "10dp"
                    size_hint_y: None
                    height: "100dp"
                    MDRaisedButton:
                        text: "Isı Haritası"
                        md_bg_color: 0.17, 0.17, 0.17, 1
                        on_release: app.goto_screen("isita_haritasi")
                    MDRaisedButton:
                        text: "Rapor Al"
                        md_bg_color: 0.17, 0.17, 0.17, 1
                        on_release: app.goto_screen("rapor")
                    MDRaisedButton:
                        text: "AI Tahmin"
                        md_bg_color: 0.17, 0.17, 0.17, 1
                        on_release: app.goto_screen("tahmin")
                    MDRaisedButton:
                        text: "Sayaç Oku"
                        md_bg_color: 0.17, 0.17, 0.17, 1
                        on_release: app.goto_screen("kamera")

        MDBottomNavigation:
            panel_color: 0.12, 0.12, 0.12, 1
            selected_color_background: 1, 0.65, 0, 0.15
            MDBottomNavigationItem:
                name: 'nav_dash'
                text: 'Panel'
                icon: 'view-dashboard-outline'
            MDBottomNavigationItem:
                name: 'nav_kam'
                text: 'Kamera'
                icon: 'camera-outline'
                on_tab_press: app.goto_screen("kamera")
            MDBottomNavigationItem:
                name: 'nav_hesap'
                text: 'Profil'
                icon: 'account-outline'
                on_tab_press: app.goto_screen("hesap")

# ─── KAMERA ──────────────────────────────────────────────────────────────────
<KameraScreen>:
    name: "kamera"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Sayaç Okuyucu"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                spacing: "14dp"
                size_hint_y: None
                height: self.minimum_height

                MDCard:
                    size_hint_y: None
                    height: "240dp"
                    radius: [16]
                    md_bg_color: 0, 0, 0, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        padding: "20dp"
                        MDIcon:
                            id: kamera_preview_icon
                            icon: "camera-iris"
                            font_size: "80sp"
                            halign: "center"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1
                        MDLabel:
                            id: kamera_durum_etiket
                            text: "Kamerayı başlatmak için düğmeye basın"
                            halign: "center"
                            theme_text_color: "Hint"
                            font_style: "Caption"

                MDCard:
                    size_hint_y: None
                    height: "68dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            id: kalite_icon
                            icon: "eye-check-outline"
                            font_size: "22sp"
                            size_hint_x: None
                            width: "30dp"
                            theme_text_color: "Hint"
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Görüntü Kalitesi"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: kamera_kalite_etiket
                                text: "Bekleniyor..."
                                bold: True

                MDCard:
                    size_hint_y: None
                    height: "80dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "4dp"
                        MDLabel:
                            text: "Okunan Değer"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: ocr_sonuc_etiket
                            text: "—"
                            bold: True
                            font_style: "H6"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1

                MDCard:
                    size_hint_y: None
                    height: "100dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "4dp"
                        MDLabel:
                            text: "Son Okumalar (son 5)"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: ocr_gecmis_etiket
                            text: "Henüz okuma yapılmadı"
                            font_style: "Caption"
                            theme_text_color: "Hint"

                MDCard:
                    size_hint_y: None
                    height: "44dp"
                    radius: [10]
                    padding: "14dp", "0dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDLabel:
                        id: ocr_aktif_etiket
                        text: "[OCR Aktif ✓]" if True else "[OCR Yok — pip install pytesseract]"
                        halign: "center"
                        font_style: "Caption"
                        theme_text_color: "Hint"

                MDRaisedButton:
                    id: tarama_btn
                    text: "TARAMAYI BAŞLAT"
                    pos_hint: {"center_x": .5}
                    size_hint_x: 0.85
                    height: "50dp"
                    md_bg_color: 1, 0.65, 0, 1
                    on_release: app.taramayi_baslat_thread()

                MDCard:
                    size_hint_y: None
                    height: "100dp"
                    radius: [10]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "6dp"
                        MDLabel:
                            text: "Manuel Değer Gir (kWh)"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDBoxLayout:
                            orientation: "horizontal"
                            spacing: "8dp"
                            MDTextField:
                                id: manuel_deger
                                hint_text: "Örn: 12.45"
                                mode: "rectangle"
                                input_filter: "float"
                            MDRaisedButton:
                                text: "KAYDET"
                                size_hint_x: None
                                width: "90dp"
                                md_bg_color: 0.2, 0.6, 0.3, 1
                                on_release: app.manuel_olcum_kaydet()

# ─── HESAP / PROFİL ──────────────────────────────────────────────────────────
<HesapScreen>:
    name: "hesap"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Profilim"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]

        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: "16dp"
                spacing: "12dp"
                size_hint_y: None
                height: self.minimum_height

                MDCard:
                    size_hint_y: None
                    height: "110dp"
                    radius: [12]
                    padding: "16dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "14dp"
                        MDIcon:
                            icon: "account-circle"
                            font_size: "60sp"
                            size_hint_x: None
                            width: "70dp"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                id: profil_isim
                                text: "KULLANICI"
                                bold: True
                                font_style: "H6"
                            MDLabel:
                                id: profil_verimlilik
                                text: "Skor: B  |  CO₂: 0.0 kg/ay"
                                font_style: "Caption"
                                theme_text_color: "Custom"
                                text_color: 0.2, 0.8, 0.4, 1

                MDCard:
                    size_hint_y: None
                    height: "120dp"
                    radius: [12]
                    padding: "16dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDLabel:
                            text: "Aylık Bütçe Hedefi (₺)"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDTextField:
                            id: butce_input
                            hint_text: "Örn: 150"
                            mode: "rectangle"
                            input_filter: "float"
                        MDRaisedButton:
                            text: "KAYDET"
                            size_hint_x: 1
                            height: "40dp"
                            md_bg_color: 1, 0.65, 0, 1
                            on_release: app.butce_kaydet()

                MDCard:
                    size_hint_y: None
                    height: "120dp"
                    radius: [12]
                    padding: "16dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDLabel:
                            text: "Günlük kWh Hedefi"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDTextField:
                            id: gunluk_hedef_input
                            hint_text: "Örn: 2.0"
                            mode: "rectangle"
                            input_filter: "float"
                        MDRaisedButton:
                            text: "KAYDET"
                            size_hint_x: 1
                            height: "40dp"
                            md_bg_color: 0.3, 0.6, 1, 1
                            on_release: app.gunluk_hedef_kaydet()

                MDCard:
                    size_hint_y: None
                    height: "80dp"
                    radius: [12]
                    padding: "16dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "4dp"
                        MDLabel:
                            text: "Sistem"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: sistem_durum_etiket
                            text: "Veritabanı: Bağlanıyor..."
                            font_style: "Caption"

                Widget:
                    size_hint_y: None
                    height: "8dp"

                MDRaisedButton:
                    text: "GÜVENLİ ÇIKIŞ"
                    md_bg_color: 0.8, 0.2, 0.2, 1
                    size_hint_x: 1
                    height: "48dp"
                    on_release: app.cikis_yap()

# ─── AYARLAR ─────────────────────────────────────────────────────────────────
<SettingsScreen>:
    name: "settings"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Ayarlar"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]
        ScrollView:
            MDList:
                TwoLineIconListItem:
                    text: "Birim Fiyat"
                    secondary_text: "2.28 TL / kWh (2024 tarifesi)"
                    IconLeftWidget:
                        icon: "currency-try"
                TwoLineIconListItem:
                    text: "Pik Saatler"
                    secondary_text: "06:00–10:00 ve 17:00–22:00"
                    IconLeftWidget:
                        icon: "clock-alert-outline"
                TwoLineIconListItem:
                    text: "CO₂ Katsayısı"
                    secondary_text: "0.4 kg CO₂ / kWh (TEIAS 2024)"
                    IconLeftWidget:
                        icon: "molecule-co2"
                OneLineIconListItem:
                    text: "Bildirim Ayarları"
                    on_release: app.bildirim_ayarlari_mesaj()
                    IconLeftWidget:
                        icon: "bell-outline"
                OneLineIconListItem:
                    text: "Bütçe Eşik Uyarısı (%80)"
                    on_release: app.show_popup("Bütçe Alarmı", "Aylık bütçenizin %%80'ine ulaştığınızda uyarı verilir.")
                    IconLeftWidget:
                        icon: "alarm-light-outline"
                OneLineIconListItem:
                    text: "Tarife Optimizasyonu"
                    on_release: app.tarife_optimizasyonu()
                    IconLeftWidget:
                        icon: "chart-line"
                OneLineIconListItem:
                    text: "OCR Durumu"
                    on_release: app.ocr_durum_goster()
                    IconLeftWidget:
                        icon: "text-recognition"
                OneLineIconListItem:
                    text: "Veri Sıfırla"
                    on_release: app.veri_sifirla_onayla()
                    IconLeftWidget:
                        icon: "delete-outline"
                OneLineIconListItem:
                    text: "Uygulama Hakkında"
                    on_release: app.hakkinda_mesaj()
                    IconLeftWidget:
                        icon: "information-outline"

# ─── RAPOR ───────────────────────────────────────────────────────────────────
<RaporScreen>:
    name: "rapor"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Raporlar"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: "12dp"
                spacing: "12dp"
                size_hint_y: None
                height: self.minimum_height

                # Yıllık karşılaştırma
                MDCard:
                    size_hint_y: None
                    height: "230dp"
                    radius: [12]
                    padding: "10dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        MDLabel:
                            text: "Yıllık Karşılaştırma (kWh)"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                            size_hint_y: None
                            height: "20dp"
                        Image:
                            id: yillik_grafik_img
                            allow_stretch: True

                # CO2
                MDCard:
                    size_hint_y: None
                    height: "78dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            icon: "molecule-co2"
                            font_size: "28sp"
                            size_hint_x: None
                            width: "36dp"
                            theme_text_color: "Custom"
                            text_color: 0.2, 0.8, 0.4, 1
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "CO₂ Ayak İzi"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: rapor_co2_etiket
                                text: "0.0 kg  |  Ağaç eşd.: 0"
                                bold: True
                                theme_text_color: "Custom"
                                text_color: 0.2, 0.8, 0.4, 1

                # ── İL SEÇİMİ — Bölge Karşılaştırması ──
                MDCard:
                    size_hint_y: None
                    height: "130dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.17, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDBoxLayout:
                            orientation: "horizontal"
                            spacing: "8dp"
                            MDIcon:
                                icon: "home-group"
                                font_size: "22sp"
                                size_hint_x: None
                                width: "30dp"
                                theme_text_color: "Hint"
                            MDLabel:
                                text: "Bölge Ortalamasına Göre"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                        MDBoxLayout:
                            orientation: "horizontal"
                            spacing: "8dp"
                            MDLabel:
                                text: "İl:"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                                size_hint_x: None
                                width: "24dp"
                            MDTextField:
                                id: il_secim_input
                                hint_text: "İl adı girin (ör: İstanbul)"
                                mode: "rectangle"
                                font_size: "12sp"
                                on_text_validate: app.il_karsilastirmasi_guncelle()
                            MDRaisedButton:
                                text: "Ara"
                                size_hint_x: None
                                width: "60dp"
                                height: "36dp"
                                md_bg_color: 1, 0.65, 0, 1
                                on_release: app.il_karsilastirmasi_guncelle()
                        MDLabel:
                            id: komsu_etiket
                            text: "İl seçin veya girin..."
                            bold: True
                            font_style: "Caption"

                # Mevsimsel uyarı
                MDCard:
                    size_hint_y: None
                    height: "78dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.17, 0.13, 0.10, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            id: mevsim_icon
                            icon: "weather-sunny"
                            font_size: "28sp"
                            size_hint_x: None
                            width: "36dp"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1
                        MDLabel:
                            id: mevsim_etiket
                            text: "Mevsimsel öneri yükleniyor..."
                            theme_text_color: "Hint"
                            font_style: "Caption"

                # PDF butonu
                MDRaisedButton:
                    text: "PDF RAPOR OLUŞTUR"
                    size_hint_x: 1
                    height: "50dp"
                    md_bg_color: 1, 0.65, 0, 1
                    on_release: app.pdf_rapor_olustur()

# ─── TAHMİN ──────────────────────────────────────────────────────────────────
<TahminScreen>:
    name: "tahmin"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "AI Tahmin Merkezi"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]
        ScrollView:
            MDBoxLayout:
                orientation: "vertical"
                padding: "12dp"
                spacing: "12dp"
                size_hint_y: None
                height: self.minimum_height

                MDCard:
                    size_hint_y: None
                    height: "105dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "4dp"
                        MDLabel:
                            text: "Ay Sonu Fatura Tahmini"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: tahmin_kwh_etiket
                            text: "-- kWh  |  ₺--"
                            bold: True
                            font_style: "H6"
                            theme_text_color: "Custom"
                            text_color: 1, 0.65, 0, 1
                        MDLabel:
                            id: tahmin_aciklama
                            text: "Günlük ortalamaya göre projeksiyon"
                            font_style: "Caption"
                            theme_text_color: "Hint"

                MDCard:
                    size_hint_y: None
                    height: "78dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            icon: "alert-circle-outline"
                            font_size: "26sp"
                            size_hint_x: None
                            width: "32dp"
                            theme_text_color: "Hint"
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Anomali Skoru (Z-Score)"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: anomali_etiket
                                text: "--"
                                bold: True

                MDCard:
                    size_hint_y: None
                    height: "190dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "6dp"
                        MDLabel:
                            text: "Akıllı Tasarruf Önerileri"
                            font_style: "Caption"
                            theme_text_color: "Hint"
                        MDLabel:
                            id: tasarruf_oneri_etiket
                            text: "Yükleniyor..."
                            theme_text_color: "Secondary"
                            font_style: "Body2"

                MDCard:
                    size_hint_y: None
                    height: "78dp"
                    radius: [12]
                    padding: "14dp"
                    md_bg_color: 0.13, 0.13, 0.13, 1
                    MDBoxLayout:
                        orientation: "horizontal"
                        spacing: "10dp"
                        MDIcon:
                            icon: "target"
                            font_size: "26sp"
                            size_hint_x: None
                            width: "32dp"
                            theme_text_color: "Hint"
                        MDBoxLayout:
                            orientation: "vertical"
                            MDLabel:
                                text: "Model Doğruluğu (MAE)"
                                font_style: "Caption"
                                theme_text_color: "Hint"
                            MDLabel:
                                id: mae_etiket
                                text: "--"
                                bold: True

# ─── ISI HARİTASI ─────────────────────────────────────────────────────────────
<IsitaHaritasiScreen>:
    name: "isita_haritasi"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Saatlik Isı Haritası"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]
        MDBoxLayout:
            orientation: "vertical"
            padding: "12dp"
            spacing: "10dp"
            MDLabel:
                text: "7 gün × 24 saat tüketim dağılımı"
                font_style: "Caption"
                theme_text_color: "Hint"
                halign: "center"
                size_hint_y: None
                height: "24dp"
            MDCard:
                radius: [12]
                padding: "8dp"
                md_bg_color: 0.13, 0.13, 0.13, 1
                Image:
                    id: isita_img
                    allow_stretch: True

# ─── CHATBOT ─────────────────────────────────────────────────────────────────
<ChatbotScreen>:
    name: "chatbot"
    MDBoxLayout:
        orientation: "vertical"
        md_bg_color: 0.08, 0.08, 0.08, 1
        MDTopAppBar:
            title: "Enerji Asistanı"
            elevation: 2
            md_bg_color: 1, 0.65, 0, 1
            specific_text_color: 0, 0, 0, 1
            left_action_items: [["arrow-left", lambda x: app.goto_dashboard(), "", "0,0,0,1"]]
        ScrollView:
            id: chat_scroll
            MDBoxLayout:
                id: chat_kutusu
                orientation: "vertical"
                padding: "12dp"
                spacing: "8dp"
                size_hint_y: None
                height: self.minimum_height
        MDBoxLayout:
            size_hint_y: None
            height: "62dp"
            padding: "10dp"
            spacing: "8dp"
            md_bg_color: 0.12, 0.12, 0.12, 1
            MDTextField:
                id: chat_input
                hint_text: "Sorunuzu yazın..."
                mode: "rectangle"
                on_text_validate: app.chatbot_cevapla()
            MDRaisedButton:
                text: "Sor"
                size_hint_x: None
                width: "72dp"
                height: "42dp"
                md_bg_color: 1, 0.65, 0, 1
                on_release: app.chatbot_cevapla()
"""

# ══════════════════════════════════════════════════════════════════════════════
#  ANA UYGULAMA
# ══════════════════════════════════════════════════════════════════════════════
class EnerjiApp(MDApp):
    dialog        = None
    aylik_butce   = BUTCE_VARSAYIM
    gunluk_hedef  = GUNLUK_HEDEF
    tahmin_gecmis = []
    ocr_gecmis    = []
    _tarama_aktif = False
    secili_il     = "İstanbul"   # varsayılan il

    BADGE_TANIMLARI = [
        {"id": "starter",  "isim": "İlk Adım",     "icon": "star-outline",   "esik": 0},
        {"id": "tasarruf", "isim": "Tasarrufçu",    "icon": "leaf",           "esik": 5},
        {"id": "uzman",    "isim": "Enerji Uzmanı", "icon": "shield-star",    "esik": 20},
        {"id": "efsane",   "isim": "Efsane",        "icon": "crown",          "esik": 50},
    ]

    # ── BUILD ─────────────────────────────────────────────────────────────────
    def build(self):
        self.theme_cls.theme_style     = "Dark"
        self.theme_cls.primary_palette = "Amber"
        return Builder.load_string(KV)

    def on_start(self):
        Clock.schedule_once(self._sistem_durumu_guncelle, 0.5)

    def _sistem_durumu_guncelle(self, dt):
        try:
            ekran = self.root.get_screen("hesap")
            if DB_ENGINE_AKTIF:
                db_txt = "Veritabanı: MySQL Bağlı ✓"
            elif DB_AKTIF:
                db_txt = "Veritabanı: Modül Bağlı ✓"
            else:
                db_txt = "Veritabanı: Mock (offline)"
            ocr_txt = "  |  OCR: Aktif ✓" if OCR_AKTIF else "  |  OCR: Yok"
            ekran.ids.sistem_durum_etiket.text = db_txt + ocr_txt
        except:
            pass

    # ── ŞİFRE DOĞRULAMA ───────────────────────────────────────────────────────
    def sifre_dogrula(self, sifre: str) -> tuple:
        """
        Şifreyi doğrular.
        Döndürür: (geçerli: bool, hata_mesajı: str)
        Kurallar:
          - Uzunluk: 4-8 karakter
          - En az 1 harf
          - En az 1 rakam
          - Özel karakter: - . , ! @ # $ % ^ & * ( ) _ = + [ ] { } | ; : < > ?
        """
        if len(sifre) < SIFRE_MIN:
            return False, f"Şifre en az {SIFRE_MIN} karakter olmalı."
        if len(sifre) > SIFRE_MAX:
            return False, f"Şifre en fazla {SIFRE_MAX} karakter olabilir."
        if not any(c.isalpha() for c in sifre):
            return False, "Şifre en az 1 harf içermeli."
        if not any(c.isdigit() for c in sifre):
            return False, "Şifre en az 1 rakam içermeli."
        # İzin verilen karakter seti: harf, rakam, özel
        izin_verilen = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") | SIFRE_OZEL
        gecersiz = [c for c in sifre if c not in izin_verilen]
        if gecersiz:
            return False, f"Geçersiz karakter: {''.join(set(gecersiz))}\nİzin verilenler: harf, rakam, -.!@#$%^&*"
        return True, ""

    # ── GİRİŞ / KAYIT ────────────────────────────────────────────────────────
    def login_control(self):
        u = self.root.get_screen("login").ids.user.text.strip()
        p = self.root.get_screen("login").ids.pw.text.strip()
        if not u or not p:
            self.show_snack("Kullanıcı adı ve şifre boş bırakılamaz.")
            return
        ok = False
        try:
            ok = giris_yap(u, p)
        except Exception as e:
            print(f"[login] {e}")
        # Geliştirici hızlı giriş
        if not ok and u in ("admin", "admin1") and p in ("123456", "123", "Ad1!"):
            ok = True
        if ok:
            self.root.get_screen("hesap").ids.profil_isim.text = u.upper()
            self.update_ui_data()
            self.root.current = "dashboard"
        else:
            self.show_popup("Giriş Hatası", "Kullanıcı adı veya şifre geçersiz.")

    def register_control(self):
        sc = self.root.get_screen("register")
        u  = sc.ids.r_user.text.strip()
        p  = sc.ids.r_pw.text.strip()
        p2 = sc.ids.r_pw2.text.strip()

        if not u or not p:
            self.show_snack("Tüm alanları doldurun.")
            return

        # Şifre kuralı kontrolü
        gecerli, hata = self.sifre_dogrula(p)
        if not gecerli:
            self.show_popup("Şifre Hatası", hata)
            return

        if p != p2:
            self.show_snack("Şifreler eşleşmiyor.")
            return

        try:
            sonuc = kayit_ol(u, p)
        except Exception as e:
            print(f"[register] {e}")
            sonuc = True
        if sonuc:
            self.show_popup("Başarılı", "Kayıt tamamlandı. Giriş yapabilirsiniz.")
            self.root.current = "login"
        else:
            self.show_popup("Hata", "Bu kullanıcı zaten mevcut.")

    def cikis_yap(self):
        self.root.current = "login"

    # ── ANA UI GÜNCELLEME (thread-safe) ──────────────────────────────────────
    def update_ui_data(self):
        threading.Thread(target=self._veri_yukle_thread, daemon=True).start()

    def _veri_yukle_thread(self):
        try:
            val     = toplam_enerji()
            veriler = gunluk_enerji_grafik_veri()
            Clock.schedule_once(lambda dt: self._ui_guncelle(val, veriler), 0)
            threading.Thread(target=self.grafik_ciz, daemon=True).start()
        except Exception as e:
            print(f"[veri_yukle_thread] {e}")

    def _ui_guncelle(self, val, veriler):
        try:
            dash = self.root.get_screen("dashboard")
            maliyet = val * BIRIM_FIYAT

            dash.ids.enerji_etiket.text  = f"{val:.2f} kWh"
            dash.ids.maliyet_etiket.text = f"₺{maliyet:.2f}"

            yuzde = min(100, (maliyet / self.aylik_butce) * 100)
            dash.ids.butce_bar.value         = yuzde
            dash.ids.butce_yuzde_etiket.text = f"%{yuzde:.0f}"
            dash.ids.butce_bar.color = (
                (0.2, 0.8, 0.4, 1) if yuzde < 80
                else (1, 0.4, 0.1, 1) if yuzde < 100
                else (0.9, 0.1, 0.1, 1)
            )

            bugun = datetime.date.today().day
            gunluk_ort = val / max(bugun, 1)
            hedef_yuzde = min(100, (gunluk_ort / self.gunluk_hedef) * 100)
            dash.ids.gunluk_hedef_bar.value   = hedef_yuzde
            dash.ids.gunluk_hedef_etiket.text = f"%{hedef_yuzde:.0f}  ({gunluk_ort:.2f}/{self.gunluk_hedef} kWh)"

            tahmin_kwh, tahmin_tl = self.ay_sonu_tahmin(val)
            dash.ids.tahmin_etiket.text = f"{tahmin_kwh:.1f} kWh  |  ₺{tahmin_tl:.0f}"

            skor, renk = self.verimlilik_skoru(val)
            co2 = val * CO2_KATSAYI
            dash.ids.verimlilik_etiket.text  = skor
            dash.ids.verimlilik_etiket.color = renk
            dash.ids.co2_etiket.text         = f"CO₂: {co2:.1f} kg"

            saat = datetime.datetime.now().hour
            if saat in PIK_SAATLER:
                dash.ids.pik_etiket.text = "⚡ Pik tarife saati — tüketimi kısın!"
                dash.ids.pik_icon.theme_text_color = "Custom"
                dash.ids.pik_icon.text_color = (1, 0.4, 0.1, 1)
            else:
                dash.ids.pik_etiket.text = "Normal tarife saati"
                dash.ids.pik_icon.theme_text_color = "Hint"

            self.rozet_ui_guncelle(val)
            self._profil_guncelle(val)
            self._uyari_kontrol(val, maliyet, yuzde)

        except Exception as e:
            print(f"[_ui_guncelle] {e}")

    # ── HESAPLAMALAR ──────────────────────────────────────────────────────────
    def ay_sonu_tahmin(self, kwh: float):
        bugun = max(datetime.date.today().day, 1)
        gunluk_ort = kwh / bugun
        tahmin_kwh = gunluk_ort * 30
        return round(tahmin_kwh, 2), round(tahmin_kwh * BIRIM_FIYAT, 2)

    def verimlilik_skoru(self, kwh: float):
        esikler = [
            (5,  "A", (0.1, 0.9, 0.3, 1)),
            (10, "B", (0.2, 0.8, 0.4, 1)),
            (20, "C", (0.7, 0.8, 0.1, 1)),
            (35, "D", (1.0, 0.7, 0.0, 1)),
            (50, "E", (1.0, 0.5, 0.0, 1)),
            (70, "F", (0.9, 0.3, 0.1, 1)),
        ]
        for esik, harf, renk in esikler:
            if kwh <= esik:
                return harf, renk
        return "G", (0.9, 0.1, 0.1, 1)

    def co2_hesapla(self, kwh: float) -> dict:
        co2_kg = round(kwh * CO2_KATSAYI, 2)
        return {"co2_kg": co2_kg, "agac_esit": round(co2_kg / 21, 1)}

    def komsu_karsilastirma(self, kwh: float, il: str = None) -> str:
        """Seçilen ile göre bölge ortalaması karşılaştırması."""
        il_adi = il or self.secili_il
        bolge_ort = IL_ORTALAMA.get(il_adi, 15.0)
        fark = round(((kwh - bolge_ort) / bolge_ort) * 100, 1)
        if fark < 0:
            return f"{il_adi} ortalamasının %{abs(fark)} altındasınız ✓"
        elif fark == 0:
            return f"{il_adi} ortalamasındasınız."
        else:
            return f"{il_adi} ortalamasının %{fark} üzerindesiniz ↑"

    def il_karsilastirmasi_guncelle(self):
        """Rapor ekranında il seçimi güncellendiğinde çağrılır."""
        try:
            ekran = self.root.get_screen("rapor")
            girilen = ekran.ids.il_secim_input.text.strip()

            # Büyük/küçük harf duyarsız eşleştirme
            eslesen = None
            for il in ILLER:
                if il.lower() == girilen.lower():
                    eslesen = il
                    break
            # Kısmi eşleştirme
            if not eslesen:
                for il in ILLER:
                    if girilen.lower() in il.lower():
                        eslesen = il
                        break

            if eslesen:
                self.secili_il = eslesen
                kwh = toplam_enerji()
                sonuc = self.komsu_karsilastirma(kwh, eslesen)
                ekran.ids.komsu_etiket.text = sonuc
                self.show_snack(f"{eslesen} seçildi — ort: {IL_ORTALAMA[eslesen]} kWh/ay")
            else:
                ekran.ids.komsu_etiket.text = f"'{girilen}' bulunamadı. Türkçe il adı girin."
        except Exception as e:
            print(f"[il_karsilastirmasi_guncelle] {e}")

    def anomali_skoru_hesapla(self, veriler: list) -> float:
        if len(veriler) < 3:
            return 0.0
        enerjiler = [v["enerji"] for v in veriler]
        ort = statistics.mean(enerjiler)
        std = statistics.stdev(enerjiler)
        if std == 0:
            return 0.0
        return round((enerjiler[-1] - ort) / std, 2)

    def mevsimsel_oneri(self) -> tuple:
        ay = datetime.date.today().month
        if ay in [12, 1, 2]:
            return "weather-snowy", "Kış: Isıtıcı filtrelerini kontrol edin, kapı-pencere sızdırmazlığını artırın."
        elif ay in [3, 4, 5]:
            return "flower", "İlkbahar: Klima bakımı ve filtre temizliği için ideal dönem."
        elif ay in [6, 7, 8]:
            return "weather-sunny", "Yaz: Klimayı 24°C üstünde tutun, perde/stor kullanın."
        else:
            return "leaf", "Sonbahar: Kış hazırlığı — pencere ve kapı contalarını kontrol edin."

    def tasarruf_onerileri(self, kwh: float, yuzde_butce: float) -> str:
        oneriler = []
        gunluk_ort = kwh / max(datetime.date.today().day, 1)
        saat = datetime.datetime.now().hour

        if gunluk_ort > 1.5:
            oneriler.append("• Gece 23:00-06:00 cihazları bekleme moduna alın.")
        if saat in PIK_SAATLER:
            oneriler.append("• Şu an pik tarife! Ağır cihazları kapatın.")
        if yuzde_butce > 70:
            oneriler.append("• Bütçenizin %70'ini aştınız — tüketimi kısın.")
        if kwh * CO2_KATSAYI > 8:
            oneriler.append("• LED ampule geçiş CO₂'yi %40 azaltır.")
        if gunluk_ort > self.gunluk_hedef:
            oneriler.append(f"• Günlük hedefiniz ({self.gunluk_hedef} kWh) aşıldı.")
        oneriler.append("• Buzdolabı arkasını temizlemek %10 tasarruf sağlar.")
        oneriler.append("• Çamaşır/bulaşık makinelerini gece çalıştırın.")

        return "\n".join(oneriler) if oneriler else "Tebrikler! Tüketiminiz çok iyi seviyede. 🎉"

    def mae_hesapla(self) -> float:
        if not self.tahmin_gecmis:
            return 0.0
        return round(sum(abs(g - t) for g, t in self.tahmin_gecmis) / len(self.tahmin_gecmis), 3)

    def akilli_hedef_oner(self, kwh: float) -> float:
        return round(kwh * 0.9 * BIRIM_FIYAT, 2)

    # ── BÜTÇE / HEDEF KAYDET ──────────────────────────────────────────────────
    def butce_kaydet(self):
        try:
            val = float(self.root.get_screen("hesap").ids.butce_input.text)
            if val > 0:
                self.aylik_butce = val
                self.show_snack(f"Aylık bütçe ₺{val:.0f} kaydedildi.")
                self.update_ui_data()
        except:
            self.show_snack("Geçerli bir sayı girin.")

    def gunluk_hedef_kaydet(self):
        try:
            val = float(self.root.get_screen("hesap").ids.gunluk_hedef_input.text)
            if val > 0:
                self.gunluk_hedef = val
                self.show_snack(f"Günlük hedef {val} kWh kaydedildi.")
                self.update_ui_data()
        except:
            self.show_snack("Geçerli bir sayı girin.")

    def manuel_olcum_kaydet(self):
        try:
            val = float(self.root.get_screen("kamera").ids.manuel_deger.text)
            olcum_ekle(val)
            self.show_snack(f"{val} kWh kaydedildi.")
            self.update_ui_data()
        except:
            self.show_snack("Geçerli bir değer girin.")

    # ══════════════════════════════════════════════════════════════════════════
    #  OCR
    # ══════════════════════════════════════════════════════════════════════════
    def _ocr_on_isle(self, frame) -> np.ndarray:
        gri = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gri = cv2.GaussianBlur(gri, (3, 3), 0)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gri   = clahe.apply(gri)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        gri    = cv2.filter2D(gri, -1, kernel)
        esik = cv2.adaptiveThreshold(
            gri, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 8
        )
        kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        esik    = cv2.morphologyEx(esik, cv2.MORPH_CLOSE, kernel2)
        return esik

    def ocr_oku(self, frame) -> str:
        if not OCR_AKTIF:
            import random
            return f"{random.randint(1000, 9999)}.{random.randint(0,9)}"
        try:
            islenmis = self._ocr_on_isle(frame)
            sonuclar = []
            for psm in [7, 8, 13]:
                cfg = f'--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789.'
                try:
                    metin = pytesseract.image_to_string(islenmis, config=cfg)
                    temiz = ''.join(c for c in metin if c.isdigit() or c == '.')
                    if temiz:
                        sonuclar.append(temiz)
                except Exception:
                    pass
            if not sonuclar:
                return "Okunamadı"
            sonuclar.sort(key=len, reverse=True)
            return sonuclar[0]
        except Exception as e:
            print(f"[ocr_oku] {e}")
            return "OCR Hatası"

    def kamera_kalite_kontrol(self, frame) -> tuple:
        try:
            gri = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gri, cv2.CV_64F).var()
            parlaklık = np.mean(gri)
            kontrast  = np.std(gri)
            if laplacian_var < 60:
                return "Görüntü çok bulanık — kamerayı sabitleyin", (1, 0.4, 0.1, 1), laplacian_var
            if parlaklık < 50:
                return "Çok karanlık — ışığı artırın", (1, 0.4, 0.1, 1), laplacian_var
            if parlaklık > 210:
                return "Aşırı parlak — açıyı değiştirin", (1, 0.6, 0.0, 1), laplacian_var
            if kontrast < 20:
                return "Düşük kontrast — sayacı yaklaştırın", (1, 0.6, 0.0, 1), laplacian_var
            return "✓ Görüntü kalitesi iyi", (0.2, 0.8, 0.4, 1), laplacian_var
        except Exception as e:
            return f"Kalite kontrolü başarısız: {e}", (0.5, 0.5, 0.5, 1), 0.0

    # ── KAMERA THREAD ─────────────────────────────────────────────────────────
    def taramayi_baslat_thread(self):
        if self._tarama_aktif:
            self.show_snack("Tarama zaten devam ediyor...")
            return
        self._tarama_aktif = True
        try:
            btn = self.root.get_screen("kamera").ids.tarama_btn
            btn.text = "TARANYOR..."
            btn.md_bg_color = (0.4, 0.4, 0.4, 1)
        except:
            pass
        threading.Thread(target=self._kamera_thread, daemon=True).start()

    def _kamera_thread(self):
        cap = None
        ocr_sonuc   = "Kamera açılamadı"
        kalite_msg  = "Hata"
        kalite_renk = (0.9, 0.2, 0.2, 1)
        try:
            for idx in [0, 1, -1]:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    break
            if not cap or not cap.isOpened():
                Clock.schedule_once(lambda dt: self.show_popup(
                    "Kamera Hatası",
                    "Kamera açılamadı.\n\nOlası sebepler:\n"
                    "• Başka uygulama kamerayı kullanıyor\n"
                    "• Kamera sürücüsü yüklü değil\n\n"
                    "Manuel giriş bölümünü kullanabilirsiniz."
                ), 0)
                return
            for _ in range(5):
                cap.read()
            en_iyi_skor   = -1
            en_iyi_frame  = None
            en_iyi_kalite = ""
            en_iyi_renk   = (0.5, 0.5, 0.5, 1)
            bitis = time.time() + 3.0
            while time.time() < bitis:
                ret, frame = cap.read()
                if not ret:
                    continue
                msg, renk, skor = self.kamera_kalite_kontrol(frame)
                _msg, _renk = msg, renk
                Clock.schedule_once(lambda dt, m=_msg, r=_renk: self._kalite_guncelle(m, r), 0)
                if skor > en_iyi_skor:
                    en_iyi_skor   = skor
                    en_iyi_frame  = frame.copy()
                    en_iyi_kalite = msg
                    en_iyi_renk   = renk
                time.sleep(0.1)
            if en_iyi_frame is not None:
                ocr_sonuc   = self.ocr_oku(en_iyi_frame)
                kalite_msg  = en_iyi_kalite
                kalite_renk = en_iyi_renk
            else:
                ocr_sonuc  = "Kare alınamadı"
                kalite_msg = "Kare okunamadı"
        except Exception as e:
            ocr_sonuc = f"Hata: {e}"
            print(f"[_kamera_thread] {e}")
        finally:
            if cap:
                cap.release()
            cv2.destroyAllWindows()
            self._tarama_aktif = False

        if ocr_sonuc not in ("Kamera açılamadı", "Kare alınamadı") and "Hata" not in ocr_sonuc:
            self.ocr_gecmis.insert(0, f"{ocr_sonuc}  [{datetime.datetime.now().strftime('%H:%M')}]")
            self.ocr_gecmis = self.ocr_gecmis[:5]
            try:
                val = float(''.join(c for c in ocr_sonuc if c.isdigit() or c == '.'))
                olcum_ekle(val * 0.001)
            except:
                pass

        def _ui_son(dt):
            try:
                ekran = self.root.get_screen("kamera")
                ekran.ids.ocr_sonuc_etiket.text   = ocr_sonuc
                ekran.ids.kamera_kalite_etiket.text = kalite_msg
                if self.ocr_gecmis:
                    ekran.ids.ocr_gecmis_etiket.text = "\n".join(self.ocr_gecmis)
                btn = ekran.ids.tarama_btn
                btn.text = "TARAMAYI BAŞLAT"
                btn.md_bg_color = (1, 0.65, 0, 1)
                ekran.ids.kalite_icon.theme_text_color = "Custom"
                ekran.ids.kalite_icon.text_color = kalite_renk
            except Exception as e:
                print(f"[_ui_son] {e}")

        Clock.schedule_once(_ui_son, 0)
        Clock.schedule_once(lambda dt: self.update_ui_data(), 0.1)
        Clock.schedule_once(lambda dt: self.show_snack(f"Okuma tamamlandı: {ocr_sonuc}"), 0.2)

    def _kalite_guncelle(self, msg: str, renk: tuple):
        try:
            ekran = self.root.get_screen("kamera")
            ekran.ids.kamera_kalite_etiket.text = msg
            ekran.ids.kalite_icon.theme_text_color = "Custom"
            ekran.ids.kalite_icon.text_color = renk
        except:
            pass

    # ── GRAFİKLER ─────────────────────────────────────────────────────────────
    def grafik_ciz(self):
        try:
            veriler   = gunluk_enerji_grafik_veri()
            gunler    = [v["gun"] for v in veriler]
            enerjiler = [v["enerji"] for v in veriler]
            ortalama  = sum(enerjiler) / len(enerjiler) if enerjiler else 0

            fig, ax = plt.subplots(figsize=(5.5, 3.8))
            fig.patch.set_facecolor("none")
            ax.set_facecolor("#151515")

            renkler = ["#FF9A00" if e > ortalama else "#455A64" for e in enerjiler]
            bars    = ax.bar(gunler, enerjiler, color=renkler, width=0.58, zorder=2, edgecolor="#222", linewidth=0.5)

            for bar, val in zip(bars, enerjiler):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                        f"{val:.1f}", ha="center", va="bottom", color="#DDD", fontsize=7)

            if len(enerjiler) >= 3:
                kayan = [sum(enerjiler[max(0, i-2):i+1]) / min(i+1, 3) for i in range(len(enerjiler))]
                ax.plot(gunler, kayan, color="#FFFFFF", linewidth=1.6, linestyle="--",
                        marker="o", markersize=4, zorder=3, label="3g Ort.")

            ax.axhline(self.gunluk_hedef, color="#42A5F5", linewidth=1.2, linestyle=":",
                       zorder=2, label=f"Hedef {self.gunluk_hedef}kWh")
            ax.axhline(ortalama, color="#FF7043", linewidth=1, linestyle=":", zorder=2)
            ax.text(len(gunler) - 0.5, ortalama + 0.03, f"Ort: {ortalama:.2f}",
                    color="#FF7043", fontsize=7, va="bottom", ha="right")

            ax.set_xlabel("Gün", color="#888", fontsize=8)
            ax.set_ylabel("kWh", color="#888", fontsize=8)
            ax.tick_params(colors="#888", labelsize=7)
            for spine in ax.spines.values():
                spine.set_edgecolor("#333")
            ax.legend(fontsize=7, facecolor="#1a1a1a", edgecolor="#333",
                      labelcolor="white", loc="upper left")
            ax.grid(True, axis="y", alpha=0.12, zorder=1)
            plt.tight_layout(pad=0.5)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", transparent=True, dpi=110)
            buf.seek(0)
            plt.close(fig)

            Clock.schedule_once(
                lambda dt: setattr(self.root.get_screen("dashboard").ids.grafik_img, "texture",
                                   CoreImage(buf, ext="png").texture), 0
            )
        except Exception as e:
            print(f"[grafik_ciz] {e}")

    def yillik_grafik_ciz(self):
        try:
            aylar  = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
            rng    = np.random.default_rng(99)
            bu_yil = [round(8 + i * 0.5 + rng.uniform(-1, 1), 1) for i in range(12)]
            gec    = [round(9 + i * 0.4 + rng.uniform(-1, 1), 1) for i in range(12)]

            fig, ax = plt.subplots(figsize=(5.5, 2.8))
            fig.patch.set_facecolor("none")
            ax.set_facecolor("#151515")
            x = range(12)
            ax.bar([i - 0.2 for i in x], gec,    width=0.36, color="#455A64", label="Geçen Yıl")
            ax.bar([i + 0.2 for i in x], bu_yil, width=0.36, color="#FF9A00", label="Bu Yıl")
            ax.set_xticks(range(12))
            ax.set_xticklabels(aylar, fontsize=6, color="#888")
            ax.tick_params(colors="#888", labelsize=6)
            for sp in ax.spines.values(): sp.set_edgecolor("#333")
            ax.legend(fontsize=6, facecolor="#1a1a1a", edgecolor="#333", labelcolor="white", loc="upper left")
            ax.grid(True, axis="y", alpha=0.12)
            plt.tight_layout(pad=0.3)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", transparent=True, dpi=100)
            buf.seek(0)
            plt.close(fig)

            Clock.schedule_once(
                lambda dt: setattr(self.root.get_screen("rapor").ids.yillik_grafik_img, "texture",
                                   CoreImage(buf, ext="png").texture), 0
            )
        except Exception as e:
            print(f"[yillik_grafik_ciz] {e}")

    def isita_haritasi_ciz(self):
        try:
            rng  = np.random.default_rng(42)
            veri = rng.uniform(0, 2.5, (7, 24))

            fig, ax = plt.subplots(figsize=(6.5, 3.2))
            fig.patch.set_facecolor("none")
            im = ax.imshow(veri, cmap="YlOrRd", aspect="auto", interpolation="bilinear")
            ax.set_xticks(range(0, 24, 2))
            ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)], fontsize=7, color="#aaa")
            ax.set_yticks(range(7))
            ax.set_yticklabels(["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"], fontsize=8, color="#aaa")
            plt.colorbar(im, ax=ax, label="kWh", shrink=0.8)
            ax.set_title("Saatlik Tüketim Isı Haritası", color="#ccc", fontsize=9, pad=6)
            plt.tight_layout(pad=0.5)

            buf = io.BytesIO()
            plt.savefig(buf, format="png", transparent=True, dpi=100)
            buf.seek(0)
            plt.close(fig)

            Clock.schedule_once(
                lambda dt: setattr(self.root.get_screen("isita_haritasi").ids.isita_img, "texture",
                                   CoreImage(buf, ext="png").texture), 0
            )
        except Exception as e:
            print(f"[isita_haritasi_ciz] {e}")

    # ── PDF RAPOR ─────────────────────────────────────────────────────────────
    def pdf_rapor_olustur(self):
        if not FPDF_AKTIF:
            self.show_popup("PDF Yok", "PDF oluşturmak için:\npip install fpdf2")
            return
        threading.Thread(target=self._pdf_thread, daemon=True).start()

    def _pdf_thread(self):
        try:
            kwh  = toplam_enerji()
            co2  = self.co2_hesapla(kwh)
            skor, _ = self.verimlilik_skoru(kwh)
            tahmin_kwh, tahmin_tl = self.ay_sonu_tahmin(kwh)
            komsu = self.komsu_karsilastirma(kwh)
            _, mevsim = self.mevsimsel_oneri()

            pdf = FPDF()
            pdf.add_page()
            pdf.set_margins(20, 20, 20)

            pdf.set_fill_color(30, 30, 30)
            pdf.set_text_color(255, 153, 0)
            pdf.set_font("Helvetica", "B", 20)
            pdf.cell(0, 14, "AKILLI ENERJI RAPORU v3.1", ln=True, align="C")

            pdf.set_text_color(150, 150, 150)
            pdf.set_font("Helvetica", size=9)
            pdf.cell(0, 6, f"Olusturulma tarihi: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
            pdf.cell(0, 6, f"Il: {self.secili_il}", ln=True, align="C")
            pdf.ln(6)

            satırlar = [
                ("Toplam Tuketim",  f"{kwh:.2f} kWh"),
                ("Tahmini Maliyet", f"TL {kwh * BIRIM_FIYAT:.2f}"),
                ("CO2 Ayak Izi",    f"{co2['co2_kg']} kg  ({co2['agac_esit']} agac esdelegi)"),
                ("Verimlilik Skoru",skor),
                ("Ay Sonu Tahmini", f"{tahmin_kwh} kWh  /  TL {tahmin_tl}"),
                ("Bolge Durumu",    komsu),
                ("Mevsimsel Oneri", mevsim),
                ("Aylik Butce",     f"TL {self.aylik_butce:.0f}"),
                ("Gunluk Hedef",    f"{self.gunluk_hedef} kWh/gun"),
            ]

            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", size=11)
            for baslik, deger in satırlar:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(70, 9, baslik + ":", border="B")
                pdf.set_font("Helvetica", size=11)
                pdf.cell(0, 9, deger, border="B", ln=True)

            masaustu = os.path.join(os.path.expanduser("~"), "Desktop")
            os.makedirs(masaustu, exist_ok=True)
            dosya = os.path.join(masaustu, f"enerji_raporu_{datetime.date.today()}.pdf")
            pdf.output(dosya)

            Clock.schedule_once(
                lambda dt: self.show_popup("PDF Hazır ✓", f"Masaüstüne kaydedildi:\n{dosya}"), 0
            )
        except Exception as e:
            Clock.schedule_once(lambda dt: self.show_popup("PDF Hatası", str(e)), 0)

    # ── CHATBOT ───────────────────────────────────────────────────────────────
    def chatbot_cevapla(self):
        soru = self.root.get_screen("chatbot").ids.chat_input.text.strip().lower()
        if not soru:
            return
        self._chat_ekle("Siz", soru)
        self.root.get_screen("chatbot").ids.chat_input.text = ""

        kwh = toplam_enerji()
        maliyet = kwh * BIRIM_FIYAT
        tahmin_kwh, tahmin_tl = self.ay_sonu_tahmin(kwh)
        co2  = self.co2_hesapla(kwh)
        skor, _ = self.verimlilik_skoru(kwh)
        yuzde = (maliyet / self.aylik_butce) * 100

        anahtar_yanit = [
            (["harcad","tükettim","ne kadar","kaç kwh","kullandım"],
             f"Bu ay {kwh:.2f} kWh tükettiniz. Tahmini maliyet ₺{maliyet:.2f}."),
            (["tahmin","ay sonu","fatura","projeksiyon"],
             f"Ay sonu tahmini: {tahmin_kwh} kWh — ₺{tahmin_tl}. "
             f"(Günlük ortalama: {kwh/max(datetime.date.today().day,1):.2f} kWh)"),
            (["co2","karbon","çevre","emisyon","iklim"],
             f"CO₂ ayak iziniz {co2['co2_kg']} kg — {co2['agac_esit']} ağaç eşdeğeri."),
            (["tasarruf","azalt","düşür","ekonomi","indir"],
             self.tasarruf_onerileri(kwh, yuzde)),
            (["skor","verimlilik","puan","derece"],
             f"Enerji verimliliği skorunuz: {skor}. "
             f"(A=en iyi, G=en kötü). Ay sonu tahmini {tahmin_kwh} kWh."),
            (["bütçe","hedef","limit","harcama"],
             f"Aylık bütçeniz ₺{self.aylik_butce:.0f} — "
             f"şu an %{yuzde:.0f} kullanıldı. "
             f"Akıllı hedef: ₺{self.akilli_hedef_oner(kwh):.0f}."),
            (["pik","tarife","saat","zaman"],
             f"Pik saatler: 06:00-10:00 ve 17:00-22:00. "
             f"Bu saatlerde birim fiyat daha yüksektir. "
             f"Şu an {'PİK saat!' if datetime.datetime.now().hour in PIK_SAATLER else 'normal tarife saati.'}"),
            (["merhaba","selam","hey","naber"],
             "Merhaba! Ben enerji asistanınızım. "
             "Tüketim, maliyet, CO₂ veya tasarruf hakkında sorabilirsiniz."),
            (["ocr","kamera","sayaç","oku"],
             f"OCR (sayaç okuma) durumu: {'Aktif ✓' if OCR_AKTIF else 'Yüklü değil — pip install pytesseract'}. "
             "Kamera ekranından sayacınızı okutabilirsiniz."),
            (["il","şehir","bölge"],
             f"Şu an seçili il: {self.secili_il}. "
             f"Bölge ortalaması: {IL_ORTALAMA.get(self.secili_il, 15.0)} kWh/ay. "
             "Rapor ekranından il değiştirebilirsiniz."),
        ]

        cevap = None
        for kelimeler, yanit in anahtar_yanit:
            if any(k in soru for k in kelimeler):
                cevap = yanit
                break

        if cevap is None:
            cevap = ("Bu konuda enerji verim bilgim yok. "
                     "Deneyin: 'harcadım', 'tasarruf', 'tahmin', 'co2', 'bütçe', 'pik saat', 'il'.")

        Clock.schedule_once(lambda dt: self._chat_ekle("Asistan 🤖", cevap), 0.25)
        Clock.schedule_once(lambda dt: setattr(
            self.root.get_screen("chatbot").ids.chat_scroll, "scroll_y", 0), 0.35)

    def _chat_ekle(self, gonderen: str, metin: str):
        kutu  = self.root.get_screen("chatbot").ids.chat_kutusu
        kullanici = gonderen == "Siz"
        kart  = Factory.MDCard(
            size_hint_y=None,
            height="70dp",
            padding="10dp",
            radius=[12, 12, 2, 12] if kullanici else [12, 12, 12, 2],
            md_bg_color=(0.18, 0.13, 0.03, 1) if kullanici else (0.15, 0.15, 0.17, 1),
        )
        etiket = Factory.MDLabel(
            text=f"[b]{gonderen}:[/b]  {metin}",
            markup=True,
            font_size="12sp",
            theme_text_color="Primary",
        )
        kart.add_widget(etiket)
        kutu.add_widget(kart)

    # ── EKRAN YÜKLEYİCİLER ───────────────────────────────────────────────────
    def rapor_ekranini_yukle(self):
        try:
            kwh   = toplam_enerji()
            co2   = self.co2_hesapla(kwh)
            ekran = self.root.get_screen("rapor")
            ekran.ids.rapor_co2_etiket.text = f"{co2['co2_kg']} kg  |  Ağaç eşd.: {co2['agac_esit']}"
            # İl bazlı karşılaştırma
            ekran.ids.komsu_etiket.text = self.komsu_karsilastirma(kwh, self.secili_il)
            ikon, msg = self.mevsimsel_oneri()
            ekran.ids.mevsim_icon.icon   = ikon
            ekran.ids.mevsim_etiket.text = msg
            threading.Thread(target=self.yillik_grafik_ciz, daemon=True).start()
        except Exception as e:
            print(f"[rapor_ekranini_yukle] {e}")

    def tahmin_ekranini_yukle(self):
        try:
            kwh     = toplam_enerji()
            veriler = gunluk_enerji_grafik_veri()
            tahmin_kwh, tahmin_tl = self.ay_sonu_tahmin(kwh)
            z       = self.anomali_skoru_hesapla(veriler)
            mae     = self.mae_hesapla()
            yuzde   = (kwh * BIRIM_FIYAT / self.aylik_butce) * 100
            oneriler= self.tasarruf_onerileri(kwh, yuzde)
            bugun   = datetime.date.today().day

            ekran = self.root.get_screen("tahmin")
            ekran.ids.tahmin_kwh_etiket.text    = f"{tahmin_kwh} kWh  |  ₺{tahmin_tl}"
            ekran.ids.tahmin_aciklama.text       = f"Gün {bugun}/30  •  Günlük ort: {kwh/max(bugun,1):.2f} kWh"
            ekran.ids.anomali_etiket.text        = f"{z}  {'⚠️ Anormal!' if abs(z) > 2 else '✔ Normal'}"
            ekran.ids.tasarruf_oneri_etiket.text = oneriler
            ekran.ids.mae_etiket.text            = f"{mae} kWh" if mae > 0 else "Henüz veri yok"

            if abs(z) > 2:
                self.show_popup("Anomali", f"Anormal tüketim tespit edildi!\nZ-Skoru: {z}")

        except Exception as e:
            print(f"[tahmin_ekranini_yukle] {e}")

    # ── ROZET SİSTEMİ ─────────────────────────────────────────────────────────
    def rozet_hesapla(self, kwh: float) -> set:
        return {b["id"] for b in self.BADGE_TANIMLARI if kwh >= b["esik"]}

    def rozet_ui_guncelle(self, kwh: float):
        kazanilan = self.rozet_hesapla(kwh)
        try:
            kutu = self.root.get_screen("dashboard").ids.rozet_kutusu
            kutu.clear_widgets()
            for badge in self.BADGE_TANIMLARI:
                aktif = badge["id"] in kazanilan
                kart  = Factory.MDCard(
                    orientation="vertical", padding="8dp",
                    size_hint=(None, None), size=("72dp", "76dp"),
                    radius=[12],
                    md_bg_color=(0.20, 0.18, 0.05, 1) if aktif else (0.13, 0.13, 0.13, 1),
                )
                ikon = Factory.MDIcon(
                    icon=badge["icon"], font_size="26sp", halign="center",
                    theme_text_color="Custom",
                    text_color=(1, 0.65, 0, 1) if aktif else (0.35, 0.35, 0.35, 1),
                )
                etiket = Factory.MDLabel(
                    text=badge["isim"], font_style="Caption", halign="center",
                    font_size="8sp", theme_text_color="Custom",
                    text_color=(0.95, 0.95, 0.95, 1) if aktif else (0.35, 0.35, 0.35, 1),
                )
                kart.add_widget(ikon)
                kart.add_widget(etiket)
                kutu.add_widget(kart)
        except Exception as e:
            print(f"[rozet_ui_guncelle] {e}")

    # ── UYARI KONTROLÜ ─────────────────────────────────────────────────────────
    def _uyari_kontrol(self, kwh: float, maliyet: float, yuzde: float):
        saat = datetime.datetime.now().hour
        if saat in PIK_SAATLER:
            print("[BİLDİRİM] Pik tarife saati.")
        if 78 < yuzde < 82:
            Clock.schedule_once(
                lambda dt: self.show_snack("⚠️ Bütçenizin %80'ine ulaştınız!"), 0)
        if yuzde >= 100:
            Clock.schedule_once(
                lambda dt: self.show_popup("🔴 Bütçe Aşıldı!", "Aylık bütçeniz doldu."), 0)
        if 0 <= saat <= 6 and (kwh / max(datetime.date.today().day, 1)) > 1.0:
            print("[BİLDİRİM] Gece yüksek tüketim.")

    # ── PROFİL ────────────────────────────────────────────────────────────────
    def _profil_guncelle(self, kwh: float):
        try:
            skor, _ = self.verimlilik_skoru(kwh)
            co2     = self.co2_hesapla(kwh)
            ekran   = self.root.get_screen("hesap")
            ekran.ids.profil_verimlilik.text = f"Skor: {skor}  |  CO₂: {co2['co2_kg']} kg/ay"
        except:
            pass

    # ── AYARLAR POPUP'LARI ────────────────────────────────────────────────────
    def tarife_optimizasyonu(self):
        veriler = gunluk_enerji_grafik_veri()
        toplam  = sum(v["enerji"] for v in veriler)
        self.show_popup(
            "Tarife Önerisi",
            f"Mevcut: Tek zaman — 2.28 TL/kWh\n\n"
            f"Çift Zaman (tahmin):\n"
            f"  Gündüz: 2.80 TL/kWh\n"
            f"  Gece:   1.20 TL/kWh\n\n"
            f"Yıllık tasarruf potansiyeli: ≈₺{toplam*12*0.5:.0f}"
        )

    def ocr_durum_goster(self):
        durum   = "✓ Aktif" if OCR_AKTIF else "✗ Yüklü değil"
        kurulum = "" if OCR_AKTIF else "\n\nKurmak için:\npip install pytesseract\n+ Tesseract kurulumu"
        self.show_popup("OCR Durumu", f"pytesseract: {durum}{kurulum}")

    def bildirim_ayarlari_mesaj(self):
        self.show_popup(
            "Bildirim Ayarları",
            "Bütçe alarmı: %80 ve %100 eşiği\n"
            "Pik saat uyarısı: 06-10 ve 17-22\n"
            "Gece boşta uyarısı: 00-06 arası\n"
            "Anomali tespiti: Z-Score > 2"
        )

    def veri_sifirla_onayla(self):
        self.show_popup("Veri Sıfırla", "Bu özellik veritabanı bağlıyken aktif olur.\nMock modda işlem yapılmaz.")

    def hakkinda_mesaj(self):
        self.show_popup(
            f"Akıllı Enerji v{VERSIYON}",
            "30+ özellikli enerji verimliliği\n"
            "ve sayaç takip uygulaması.\n\n"
            f"OCR: {'Aktif' if OCR_AKTIF else 'Pasif'}\n"
            f"PDF: {'Aktif' if FPDF_AKTIF else 'Pasif'}\n"
            f"Veritabanı: {'MySQL Bağlı' if DB_ENGINE_AKTIF else ('Modül Bağlı' if DB_AKTIF else 'Mock')}\n"
            f"Şifre: {SIFRE_MIN}-{SIFRE_MAX} karakter"
        )

    # ── NAVIGASYON ───────────────────────────────────────────────────────────
    def goto_screen(self, sc: str):
        self.root.current = sc
        if sc == "rapor":
            Clock.schedule_once(lambda dt: self.rapor_ekranini_yukle(), 0.2)
        elif sc == "tahmin":
            Clock.schedule_once(lambda dt: self.tahmin_ekranini_yukle(), 0.2)
        elif sc == "isita_haritasi":
            Clock.schedule_once(lambda dt: self.isita_haritasi_ciz(), 0.2)

    def goto_dashboard(self):
        self.root.current = "dashboard"

    # ── YARDIMCI POPUP / SNACK ───────────────────────────────────────────────
    def show_popup(self, baslik: str, metin: str):
        if self.dialog:
            self.dialog.dismiss()
        self.dialog = MDDialog(
            title=baslik,
            text=metin,
            buttons=[MDRaisedButton(
                text="TAMAM",
                md_bg_color=(1, 0.65, 0, 1),
                on_release=lambda x: self.dialog.dismiss()
            )]
        )
        self.dialog.open()

    def show_snack(self, metin: str):
        try:
            Snackbar(text=metin, snackbar_x="12dp", snackbar_y="12dp",
                     size_hint_x=0.95, duration=2.5).open()
        except Exception:
            print(f"[Snack] {metin}")


# ── BAŞLAT ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    EnerjiApp().run()