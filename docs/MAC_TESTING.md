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

   Your browser opens the private enrollment page. Set a password and enroll an authenticator app for the displayed code. Then sign in. Choose **Test workspace** to explore the synthetic purchasing, mold, manufacturing, inventory, sales, accounting, profit-sharing, and approval records. The live division stays disabled for financial execution. A fresh joint approval waits for Sami to receive his own invitation; the existing sample decisions show completed two-person approvals.

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
