# AggieWorks Payment Tracker

Turn Venmo and Zelle payment emails into a spreadsheet of member payments.

## The problem

At AggieWorks, the Director of Finance manually tracked incoming payments and tagged what each covered, such as dues or a retreat. This was repetitive work.

While President of AggieWorks, I built this tool to automate that process using Gmail notifications.

## How it works

**Connect.** Enter the Gmail address that receives payment notifications. On the first scrape, authorize read-only Gmail access through Google's OAuth consent flow.

**Filter.** Choose Venmo, Zelle, or both, then select a starting date and time. Retreat and dues use preset keywords. Other accepts comma-separated keywords, or includes all matching payments when left blank.

**Extract.** The backend searches Gmail and extracts the sender, date, description, and amount from Venmo and Wells Fargo Zelle notifications.

**Export.** Results are written to `backend/member_to_DoF_payments.csv`, sorted by date with a total row. Repeating the same search adds new payments without duplicating existing results. Changing the account or filters starts a fresh export.

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
- The selected email address stays in browser storage; OAuth tokens stay in `backend/tokens/`. Clearing the selected account does not revoke Google access or delete its tokens.
- OAuth credentials, tokens, export data, and search metadata are excluded from Git. Keep them private.
- The CSV is one current export. Copy it elsewhere before switching searches if you want to retain a collection's results.
- Parsing depends on the supported email formats. Zelle emails from banks other than Wells Fargo are not supported.
- Categories use keywords in payment notes, so ambiguous or missing notes still need manual review. Review the export against your records.

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

## License

Licensed under the [MIT License](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md) for attribution.
