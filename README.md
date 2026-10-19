# AggieWorks Finance Tracker

Turn incoming Venmo and Zelle payment emails into a spreadsheet of member payments. Built for the AggieWorks Director of Finance to track dues, retreat payments, and other collections from Gmail.

## The problem

Member payments arrive as individual email notifications, while tracking a collection requires a list of who paid, how much, and what it was for. This tool brings those notifications into one CSV, with filters for the collection being tracked and a total at the bottom.

It runs locally on the finance director's computer. Gmail provides the payment notifications; the app extracts and organizes them without needing a direct Venmo or banking integration.

## How it works

**Connect.** Enter the Gmail address that receives payment notifications. On the first scrape, the backend opens Google's OAuth consent flow to request read-only Gmail access. The app never asks for a Gmail password.

**Filter.** Choose Venmo, Zelle, or both, then select a starting date and time. Retreat and dues use preset keywords. Other accepts comma-separated keywords, or includes all matching payments when left blank.

**Extract.** The Python backend searches Gmail and parses incoming payment emails into the sender, date, description, and amount. Venmo support uses notifications from `venmo@venmo.com`; Zelle support targets Wells Fargo notifications from `alerts@notify.wellsfargo.com`.

**Export.** Results are written to `backend/member_to_DoF_payments.csv`, sorted by date with a total row. Repeating the same search accumulates results and removes duplicates using Gmail message IDs and each payment's position within the email. Changing the account, category, keywords, starting date/time, or payment source starts a fresh export so different collections do not get mixed together.

## Tech stack

- **Frontend:** Next.js, React, TypeScript
- **Styling:** Tailwind CSS, shadcn/ui
- **Backend:** Python, FastAPI
- **Email access:** Gmail API with Google OAuth and the `gmail.readonly` scope
- **Storage:** Local CSV export and per-account OAuth token files

## Project structure

```text
.
├── backend/
│   ├── main.py          # scraper API endpoint
│   ├── scraper.py       # Gmail authentication, email parsing, and filtering
│   ├── csv_handler.py   # export, duplicate detection, and search isolation
│   ├── run.py           # local backend entrypoint
│   └── tests/           # regression tests with synthetic data
└── frontend/src/
    ├── app/             # account selection and scraper form
    └── components/ui/   # shared UI components
```

## Local setup

Requires Python 3.13+, Node.js 20.9+, pnpm, and a Gmail account that receives payment notifications.

### Google OAuth

Use your own Google Cloud project; access to an AggieWorks project is not required.

1. Create or select a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Gmail API**.
3. Configure the OAuth consent screen and add your Gmail address as a test user if the app is in testing mode.
4. Create an OAuth client with the **Desktop app** application type. The backend uses a local browser callback for authorization.
5. Download its client configuration and save it as `backend/credentials.json`.

### Backend

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

On Windows, activate the environment with `.venv\Scripts\activate` instead. The backend runs at `http://localhost:8000`.

### Frontend

In a second terminal, from the repository root:

```bash
cd frontend
pnpm install
pnpm dev
```

Open [localhost:3000](http://localhost:3000), enter your Gmail address, choose your filters, and click **Run Scraper**. When Google opens the consent flow, authorize the same Gmail account you entered. Open the resulting CSV from `backend/` in your spreadsheet application.

## Data handling and limitations

- This is a local internal tool with no application-level access control. Keep the backend on your own computer; it is not configured for public hosting or concurrent users.
- Only the selected email address is remembered in browser storage. OAuth tokens stay in `backend/tokens/` so repeated runs can reuse the account's authorization. Clearing the selected account in the UI does not revoke Google access or delete these tokens.
- OAuth credentials, tokens, export data, and search metadata are excluded from Git. Keep them private. Older pickle-format token files are not reused; authorize again to create the current JSON token file.
- The CSV is one current export. Copy it elsewhere before switching searches if you want to retain a collection's results.
- Parsing depends on the supported email formats. Zelle emails from other banks are not supported, and keyword filtering depends on what members write in their payment notes. Review the export against your records.
- Duplicate detection uses stable message IDs when available. Records without an ID fall back to their source, person, timestamp, note, and amount; identical records without IDs can collapse into one row.

## Tests

With the backend virtual environment activated, run from the repository root:

```bash
pip install -r backend/requirements-dev.txt
python -m unittest discover -s backend/tests
```

The tests use synthetic payment data and do not require access to a real Gmail inbox.

For frontend checks:

```bash
cd frontend
pnpm test
pnpm lint
pnpm exec tsc --noEmit
```
