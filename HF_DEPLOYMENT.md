# Deploying GramArogya AI (free) — Hugging Face Space + Neon Postgres

One public link for the professor: a **Hugging Face Docker Space** runs the whole
app (FastAPI serves the React build **and** the API on one URL — no CORS), backed
by a free **Neon** Postgres database that keeps your data between restarts.

Everything on the code side is already prepared: `Dockerfile`, `.dockerignore`,
one-URL frontend serving, and automatic first-boot seeding (`backend/startup_seed.py`).

---

## What you do — step by step

### Step 1 — Push the repo (with the deploy files) to GitHub
From the project folder:
```bash
git add -A
git add -f backend/artifacts/demand_model.joblib   # model is git-ignored by default; deploy needs it
git commit -m "Add deployment setup (Docker, HF Space, startup seeding)"
git push origin develop
```

### Step 2 — Create a free Postgres database (Neon)
1. Go to **https://neon.tech** → sign in with GitHub → **Create project** (name it `gramarogya`).
2. Copy the **connection string**. It looks like:
   `postgresql://user:pass@ep-xxxx.aws.neon.tech/neondb?sslmode=require`
3. **Change the scheme** to what our code expects — replace `postgresql://` with
   `postgresql+psycopg://` (keep the rest, including `?sslmode=require`):
   `postgresql+psycopg://user:pass@ep-xxxx.aws.neon.tech/neondb?sslmode=require`
   Save this — it is your `DATABASE_URL`.

### Step 3 — Create the Hugging Face Space
1. Go to **https://huggingface.co** → sign in → your avatar → **New Space**.
2. Owner = you · Space name = `gramarogya` · License = your choice.
3. **Space SDK = Docker** → choose the **Blank** template.
4. Visibility = **Public** (so the professor can open it) → **Create Space**.

### Step 4 — Add your secrets to the Space
In the Space → **Settings** → **Variables and secrets** → add these **Secrets**:

| Name | Value |
|---|---|
| `DATABASE_URL` | the `postgresql+psycopg://…` string from Step 2 |
| `SECRET_KEY` | any long random string (used to sign login tokens) |
| `ADMIN_USERNAME` | e.g. `admin` (optional — defaults to `admin`) |
| `ADMIN_PASSWORD` | a password you choose (optional — defaults to `admin123`) |
| `GROQ_API_KEY` | *(optional)* your Groq key for AI summaries; blank uses the built-in fallback |

### Step 5 — Push your code to the Space
A Space is its own git repo. Point your project at it and push. Replace
`<user>` with your HF username:
```bash
git remote add space https://huggingface.co/spaces/<user>/gramarogya
git push space develop:main            # HF Spaces build from the "main" branch
```
When prompted for a password, paste a **Hugging Face access token** with *write*
permission (create one at https://huggingface.co/settings/tokens).

### Step 6 — Watch it build, then open the link
- The Space shows a **Building** log (installing Python deps + building the React app — a few minutes the first time).
- On first boot it auto-creates the tables, loads the data from the CSVs, and creates your admin login.
- When it says **Running**, open the Space URL: `https://<user>-gramarogya.hf.space`
- Log in with the `ADMIN_USERNAME` / `ADMIN_PASSWORD` you set (or `admin` / `admin123`).

**Done — that URL is what you send the professor.**

---

## Updating the deployed app later
Make changes → push to GitHub → then push to the Space again:
```bash
git push origin develop
git push space develop:main
```
The Space rebuilds automatically.

---

## Good to know
- **Sleeping:** a free Space sleeps after ~48 h of no visitors and takes ~30–60 s
  to wake on the next visit. Before a graded demo, open it once yourself to warm it up.
- **Your data persists** in Neon, so audit entries, approved rosters, etc. survive
  restarts. (Seeding only runs when the database is empty.)
- **Reset to a clean demo state:** in Neon, drop the tables (or the branch) and
  restart the Space — it will re-seed from the CSVs.
- **Troubleshooting:** the Space **Logs** tab shows build and runtime errors. The
  most common issue is a wrong `DATABASE_URL` (make sure the scheme is
  `postgresql+psycopg://` and it ends with `?sslmode=require`).

---

## Alternative host (if HF ever misbehaves)
The exact same image runs on **Render** (free web service) or **Railway** — connect
the GitHub repo, it detects the `Dockerfile`, and you set the same environment
variables. Render's free tier has less memory (512 MB) and sleeps after 15 min, so
HF Spaces (16 GB RAM) is the better fit for this ML workload.
