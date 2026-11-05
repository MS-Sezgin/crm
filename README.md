# CRM Capstone

A desktop CRM application built with PyQt6 and PostgreSQL. It manages refugee IT candidates: applications, mentor meetings, project interviews and calendar-based reminders.

All data lives in a PostgreSQL database. The old Excel files are loaded into it once with `migrate_excel_to_db.py`. Google Drive is no longer used; Google Calendar and Gmail are still used by the admin menu.

## Features

- **Login** with role check (Admin / User). Passwords are stored as salted hashes.
- **Applications**: all, mentor meeting defined / not defined, name search, and filters for duplicate records, unique names, previous VIT check and different records
- **Mentor Interview**: all conversations, tab filter by recommendation, search by candidate or mentor name
- **Interviews**: project sent / project received, name search
- **Admin Menu**: Google Calendar events in a table, reminder mail to event participants through Gmail
- Every list, search and filter is an SQL query (parameterised, so typed text cannot change a query)
- Modern interface: dark navy side menu (Home, Applications, Mentor Interview, Interviews, Admin Menu for administrators, Log out, Exit), a Home screen with live numbers from the database, icons on every button, a clearly selected filter button, readable read-only tables and a status bar that shows the database connection
- The look is the same in code mode and in `.ui` mode

## Requirements

- Python 3.11 or newer
- PostgreSQL (tested with version 16)
- Windows, macOS or Linux

```
pip install -r requirements.txt
```

## Setup

1. Create an empty database (pgAdmin, or `createdb -U postgres crm_db`).
2. Copy `.env.example` to `.env` and fill in your values. The password is only read from `.env` or from environment variables, never from the source code. `.env` is listed in `.gitignore`.
3. Check the connection: `python check_db.py`
4. Create the tables and load the Excel data (one time). Put the Excel files in a `data/` folder next to the program first:

```
python migrate_excel_to_db.py --create-schema
```

5. Start the application:

```
python main.py          # windows built in Python code
python main.py --ui     # windows loaded from the Qt Designer .ui files
```

Instead of step 4 you can run `database/schema.sql` yourself (`psql -U postgres -d crm_db -f database/schema.sql`) and load your own data.

## Database

Five tables (see `diagram/erd_diagram.png`):

| Table | Content |
|---|---|
| `Kursiyerler` | One row per person, identified by name + e-mail (the e-mail alone is not unique) |
| `Basvurular` | Every application, linked to a person by `KursiyerID`. Old VIT1 / VIT2 lists are stored here too (`BasvuruDonemi`) |
| `Mentortablosu` | Mentor conversations, linked by `KursiyerID` |
| `Mulakatlar` | Project sent / received dates, linked by `KursiyerID` |
| `Kullanicilar` | Login: user name, password hash, role |

Design notes:

- A person is stored once; applications, mentor conversations and interviews point to that person. Exact copies of an application are kept on purpose, because the "Duplicate Records" filter needs them.
- Questionnaire answers are `TEXT` columns, because people write free text (one answer in the real data had 79 characters).
- `basvuru_detay`, `mentor_detay` and `mulakat_detay` are views that show the tables as flat lists.
- The old VIT1 / VIT2 lists are told apart by `PAST_PERIODS` in `data_store.py`. "All Applications" and the mentor-meeting filters show the other applications only.

## Loading the Excel data

```
python migrate_excel_to_db.py --dry-run --create-schema   # try everything, then roll back
python migrate_excel_to_db.py --create-schema             # load for real
python migrate_excel_to_db.py --truncate                  # empty the tables and load again
```

- The Excel files are only read, never changed. A copy goes to `data_backup/` first.
- Everything runs in one transaction. Row counts are compared with the Excel files at the end; if anything differs, nothing is saved.
- A mentor or interview row whose name matches no trainee stops the migration with a list. `--skip-unmatched` leaves such rows out and lists them in the report.
- `migration_report.txt` lists the counts, contact-data conflicts, e-mail addresses shared by several people and skipped rows.

Expected Excel files in `data/`: `Applications.xlsx`, `Interviews.xlsx`, `Mentor.xlsx`, `Users.xlsx`, and optionally `VIT1.xlsx`, `VIT2.xlsx`. Column names are matched by name, with Turkish and English variants.

## Google setup (optional, needed for the admin menu)

1. Create a project in the Google Cloud Console.
2. Enable **Google Calendar API** and **Gmail API**.
3. Configure the OAuth consent screen and add your account as a test user.
4. Create an **OAuth client ID** of type *Desktop app* and download the JSON file.
5. Save it as `credentials/credentials.json`.
6. Open the Admin Menu once and sign in in the browser. `credentials/token.json` is created automatically.

Without this setup everything else works; the admin menu shows a message instead.

## Tests

```
python test_navigation.py
```

The test needs PostgreSQL and the same settings as the application. It builds a temporary schema (`crm_test_<number>`), fills it with sample rows, runs the screens in code mode and in `.ui` mode with fake Google functions, and drops the schema at the end. Your real tables are not touched.

## Building the .exe (Windows)

```
pip install pyinstaller
pyinstaller CRM.spec
```

Put the `.env` file (and `credentials/`, if you use Google) next to `CRM.exe`.

## Project structure

```
main.py                 main window (side menu + pages) and navigation
data_store.py           DataStore: the SQL queries behind every page
database/
  config.py             DbConfig: settings from environment / .env
  connection.py         Database: connection, transactions, queries
  repositories.py       one repository class per table
  security.py           PasswordHasher
  text_utils.py         accent-insensitive text helper
  schema.sql            tables, indexes, views, search function
migrate_excel_to_db.py  one-time Excel -> PostgreSQL migration
check_db.py             database connection check
google_services.py      Google Calendar and Gmail access
styles.py               shared stylesheets (pages, side menu, status bar)
sidebar.py              the dark side menu
icons.py                vector icons drawn from inline SVG (no image files)
pages/                  one module per window (code version); home_base.py = shared home screen
ui/                     one Qt Designer .ui file per window
diagram/                ERD, class diagram, use case diagram (+ .dot sources)
test_navigation.py      database and navigation tests
```

## Authors

- Muhammed Said Sezgin
