<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License: MIT"/>
  <img src="https://img.shields.io/badge/Platform-Windows-blue.svg?style=for-the-badge&logo=windows&logoColor=white" alt="Platform: Windows"/>
</p>

<h1 align="center">🎬 Live Video Player</h1>

<p align="center">
  <em>پخش آنلاین ویدیو از لینک مستقیم</em> ·
  <em>Stream online video from direct links</em>
</p>

---

## 🇬🇧 English

### 📖 About

**Live Video Player** is a desktop application that plays video from a **direct
media link** (`http` / `https`). Just paste the link and the app streams the
video smoothly — using **parallel downloads** and an **in-memory buffer** to
keep playback fast and interruption-free.

### ✨ Features

| Feature | Description |
| --- | --- |
| ⚡ Parallel downloads | Multi-connection fetching for higher throughput |
| 🧠 RAM cache | Configurable in-memory buffer (default 256 MiB) |
| 📡 `Range` support | Plays Range-capable servers, plus a fallback mode for servers without it |
| 🎞️ Two playback modes | **HTML5** inside the app, or **VLC** for formats the browser can't play (MKV, AVI…) |
| 🔒 Loopback proxy | Streams through a local proxy so the original link stays hidden |
| 🌑 Dark UI | Modern, dark, RTL-ready interface |
| 🛡️ `--insecure` | Ignore HTTPS certificate errors when needed |

### 🚀 Install & run from source

Prerequisites: **Python 3.10 or newer**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python main.py
```

### 🎯 Usage

```bash
python main.py --url https://example.com/video.mp4 --cache 512
```

#### Command-line options

| Option | Description |
| --- | --- |
| `--url <link>` | Direct video link to play on startup |
| `--cache <mb>` | Max RAM buffer in MiB *(default: 256)* |
| `--keep-ahead <mb>` | Max fetch lead in no-range mode in MiB *(default: 64)* |
| `--workers <n>` | Number of parallel download connections *(default: 3)* |
| `--insecure` | Ignore HTTPS certificate errors |
| `--debug` | Keep the WebView development console enabled |

> 💡 **Note:** [VLC](https://www.videolan.org/vlc/) must be installed to play
> formats the browser does not support.

### 📦 Building the executable

```bash
pip install pyinstaller
python -m PyInstaller build.spec --noconfirm --clean
```

---

## 🇮🇷 فارسی

### 📖 معرفی

**پخش زنده ویدیو** یک برنامه دسکتاپ برای پخش ویدیو از **لینک مستقیم**
(`http://` یا `https://`) است. کافی است لینک فایل ویدیویی را وارد کنید تا برنامه
با **دانلود موازی** و **بافر درون‌حافظه**، ویدیو را روان و بدون قطعی پخش کند.

### ✨ امکانات

| امکانات | توضیح |
| --- | --- |
| ⚡ دانلود موازی | دریافت فایل با چند اتصال هم‌زمان برای سرعت بیشتر |
| 🧠 بافر در RAM | حافظه موقت قابل تنظیم (پیش‌فرض: ۲۵۶ مگابایت) |
| 📡 پشتیبانی از `Range` | پخش از سرورهای دارای Range و حالت جایگزین برای سرورهای بدون آن |
| 🎞️ دو حالت پخش | **HTML5** درون خود برنامه، یا **VLC** برای فرمت‌هایی که مرورگر پشتیبانی نمی‌کند (MKV، AVI و…) |
| 🔒 پروکسی لوکال | پخش از طریق پروکسی داخلی تا لینک اصلی مخفی بماند |
| 🌑 رابط کاربری تیره | ظاهری مدرن، تیره و فارسی |
| 🛡️ `--insecure` | نادیده گرفتن خطای گواهی HTTPS در صورت نیاز |

### 🚀 نصب و اجرا از سورس

پیش‌نیازها: **پایتون ۳.۱۰ یا بالاتر**

```bash
# ۱. نصب وابستگی‌ها
pip install -r requirements.txt

# ۲. اجرای برنامه
python main.py
```

### 🎯 اجرا با پارامتر

```bash
python main.py --url https://example.com/video.mp4 --cache 512
```

#### پارامترهای خط فرمان

| پارامتر | توضیح |
| --- | --- |
| `--url <لینک>` | لینک مستقیم ویدیو هنگام شروع |
| `--cache <مگابایت>` | حداکثر بافر در RAM *(پیش‌فرض: ۲۵۶)* |
| `--keep-ahead <مگابایت>` | حداکثر فاصله دریافت در حالت بدون Range *(پیش‌فرض: ۶۴)* |
| `--workers <تعداد>` | تعداد اتصال‌های موازی دانلود *(پیش‌فرض: ۳)* |
| `--insecure` | نادیده گرفتن خطای گواهی HTTPS |
| `--debug` | فعال‌سازی کنسول توسعه WebView |

> 💡 **نکته:** برای پخش فرمت‌هایی که مرورگر پشتیبانی نمی‌کند، باید
> [VLC](https://www.videolan.org/vlc/) نصب باشد.

### 📦 ساخت نسخه اجرایی (EXE)

```bash
pip install pyinstaller
python -m PyInstaller build.spec --noconfirm --clean
```

---

## 📄 License

Released under the [MIT License](LICENSE) · Copyright © 2026 **SOHAYB N13**
