# AggieWorks Finance Tracker

A web application for AggieWorks Director of Finance to scrape and track incoming member Venmo and Zelle payments from Gmail.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [CSV Output](#csv-output)
- [Payment Sources](#payment-sources)

---

## Overview

This repository includes:

1. **Frontend**: A Next.js application with server-side rendering. Using TailwindCSS for styling and shadcn/ui for pre-built components.
2. **Backend**: A FastAPI backend for scraping Gmail emails, extracting payment data, and exporting to CSV. Using Gmail API OAuth2 for secure authentication.

---

## Project Structure

```
aw-finance-tracker/
├── backend/
│   ├── tokens/              # OAuth2 tokens (one per Gmail account)
│   ├── main.py              # FastAPI routes and API logic
│   ├── scraper.py           # Gmail scraping logic (Venmo & Zelle)
│   ├── csv_handler.py       # CSV read/write operations
│   ├── run.py               # Backend entry point
│   ├── requirements.txt     # Python dependencies
│   └── credentials.json     # Gmail API credentials (you must add this)
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx     # Main scraper form page
│   │   │   └── login/
│   │   │       └── page.tsx # Login page
│   │   └── lib/
│   │       └── utils.ts     # Utility functions
│   ├── components.json      # shadcn/ui configuration
│   └── package.json         # Node.js dependencies
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.13+ with pip
- Node.js with pnpm ([installation](https://pnpm.io/installation))
- Gmail account

---

### 1. Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Make sure you are logged into the AggieWorks console
3. Navigate to **APIs & Services** > **OAuth consent screen**
4. Go to the **Audience** section on the left
5. Scroll to **Test users** section
6. Click **+ ADD USERS** and add your Gmail address
7. Leave **OAuth consent screen** and go to **Credentials** > Select your OAuth 2.0 Client ID
8. Download credentials JSON → Rename to `credentials.json`
9. Replace `credentials.json` in `backend/` folder with new one

---

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3. Frontend

```bash
cd frontend
pnpm install
```

---

### 4. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate
python run.py
```
Backend runs on `http://localhost:8000`

**Terminal 2 - Frontend:**
```bash
cd frontend
pnpm dev
```
Frontend runs on `http://localhost:3000`

Open [http://localhost:3000](http://localhost:3000) in your browser.

**First Run:** Browser will open for Gmail OAuth (click Allow). Each Gmail account needs separate authentication.

---

## Usage

1. **Login** - Enter your Gmail credentials (saved in browser for future sessions)
2. **Select payment sources:**
   - ☑️ Venmo - scrapes from `venmo@venmo.com`
   - ☑️ Zelle - scrapes from `alerts@notify.wellsfargo.com`
   - Select one, the other, or both
3. **Choose category:**
   - **Retreat** - searches for retreat-related keywords
   - **Dues** - searches for dues/membership keywords
   - **Other** - enter custom comma-separated keywords
4. **Select start date/time** - scraper searches from this point forward
5. **Click "Run Scraper"**

Results are saved to `backend/member_to_DoF_payments.csv`

**Note:** CSV file resets when you change payment sources or start date/time parameters.

---

## CSV Output

**Location:** `backend/member_to_DoF_payments.csv`

**Columns:**
- `Person` - Who paid you
- `Date` - Payment timestamp (YYYY-MM-DD HH:MM AM/PM)
- `Description` - Payment note/memo
- `Amount` - Payment amount ($X.XX)

**Behavior:**
- Only tracks **incoming** payments (money you received)
- No duplicates (detected by Person + Date + Amount)
- Sorted by date (newest first)
- Updates same file on repeated runs with identical parameters
- Includes a **TOTAL** row at the bottom summing all amounts
- Resets CSV when payment source or date changes

---

## Payment Sources

### Venmo
- **Email:** `venmo@venmo.com`
- **Subject:** `[Name] paid you $X.XX`
- **Extracts:** Person, amount, date, payment note

### Zelle (Wells Fargo)
- **Email:** `alerts@notify.wellsfargo.com`
- **Subject:** `You received money with Zelle®`
- **Body format:** `[NAME] sent you $X.XX`
- **Extracts:** Person, amount, date, memo

---

## Security

- `credentials.json` and `tokens/` are git-ignored
- Never commit these files - they contain authentication credentials
- CSV output is also git-ignored
- Login credentials stored in browser localStorage (clear on logout)
- Each Gmail account gets its own token file for multi-account support

---

## Contributors

- Samar Varma
