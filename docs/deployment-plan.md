# Deployment plan

Status: prepared; public deployment pending.

The event prefers a deployed demo. Local Compose plus complete setup/video is allowed.

## Intended setup

Host FastAPI with server-side Groq/TinyFish secrets and protected persistent FalkorDB.
Use one worker for the current process-lock behavior. Do not expose database or Browser
ports publicly. Bind API to the host's assigned port.

The current app is one synthetic demonstration workspace. Public use needs an explicit
shared-demo notice and request limits, or per-session isolation before representing
it as private user storage. No real applicant documents are accepted.

## Deployment inputs

Choose the user's hosting account and either FalkorDB Cloud or self-hosted DB.
Configure FALKORDB_HOST/PORT/PASSWORD, GROQ_API_KEY and TINYFISH_API_KEY on that host.
Set FALKORDB_SSL=true for a TLS endpoint. Dockerfile uses app.server with the host's
PORT environment variable and one worker. .dockerignore excludes local credentials.
The TinyFish key currently lives in the execution environment; project .env contains Groq.
Do not copy hidden connection credentials to public files.

## Final checks

Live discovery → graph context → plan → receipt → simulated change → acceptance/readback.
Verify restart and source uncertainty on the host. Keep tested local setup as backup.
Prepare everything before any public account/deployment action requiring authorization.

