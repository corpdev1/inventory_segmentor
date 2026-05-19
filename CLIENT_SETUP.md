# Inventory Segmentor — Client Setup Guide

Follow every step in order. Each command is on its own line — copy it exactly as shown.

---

## Prerequisites

Before starting, make sure you have the following installed on your computer.

### 1. Install Python

1. Open your browser and go to: **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button.
3. Open the downloaded file and run the installer.
   - **Important:** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install.
4. When the installer finishes, click **Close**.

Verify it worked — open **Terminal** (Mac) or **Command Prompt** (Windows) and run:

```
python --version
```

You should see something like `Python 3.12.x`. If you see an error, restart your computer and try again.

---

### 2. Install Git

1. Go to: **https://git-scm.com/downloads**
2. Download and run the installer for your operating system.
3. Accept all default options during installation.

Verify it worked:

```
git --version
```

You should see something like `git version 2.x.x`.

---

## Part 1 — Get the Code

Open **Terminal** (Mac: press `Cmd + Space`, type `Terminal`, press Enter) or **Command Prompt** (Windows: press `Win + R`, type `cmd`, press Enter).

Run these commands one at a time, pressing Enter after each:

**Step 1 — Go to your home folder:**

```
cd ~
```

**Step 2 — Clone (download) the project:**

```
git clone https://github.com/YOUR_ORG/inventory-segmentor.git
```

> Replace `https://github.com/YOUR_ORG/inventory-segmentor.git` with the exact link provided to you.

**Step 3 — Enter the project folder:**

```
cd inventory-segmentor
```

---

## Part 2 — Set Up the Python Environment

**Step 4 — Create a virtual environment (isolated workspace for the tool):**

Mac / Linux:
```
python3 -m venv .venv
```

Windows:
```
python -m venv .venv
```

**Step 5 — Activate the environment:**

Mac / Linux:
```
source .venv/bin/activate
```

Windows:
```
.venv\Scripts\activate
```

After this step you will see `(.venv)` at the start of your terminal line. That means it worked.

**Step 6 — Install the required packages:**

```
pip install -r requirements.txt
```

This will take 1–3 minutes. Wait for it to finish before moving on.

---

## Part 3 — Add Your API Key

The tool uses an AI model (Claude by Anthropic) to read and classify your files. You need an API key.

**Getting an Anthropic API key (if you don't have one):**

1. Go to: **https://console.anthropic.com/**
2. Sign up or log in.
3. Click **API Keys** in the left sidebar.
4. Click **Create Key**, give it any name, and copy the key (it starts with `sk-ant-`).

**Step 7 — Open the `.env` file in a text editor:**

Mac:
```
open -a TextEdit .env
```

Windows:
```
notepad .env
```

**Step 8 — Find this line in the file:**

```
ANTHROPIC_API_KEY=
```

Paste your API key directly after the `=` sign, with no spaces:

```
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
```

Save the file (`Cmd + S` on Mac, `Ctrl + S` on Windows) and close it.

---

## Part 4 — Google Drive Credentials (if scanning Google Drive)

Skip this part if you are only scanning a **local folder** on your computer. Jump to Part 5.

### Get the OAuth credentials file from Google Cloud

You should have received a file named something like `client_secret_xxxx.json` or `google_oauth_client.json`. This file is typically in your **Downloads** folder.

**Step 9 — Run the setup wizard:**

```
python setup.py
```

The wizard will ask you two questions:

**Question 1 — API key:**
Press `Enter` to keep the key you already set in Step 8.

**Question 2 — Google Drive access:**
Type `y` and press `Enter`.

When it asks:
```
Path to OAuth client JSON file:
```

Type the path to the credentials file. If it is in your Downloads folder:

Mac:
```
~/Downloads/client_secret_xxxx.json
```

Windows:
```
C:\Users\YourName\Downloads\client_secret_xxxx.json
```

> Replace `client_secret_xxxx.json` with the exact filename of the file you received.

**Question 3 — Authorize Google Drive:**
Type `y` and press `Enter`. A browser tab will open. Sign in with the Google account that has access to the Drive you want to scan. Click **Allow** when prompted.

When the browser shows a success message, return to the terminal. You will see:
```
→ Google Drive authorized successfully.
```

---

## Part 5 — Run the Tool

### Option A — Scan a local folder on your computer

**Step 10 — Point the tool at your data folder:**

Mac / Linux:
```
python run_dump.py --dump ~/Downloads/company-files --out out/inventory.xlsx
```

Windows:
```
python run_dump.py --dump C:\Users\YourName\Downloads\company-files --out out\inventory.xlsx
```

> Replace `~/Downloads/company-files` (or the Windows equivalent) with the actual path to the folder containing your company's files.

---

### Option B — Scan your entire Google Drive / Workspace

**Step 10 — Scan all drives:**

```
python run_drive.py --all-drives --out out/drive_inventory.xlsx
```

**Option B2 — Scan a specific folder only:**

```
python run_drive.py --folder-id "https://drive.google.com/drive/folders/PASTE_FOLDER_URL_HERE" --out out/drive_inventory.xlsx
```

> Paste the full URL of the Google Drive folder you want to scan between the quotes.

---

## Part 6 — Find Your Output

When the scan finishes, the output file will be in the `out/` folder inside the project:

Mac:
```
open out/
```

Windows:
```
explorer out
```

Open the `.xlsx` file with Excel or Google Sheets. It contains:
- A **Master** sheet with every file
- One sheet per category (Product & Engineering, Customer & Sales, etc.)
- A **Summary** sheet with counts and totals

---

## Resuming an Interrupted Scan

If the scan stops midway (internet cut out, computer sleep, etc.), just run the **exact same command** again. The tool saves its progress automatically and will pick up where it left off.

---

## Common Issues

| Problem | Fix |
|---|---|
| `python: command not found` | Use `python3` instead of `python`, or reinstall Python with "Add to PATH" checked |
| `(.venv)` not showing | Re-run Step 5 (activate the environment) |
| `No module named ...` | Re-run Step 6 (install packages) |
| `AuthenticationError` or `Invalid API key` | Double-check the key in `.env` — no spaces, no quotes around it |
| Google login fails | Make sure you are signing in with the correct Google account, and that the OAuth credentials file is a **Desktop app** type |
| Scan seems slow | Normal — each file is read by an AI. A 1,000-file drive takes ~10–20 minutes |

---

## Updating the Tool

To pull the latest version of the code, run these two commands:

```
git pull
pip install -r requirements.txt
```

Your `.env` and credentials are not affected by updates.
