# 📊 PPFAS Flexi Cap Fund Tracker

Automated monthly dashboard & email notifications for **Parag Parikh Flexi Cap Fund (Direct Growth)**.

## What It Does

- **Fetches daily NAV** from MFAPI (AMFI data, free, no auth)
- **Parses PPFAS monthly factsheets** (PDF) for AUM, sector & category allocation
- **Calculates rolling returns** (3-year CAGR)
- **Sends a rich HTML email** with charts, metrics, and a link to the live dashboard
- **Runs automatically** on the 5th of every month via GitHub Actions

## Project Structure

```
ppfas-fund-tracker/
├── main.py                          # Orchestrator — runs the full pipeline
├── config.yaml                      # Fund config, email settings
├── requirements.txt                 # Python dependencies
├── src/
│   ├── nav_fetcher.py               # Fetch NAV history from MFAPI
│   ├── factsheet_parser.py          # Download & parse PPFAS factsheet PDFs
│   ├── returns_calculator.py        # Rolling & point-to-point return calculations
│   ├── email_builder.py             # Generate HTML email with inline charts
│   └── email_sender.py              # Send via Gmail SMTP
├── dashboard/
│   └── app.py                       # Streamlit interactive dashboard
├── data/                            # Generated data (gitignored)
│   ├── nav_history.csv
│   ├── factsheet_data.json
│   └── email_preview.html
└── .github/workflows/
    └── monthly_report.yml           # GitHub Actions cron job
```

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/ppfas-fund-tracker.git
cd ppfas-fund-tracker
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate a Gmail App Password

> **Important:** You need an **App Password**, not your regular Gmail password.

1. Go to [Google Account → Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** → **Other** → Name it "PPFAS Tracker"
5. Copy the 16-character password

### 3. Test Locally (Dry Run)

```bash
# Just generate the email preview (no email sent)
python main.py --dry-run

# Open the preview in your browser
open data/email_preview.html  # macOS
# xdg-open data/email_preview.html  # Linux
```

### 4. Send a Test Email

```bash
export GMAIL_ADDRESS="your-email@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export EMAIL_RECIPIENTS="person1@example.com,person2@example.com"

python main.py
```

### 5. Launch the Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard opens at `http://localhost:8501`.

## Deploy

### Deploy Dashboard to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path**: `dashboard/app.py`
5. Deploy — you'll get a URL like `https://your-app.streamlit.app`
6. Update `DASHBOARD_URL` in your GitHub secrets

### Set Up GitHub Actions (Automated Monthly Emails)

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Add these **Repository Secrets**:

   | Secret Name        | Value                                |
   |--------------------|--------------------------------------|
   | `GMAIL_ADDRESS`    | `your-email@gmail.com`               |
   | `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` (App Password) |
   | `EMAIL_RECIPIENTS` | `person1@example.com,person2@example.com` |
   | `DASHBOARD_URL`    | `https://your-app.streamlit.app`     |

3. The workflow runs automatically on the **5th of every month at 10:00 AM IST**
4. You can also trigger it manually: **Actions** → **Monthly Fund Report** → **Run workflow**

## Configuration

Edit `config.yaml` to customize:

```yaml
fund:
  scheme_code: 122639          # AMFI scheme code
email:
  sender: "your-email@gmail.com"
  recipients:
    - "recipient1@example.com"
    - "recipient2@example.com"
  subject_prefix: "[PPFAS Tracker]"
dashboard:
  url: "https://your-app.streamlit.app"
```

## Email Preview

The monthly email includes:

- 💰 **NAV** and **AUM** as big metric cards
- 📈 **NAV trend chart** (12 months)
- 📊 **Point-to-point returns** (1M, 3M, 6M, 1Y, 3Y, 5Y)
- 🔄 **3-Year rolling return** summary + chart
- 📦 **Category allocation** (Equity/Debt/Cash/Foreign)
- 🏢 **Sector allocation** bar chart
- 🔗 **Link to live dashboard** button

## Data Sources

| Data       | Source | API/Method |
|------------|--------|------------|
| NAV        | AMFI via [mfapi.in](https://www.mfapi.in/) | REST API (free, no auth) |
| Factsheet  | [ppfas.com](https://www.ppfas.com/) | PDF scraping with pdfplumber |

## License

MIT — use freely for personal portfolio tracking.
