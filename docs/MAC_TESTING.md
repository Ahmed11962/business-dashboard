# Test the dashboard on a Mac

This is the same source application as the cloud workspace. The local database is a fresh copy with reproducible sample transactions; cloud data and one-time invitation links do not travel with Git.

## First time

1. Install [Homebrew](https://brew.sh/) if `brew --version` does not work in Terminal. Install Apple's command-line tools if macOS asks for them. Then open Terminal and run:

   ```sh
   brew install git uv
   ```

2. Download the application. Paste these lines into Terminal one at a time:

   ```sh
   cd ~
   git clone https://github.com/Ahmed11962/business-dashboard.git
   cd business-dashboard
   ./scripts/install.sh
   ```

   The first install can take several minutes. It installs Python 3.12 and the locked Python packages, starts a private PostgreSQL database, prepares the dashboard, and adds clearly labeled sample business transactions. You do not need a separate PostgreSQL installation, account, or database password.

3. Create your private invitation using your own email address:

   ```sh
   ./scripts/prepare_local_test.sh YOUR_EMAIL_ADDRESS
   ```

   No email is sent. The one-time link is saved only on your Mac. Sami remains uninvited until his address is supplied.

4. Start the application and leave this Terminal window open:

   ```sh
   ./scripts/start.sh
   ```

5. Open a **second** Terminal window. Run `cd ~/business-dashboard`, then:

   ```sh
   ./scripts/open_local_invitation.sh
   ```

   Your browser opens the private enrollment page. Set a password and enroll an authenticator app for the displayed code. Then sign in. Choose **Test workspace** to explore synthetic payments, outstanding amounts, a saved calculator scenario, an approved decision, and preserved historical purchasing and manufacturing records. The live division stays disabled for financial execution. A fresh joint approval waits for Sami to receive his own invitation; the existing sample decisions show completed two-person approvals.

## Tomorrow and later

Open Terminal and run:

```sh
cd ~/business-dashboard
./scripts/start.sh
```

Open **http://127.0.0.1:8000/login/** in a browser and sign in using the same email, password, and current authenticator code. Closing Terminal stops the app but does not erase its data. The database, uploads, private invitation, and development secret are stored in `~/business-dashboard/.runtime/` and ignored by Git. Keep that folder if you want to retain your local transactions. `./scripts/install.sh` can be rerun after updates; it does not delete your database, and the sample seeder leaves an existing test workspace alone.

Nothing in local testing sends real payments, transfers, statutory invoices, or other external financial actions. The application has no payment, bank, or tax-invoice connection. Sample records are synthetic. Do not use them as authoritative accounts.

## If something fails

- If `brew` is missing, install it from [brew.sh](https://brew.sh/) and reopen Terminal.
- If `git clone` says the destination exists, use `cd ~/business-dashboard` to open the existing copy; do not delete it.
- If port 8000 is busy, close the other app using it, then rerun `./scripts/start.sh`.
- If an invitation expired, ask for a new local invitation before creating a user; do not share the private path publicly.

## Try the manufacturing dashboard on your existing Mac

The finished redesign is on the `manufacturing-workflow` development branch. Your local database and attachments are in `.runtime/`, outside Git. These steps keep them in place. Close the Terminal window running the app, then enter these lines one at a time:

```sh
cd ~/business-dashboard
./scripts/backup_before_upgrade.sh
git status --short
git fetch origin
git switch --track origin/manufacturing-workflow
./scripts/install.sh
./scripts/start.sh
```

`git status --short` should show no source-code changes before switching branches. If `git switch --track` says the branch already exists locally, run `git switch manufacturing-workflow` and then `git pull --ff-only origin manufacturing-workflow`. If any command reports a conflict or failed backup, stop and keep the folder unchanged. Do not delete `.runtime/` or clone over the existing folder.

Open **http://127.0.0.1:8000/login/** and sign in with your existing email, password, and authenticator code. Choose **Test workspace** to explore the synthetic basket mold, production order, accepted inventory, sale, partial collection, and example capital. The live workspace is separate. Creating a local record does not send a payment or issue a statutory tax invoice.

The pre-upgrade dump and SHA-256 file are stored under `~/business-dashboard/.runtime/backups/`. The install script applies additive migrations and adds the basket example only if it is absent from Test. Existing users, documents, records, and audit history remain in the same local PostgreSQL database. Tomorrow, run `cd ~/business-dashboard` and `./scripts/start.sh`, then open the same login URL.

To update this branch later, stop the app and run:

```sh
cd ~/business-dashboard
./scripts/backup_before_upgrade.sh
git pull --ff-only origin manufacturing-workflow
./scripts/install.sh
./scripts/start.sh
```

The dashboard is for internal management testing. Before live financial use, have your accountant confirm the authoritative books and opening balances, have the partners confirm legal funding and distribution terms, and configure a malware scanner for live document previews and downloads. The internal sales PDF is not a verified ZATCA tax invoice.
