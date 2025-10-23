# AggieWorks Member Payment Tracker

Web app to scrape incoming Venmo payments from Gmail and export to CSV.

## Features

- 🔍 Scrapes incoming Venmo payments from Gmail
- 🏷️ Filter by categories: Retreat, Dues, or custom keywords
- 📅 Search from specific date/time
- 📊 Exports to CSV (no duplicates on repeated runs)
- 🎨 Modern UI built with Next.js + shadcn/ui

## Prerequisites

- Python 3.13+ with pip
- Node.js with pnpm
- Gmail account

## Setup

### 1. Gmail API Setup (One-time)

**Create Google Cloud Project:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project → Enable **Gmail API** from APIs & Services > Library
3. Go to **APIs & Services** > **Credentials** > **+ CREATE CREDENTIALS** > **OAuth client ID**

**Configure OAuth Consent Screen:**
- User Type: **External**
- Add your Gmail address as a **Test User** (important!)
- Fill in app name and contact emails

**Create Desktop App Credentials:**
- Application type: **Desktop app**
- Download credentials JSON → Rename to `credentials.json`
- Place in `backend/` folder

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
pnpm install
```

## Running the App

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate
python run.py
```
First run will open browser for Gmail OAuth (click Allow).

**Terminal 2 - Frontend:**
```bash
cd frontend
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000)

## Usage

1. **Enter Gmail credentials** (for display only - OAuth handles auth)
2. **Select start date/time** - scraper searches from this point forward
3. **Choose category:**
   - **Retreat** - searches for "retreat" keywords
   - **Dues** - searches for "dues", "membership" keywords
   - **Other** - enter custom keywords (comma-separated)
4. **Click "Run Scraper"**

Results are saved to `backend/venmo_payments.csv`

## CSV Output

**Location:** `backend/venmo_payments.csv`

**Columns:**
- **Person** - Who paid you
- **Date** - Payment timestamp
- **Description** - Payment note
- **Amount** - Payment amount

**Behavior:**
- Only tracks **incoming** payments (money you received)
- No duplicates (detected by Person + Date + Amount)
- Sorted by date (newest first)
- Updates same file on repeated runs

## Notes

- `credentials.json` and `token.pickle` are excluded from git (.gitignore)
- Never commit these files - they contain authentication credentials
- CSV file is also git-ignored
- Scraper only searches emails from `venmo@venmo.com`
