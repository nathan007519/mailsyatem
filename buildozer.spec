[app]
title = Mail Server
package.name = mailserver
package.domain = org.squadround
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
source.exclude_patterns = test_*.py
version = 1.0.0

# pure-python deps (aiosmtpd, dnspython) are pulled from PyPI by python-for-android
requirements = python3,kivy==2.3.0,sqlite3,openssl,aiosmtpd,atpublic,attrs,typing_extensions,dnspython

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,WAKE_LOCK,FOREGROUND_SERVICE
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1
