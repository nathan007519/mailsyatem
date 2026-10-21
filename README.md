# Mail Server (Android APK)

Self-hosted SMTP mail server + mail app in one APK. Kivy UI, SQLite storage, no Gmail/Outlook.

## App password
On first launch you create your address and an **app password**.
- It unlocks the app (stored only as a salted PBKDF2 hash).
- It is the SMTP AUTH password other mail clients must use to *send through* your server.
- Anyone can deliver mail *to* your address; nobody can relay through you without the password.

## Try it on a PC first
    pip install kivy aiosmtpd dnspython
    python main.py
Use `me@localhost` as the address. Tests: `python tests/test_core.py`

## Build the APK (Linux / WSL2 / Google Colab)
    sudo apt update
    sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
        zlib1g-dev libncurses5-dev libncursesw5-dev cmake libffi-dev libssl-dev
    pip install --user buildozer "cython<3"
    buildozer -v android debug          # first build downloads SDK/NDK: 20-40 min
    # APK appears in ./bin/  ->  adb install bin/*.apk   (or copy to the phone)

## Connect other apps (same Wi-Fi)
Server = phone IP shown in the Info tab, port 2525, user = your address,
password = app password, no encryption.

## Build in the cloud (no Linux needed)
1. Create a free GitHub repo and upload the *contents* of this folder (including the hidden `.github` folder).
2. Open the repo's **Actions** tab -> "Build APK" -> wait ~30-40 min.
3. Open the finished run -> download the **mail-server-apk** artifact -> unzip -> install the .apk on your phone.
