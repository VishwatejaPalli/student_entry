# 🏫 Room Entry & Lab Data Management System

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite%20EAV-003B57.svg)](https://www.sqlite.org/)
[![Raspberry Pi](https://img.shields.io/badge/Hardware-Raspberry%20Pi%20Ready-C51A4A.svg)](https://www.raspberrypi.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, hardware-ready **Room Entry & Laboratory Data Management Platform** designed for academic laboratories, college departments, research centers, and smart facilities. 

Includes support for **Individual Walk-in Kiosk Entry**, **Live Class Session Scanner Cockpits**, **Semester Batch Division**, **Dynamic Form Builder (Zero Code)**, **Solid Material Symbols UI**, **Formatted Master Excel Exports**, and a **Password-Protected Year-End Data Purge Center**.

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
      Dashboard    Analytics    Master Excel Sheets
```

### 1. 👤 Individual Entry & Exit Kiosk
* **Barcode / Manual Roll Input**: High-speed scanner autofocus for instant check-in.
* **Dynamic Form Rendering**: Dynamically asks custom questions (Purpose, PC Number, Project, Remarks) configured by the admin without code changes.
* **Personalized Exit Screen**: Displays student name, exact In/Out timestamps, total duration spent in the lab (`2h 15m`), and an automatic 3-second countdown before resetting.

### 2. ⚡ Live Class Session Cockpit
* **Designed for Lab Classes**: Created for 30–60 student laboratory batches (e.g. *ECE-A*, *VLSI Lab*, *14:00–16:00*).
* **High-Speed Scanner Input**: Permanent autofocus recovery so USB barcode scanner keystrokes are never lost.
* **Web Audio Synthesizer**: Harmonic chime for on-time arrival, warning tone for late entry, and buzzer for errors.
* **Smart PC Auto-Assignment**: Automatically assigns `PC-01`, `PC-02`... sequentially as students scan.
* **Single-Click "End Session"**: Automatically marks all unscanned students as `ABSENT` and calculates durations.

### 3. 📋 3-Way Student Selection & Semester Batch Allocator
* **Class Roster Checkbox Grid**: Select from pre-enrolled classes with checkboxes and *Select All / Deselect All*.
* **Drag & Drop Excel / CSV Dropzone**: Upload `.xlsx` or `.csv` files to auto-parse roll numbers.
* **Multiline Paste Box**: Paste roll numbers separated by newlines, commas, or spaces (unlisted students are automatically registered in the directory).
* **Semester Batch Allocator**: Automatically divides class cohorts into $N$ equal lab batches (e.g., `ECE-A` into `A1, A2` or `Batch 1, Batch 2`) directly in the database.

### 4. 📊 Master Excel Spreadsheet Exports
* **Master Student Directory Excel (`/api/export/students/excel`)**: Complete formatted student roster with index, roll number, full name, department, section, batch, year, status, and registered date.
* **Master Entry Log Excel (`/api/export/excel`)**: Comprehensive activity logs containing roll number, student name, department, section, batch, session name/type, date, entry time, exit time, duration, and custom form question responses.
* **Session Attendance Excel (`/api/export/session/{id}/excel`)**: Color-coded attendance sheets with PC numbers and status.

### 5. 🗑️ Password-Protected Year-End Data Reset Center
Easily clear or reset the database for a new academic year or semester in one click:
* **Option 1: Clear Master Student Directory & Records**: Wipes the student list for clean incoming batch imports.
* **Option 2: Clear Activity Logs & Class Sessions Only**: Clears attendance logs, keeping students intact for the next semester.
* **Option 3: Complete Fresh Reset (Wipe All)**: Clears all students, records, and sessions.
* **Direct Excel Download Shortcuts**: Download fresh copies of your Master Student Excel and Master Entry Logs Excel right before wiping.

---

## 🔒 Admin Password (1-Place Configuration)

The password for the **Year-End Data Reset & Purge Center** is configured in **one single place**: the `.env` file in your project folder.

### How to Change the Password:
Open `.env` and change the `ADMIN_PASSWORD` value:

```ini
ADMIN_PASSWORD=your_new_password
```

*(Default password: `admin`)*

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
├── main.py                     # FastAPI application & lifespan entry point
├── database.py                 # SQLite schema, EAV pattern & seed data
├── models.py                   # Pydantic validation schemas
├── install.sh                  # Turnkey 1-line Linux/Pi automated installer
├── uninstall.sh                # Clean uninstaller script
│
├── services/
│   ├── form_engine.py          # Dynamic HTML form generator & validator
│   ├── entry_service.py        # Individual entry, exit & duration business logic
│   ├── session_service.py      # Live class session engine, batch allocator & PC assignment
│   └── export_service.py       # Master Excel & CSV spreadsheet generator (OpenPyXL)
│
├── routers/
│   ├── entry.py                # Individual student scan & dynamic form submission
│   ├── sessions.py             # Class sessions hub, batch allocator & live cockpit API
│   ├── dashboard.py            # Live occupancy dashboard & quick-scan API
│   ├── forms.py                # Visual Form Builder CRUD
│   ├── students.py             # Student directory, import & password-protected clear API
│   └── export.py               # Master Excel and CSV export endpoints
│
├── templates/
│   ├── base.html               # Base layout with Google Material Symbols & Anti-FOUC theme
│   ├── entry.html              # Individual entry form & Exit message screen
│   ├── dashboard.html          # Real-time room occupancy dashboard
│   ├── sessions/
│   │   ├── index.html          # Class sessions hub (3 selection modes & allocator)
│   │   ├── live.html           # High-speed barcode scanner live cockpit
│   │   └── settings.html       # Bulk presets & custom field settings
│   └── admin/
│       ├── form-builder.html   # Drag-and-drop form editor
│       ├── form-preview.html   # Form test preview
│       ├── students.html       # Student roster management table & Clear Data modal
│       └── export.html         # Master Excel export center & Year-End Reset card
│
└── static/
    ├── css/
    │   ├── style.css           # Compiled glassmorphic design system
    │   ├── base.css            # Typography & solid Material Symbols styles
    │   ├── tokens.css          # Color variables & dark/light theme tokens
    │   └── components/         # Modular buttons, cards, tables, scanner, modal styles
    └── js/
        ├── app.js              # Shared toast, modal & API utilities
        ├── entry.js            # Barcode scanner input & Exit countdown timer
        ├── session-live.js     # Web Audio synth chime & permanent autofocus
        ├── sessions.js         # Dropzone Excel parser & batch allocator
        ├── session-settings.js # Dynamic preset tags & custom session fields
        ├── form-builder.js     # Form field CRUD & reordering
        ├── dashboard.js        # Auto-refresh statistics & table filters
        └── admin.js            # Student import, search & password-protected clear data
```

---

## 📜 License

MIT License. Free for educational and commercial use.
