# ReMa Procurement Tracker (Streamlit)

A starter web app based **only on the `Procurement` worksheet** in `ReMa Tracker_09102026.xlsx`. It does not import, query, or display the `Balance Sheet` worksheet.

## Features
- Procurement dashboard with stock cost, sold revenue, gross profit, and pending payments
- Inventory search and filters
- Add new sarees to inventory
- Edit existing records and record sales
- CSV export
- Local SQLite storage for development, with optional Supabase storage for hosted persistence

## Run locally

1. Install Python 3.10 or later.
2. Open a terminal in this folder.
3. Create a virtual environment (recommended), then run:

   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

4. The app opens in your browser. In local mode, records are stored in `procurement.db` in this folder. The initial records are loaded from `procurement_seed.csv` only when the database is empty.

## Host on Streamlit Community Cloud

1. Create a private GitHub repository and upload the contents of this folder. Keep `procurement.db`, `.env`, and `.streamlit/secrets.toml` out of Git.
2. For durable cloud storage, create a Supabase project and run `supabase_schema.sql` in its SQL Editor.
3. In Supabase, configure appropriate Row Level Security policies for your chosen authentication setup. Do not expose a `service_role` key in a public repository or browser code. For a personal private app, protect access to the Streamlit app and use secrets securely.
4. In Streamlit Community Cloud, deploy the repository with `app.py` as the main file.
5. In the app's **Settings → Secrets**, add:

   ```toml
   SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
   SUPABASE_KEY = "YOUR-APPROPRIATE-SERVER-SIDE-KEY"
   ```

   Use a key appropriate for server-side access and ensure database permissions/RLS are configured before adding real financial data. The app will use Supabase when these secrets are present; otherwise, it uses local SQLite.

**Important:** Streamlit Community Cloud local files may not be durable across restarts/redeploys. Do not use local SQLite mode for your only copy of business records on a hosted deployment. Configure persistent storage and make backups.

## Data interpretation
- `Cost price` is treated as procurement cost.
- For revenue and gross profit, the app uses `Discount/ Final Price` when populated, otherwise `Selling Price`.
- Calculated gross profit is effective sale price minus cost price. It is not an accounting or tax report.
- Existing sheet rows labelled `Sold` stay sold; other valid inventory rows start as `In Stock`.
- Repeated header lines, totals, and blank rows in the original worksheet are excluded from the seed data.
- The source sheet does not provide a purchase date for each item; this field is optional for new entries.
