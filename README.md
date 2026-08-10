<div align="center">

# پخش زنده ویدیو / Live Video Player

پخش آنلاین ویدیو از لینک مستقیم (HTTP/HTTPS) با رابط کاربری تیره و مدرن.

Stream online video from direct HTTP/HTTPS links with a modern dark UI.

</div>

---

## فارسی

### معرفی

این برنامه یک پخش‌کننده ویدیو از **لینک مستقیم** است. کافی است لینک یک فایل ویدیویی را وارد کنید؛ برنامه
ویدیو را با دانلود موازی و بافر درون‌حافظه، روان و بدون قطعی پخش می‌کند.

### امکانات

- پخش ویدیو از لینک مستقیم `http://` یا `https://`
- دانلود موازی با چند اتصال برای سرعت بیشتر
- بافر (Cache) در RAM با قابلیت تنظیم اندازه
- پشتیبانی از درخواست‌های `Range` و حالت جایگزین برای سرورهای بدون پشتیبانی Range
- دو حالت پخش:
  - **HTML5** درون خود برنامه (شروع سریع و کنترل کامل)
  - **VLC** برای فرمت‌هایی که مرورگر پشتیبانی نمی‌کند (مانند MKV و AVI)
- پخش از طریق پروکسی لوکال (loopback) برای محافظت از لینک اصلی
- رابط کاربری تیره و فارسی
- نادیده گرفتن خطای گواهی HTTPS (با `--insecure`)

### نصب و اجرا از سورس

پیش‌نیازها: پایتون ۳.۱۰ به بالا

```bash
pip install -r requirements.txt
python main.py
```

### اجرا با پارامتر

```bash
python main.py --url https://example.com/video.mp4 --cache 512
```

| پارامتر | توضیح |
| --- | --- |
| `--url` | لینک مستقیم ویدیو هنگام شروع |
| `--cache` | حداکثر بافر در RAM به مگابایت (پیش‌فرض: ۲۵۶) |
| `--keep-ahead` | حداکثر فاصله دریافت در حالت بدون Range (پیش‌فرض: ۶۴) |
| `--workers` | تعداد اتصال‌های موازی (پیش‌فرض: ۳) |
| `--insecure` | نادیده گرفتن خطای گواهی HTTPS |
| `--debug` | فعال‌سازی کنسول توسعه WebView |

> نکته: برای پخش فرمت‌هایی که مرورگر پشتیبانی نمی‌کند، باید [VLC](https://www.videolan.org/vlc/)
> نصب باشد.

### ساخت نسخه اجرایی (EXE)

```bash
pip install pyinstaller
python -m PyInstaller build.spec --noconfirm --clean
```

---

## English

### About

This is a streaming video player for **direct media links**. Paste a direct link to a video file and
the app streams it smoothly using parallel downloads and an in-memory buffer.

### Features

- Plays video from direct `http://` / `https://` links
- Parallel multi-connection downloads for higher throughput
- RAM cache with configurable size
- Supports `Range` requests plus a fallback mode for servers without Range support
- Two playback modes:
  - **HTML5** inside the app (fast start, full controls)
  - **VLC** for formats the browser cannot play (e.g. MKV, AVI)
- Streams through a loopback proxy so the original link stays hidden
- Dark, modern UI
- Ignore HTTPS certificate errors (`--insecure`)

### Install & run from source

Prerequisites: Python 3.10+

```bash
pip install -r requirements.txt
python main.py
```

### Usage

```bash
python main.py --url https://example.com/video.mp4 --cache 512
```

| Argument | Description |
| --- | --- |
| `--url` | Direct video link to play on startup |
| `--cache` | Max RAM buffer in MiB (default: 256) |
| `--keep-ahead` | Max fetch lead in no-range mode in MiB (default: 64) |
| `--workers` | Number of parallel download connections (default: 3) |
| `--insecure` | Ignore HTTPS certificate errors |
| `--debug` | Keep the WebView development console enabled |

> Note: [VLC](https://www.videolan.org/vlc/) is required to play formats the
> browser does not support.

### Building the executable

```bash
pip install pyinstaller
python -m PyInstaller build.spec --noconfirm --clean
```

---

## License

This project is released under the [MIT License](LICENSE).
