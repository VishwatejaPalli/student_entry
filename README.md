# 🏫 Room Entry & Lab Data Management System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20EAV-003B57.svg)](https://www.sqlite.org/)
[![Raspberry Pi](https://img.shields.io/badge/Hardware-Raspberry%20Pi%20Ready-C51A4A.svg)](https://www.raspberrypi.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, configurable, hardware-ready **Room Entry & Laboratory Data Management Platform** designed for academic labs, research centers, computer labs, and smart facilities. 

Includes support for **Individual Walk-in Entry**, **Live Class Session Cockpits**, **Dynamic Form Builder (Zero Code)**, **Barcode Scanner autofocus with Web Audio chimes**, **Smart PC Auto-Assignment**, and **Attendance Excel Exports**.

---

## ⚡ Quick 1-Line Installation (Linux / Raspberry Pi)

Run this on any Debian/Ubuntu machine or Raspberry Pi:

```bash
curl -sSL https://raw.githubusercontent.com/VishwatejaPalli/student_entry/main/install.sh | sudo bash
```

Or clone and run locally:

```bash
git clone https://github.com/VishwatejaPalli/student_entry.git
cd student_entry
sudo bash install.sh
```

The installer automatically:
* Installs all system dependencies (`python3`, `sqlite3`, `pip`, `venv`).
* Sets up the virtual environment and Python packages.
* Configures and enables a `systemd` background service (`student-entry.service`) that starts on boot.
* Installs the `student-entry` CLI management utility.

---

## 🎯 Key Features

```text
                 ENTRY INTERFACE
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 Individual        Class          Bulk Import
 (Dynamic Form)   Session         (Excel/Paste)
       │              │               │
       ▼              ▼               ▼
  SQLite DB      Live Cockpit     Batch Records
 (records + EAV) (session_students) (class_sessions)
       │              │               │
       └──────────────┼───────────────┘
                      ▼
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      Dashboard    Analytics    Excel Sheets
```

### 1. 👤 Individual Entry & Exit Screen
* **Barcode / Manual Roll Input**: Quick input with scanner autofocus.
* **Dynamic Form Rendering**: Dynamically asks custom questions (Purpose, PC Number, Project, Remarks) configured by the admin.
* **Personalized Exit Message Screen**: When a student leaves, displays student name, exact In/Out timestamps, total duration spent in the lab (`2h 15m`), and an automatic 4-second countdown before resetting for the next student.

### 2. ⚡ Live Class Session Cockpit
* **Designed for Lab Classes**: Created for 30–60 student laboratory batches (e.g. *ECE-A*, *VLSI Lab*, *14:00–16:00*).
* **High-Speed Scanner Input**: Permanent autofocus recovery so USB barcode scanner keystrokes are never lost.
* **Web Audio Synthesizer**: Pleasant harmonic two-tone chime for on-time arrival, warning sound for late entry, and buzzer for unregistered cards.
* **Smart PC Auto-Assignment**: Automatically assigns `PC-01`, `PC-02`... in the order students arrive and scan.
* **Single-Click "End Session"**: Automatically marks all unscanned students as `ABSENT` and calculates duration for all attendees.

### 3. 📋 3-Way Student Selection for Classes
* **Class / Section Roster**: Select from pre-enrolled classes (`ECE-A`, `CSE-B`) with checkboxes and *Select All / Deselect All*.
* **Drag & Drop Excel / CSV Dropzone**: Upload `.xlsx` or `.csv` files to auto-parse roll numbers with duplicate detection.
* **Multiline Paste Box**: Paste roll numbers separated by newlines, commas, or spaces.

### 4. 🛠️ Dynamic Form Builder (Zero Code)
* Create, customize, and reorder fields without editing source code:
  * Layout: Headings, Info Paragraphs, Dividers.
  * Inputs: Text, Number, Textarea, Date, Time.
  * Selectors: Dropdowns, Radio buttons, Checkboxes.
* Multiple forms stored with versioning; toggle active form with 1 click.
* Uses **Entity-Attribute-Value (EAV)** SQLite schema so adding fields never requires database migrations.

### 5. 📊 Live Dashboard & Formatted Excel Export
* **Live Occupancy Stats**: Real-time count of currently present students and total daily visits.
* **Class Attendance Sheets**: Export styled Excel reports with Faculty, Subject, Scheduled vs Actual In/Out times, Durations, and status color codes (`PRESENT`, `LATE`, `ABSENT`).
* **Custom Filter Exports**: Date range, form-based, or class-based exports.

---

## 🛠️ CLI Management Tool

Once installed with `install.sh`, you can manage the service with `student-entry`:

```bash
# Check service status
student-entry status

# View live real-time logs
student-entry logs

# Restart service
student-entry restart

# Create a timestamped SQLite database backup
student-entry backup

# Pull latest update from GitHub and restart
student-entry update
```

---

## 🍓 Raspberry Pi & Kiosk Mode Setup

### Hardware Requirements
* **Board**: Raspberry Pi Zero 2 W, Raspberry Pi 3B+, 4B, or 5.
* **Display**: Any HDMI monitor or Official 7" Raspberry Pi Touchscreen.
* **Scanner**: Standard USB 1D/2D Barcode Scanner (HID Keyboard Emulation mode).

### Auto-Start Chromium in Fullscreen Kiosk Mode
To launch the entry screen automatically on boot without window frames:

1. Edit your Pi autostart file:
   ```bash
   nano ~/.config/lxsession/LXDE-pi/autostart
   ```
2. Add:
   ```bash
   @xset s off
   @xset -dpms
   @xset s noblank
   @chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost:8000
   ```

---

## 🏗️ Project Structure

```
student_entry/
├── main.py                     # FastAPI lifespan application entry point
├── database.py                 # SQLite schema, EAV pattern & sample data seeding
├── models.py                   # Pydantic request & response validation schemas
├── install.sh                  # Turnkey 1-line Linux/Pi automated installer
├── uninstall.sh                # Clean uninstaller script
│
├── services/
│   ├── form_engine.py          # Dynamic HTML form generator & validator
│   ├── entry_service.py        # Individual entry, exit & duration business logic
│   ├── session_service.py      # Live class session engine & PC auto-assignment
│   └── export_service.py       # OpenPyXL styled Excel & CSV report generator
│
├── routers/
│   ├── entry.py                # Individual student scan / form submission routes
│   ├── sessions.py             # Class sessions hub & live cockpit API
│   ├── dashboard.py            # Live occupancy dashboard API
│   ├── forms.py                # Admin Form Builder CRUD
│   ├── students.py             # Student roster management & Excel import
│   └── export.py               # Excel and CSV export endpoints
│
├── templates/
│   ├── base.html               # Base layout with fonts, toasts, modals
│   ├── entry.html              # Individual entry form & Exit message screen
│   ├── dashboard.html          # Real-time room occupancy dashboard
│   ├── sessions/
│   │   ├── index.html          # Class sessions hub (3 selection modes)
│   │   └── live.html           # High-speed barcode scanner cockpit
│   └── admin/
│       ├── form-builder.html   # Visual drag-and-drop form editor
│       ├── form-preview.html   # Form test preview
│       ├── students.html       # Student roster management table
│       └── export.html         # Custom export filters
│
└── static/
    ├── css/style.css           # Premium dark-mode glassmorphic design system
    └── js/
        ├── app.js              # Shared toast, modal, API & time utilities
        ├── entry.js            # Barcode scanner input & Exit countdown timer
        ├── session-live.js     # Web Audio synth chime & permanent autofocus
        ├── sessions.js         # Dropzone Excel parser & multi-mode selection
        ├── form-builder.js     # Form field CRUD & reordering
        ├── dashboard.js        # Auto-refresh statistics & table filters
        └── admin.js            # Student import & debounced search
```

---

## 📜 License

MIT License. Free for educational and commercial use.
