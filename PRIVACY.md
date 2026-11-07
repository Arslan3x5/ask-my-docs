# Privacy and offline mode

AskMyDocs is built to run on your own server with no outside services.

## Where your data lives
- Uploaded files are read in memory and **never saved**. Only the extracted text is stored, in the app's own database (`/data/db.sqlite3` in Docker).
- Each user can only see their own workspaces. Deleting a document or a workspace removes its text from the database.

## What is never sent out
- There is no AI model, no analytics, no telemetry and no third-party API in this app.
- Search and answers are computed on your server with plain Python (BM25 keyword ranking).
- **Offline mode is on by default.** While the app runs, any attempt to connect to a non-local host, or to look up a public domain name, fails with an error. Hosts you trust (for example an internal database) can be allowed with `OFFLINE_ALLOW_HOSTS`.

## How you can check this
- Run `python manage.py test`. The tests fail if offline mode stops working, or if the app code starts importing a network library.
- Read `knowledge/offline.py`. It is about 60 lines.
- For the strongest isolation, run the container on a network with no internet access, or block outbound traffic with your firewall. Offline mode is a safety net, not a replacement for network controls.

## What this is not
This is not a compliance certificate. You still need your own security review, HTTPS in front of the app, backups and access controls suited to your documents.