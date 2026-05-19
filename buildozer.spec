[app]
title = Akilli Enerji
package.name = akillıenerji
package.domain = org.akilli

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

entrypoint = mobile_app_kivy.py

version = 3.1

requirements = python3,kivy==2.3.0,kivymd==1.2.0,numpy,matplotlib,pillow

orientation = portrait
fullscreen = 0

android.permissions = CAMERA,INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a

[buildozer]
log_level = 2