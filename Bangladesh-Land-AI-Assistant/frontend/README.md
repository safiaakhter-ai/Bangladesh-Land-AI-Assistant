# Frontend

Next.js 16 / React 19 / Tailwind 4 application for the Bangladesh Land AI Assistant.

From the repository root, start the Python API first (`python app.py` in an environment
with `requirements.txt` installed). Then run `npm ci && npm run dev` in this folder.

The frontend uses same-origin `/api/*` requests. Configure `BACKEND_URL` in
`frontend/.env.local` if the API does not use `http://127.0.0.1:5000`.

`npm run lint` and `npm run build` are the front-end quality checks.
See the repository root README for data, AI and legal limitations.
