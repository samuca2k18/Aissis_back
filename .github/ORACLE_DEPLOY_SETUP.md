# Oracle VM Deploy Setup

This repository deploys to the Oracle VM only after CI passes on pushes to `main`.

## Required GitHub Actions secrets

Configure these secrets in:
`Repository -> Settings -> Secrets and variables -> Actions`

- `ORACLE_VM_HOST`: public IP or host of the Oracle VM.
- `ORACLE_VM_USER`: SSH user on the VM (example: `ubuntu`).
- `ORACLE_VM_SSH_KEY`: private key content for the deploy user.
- `ORACLE_APP_DIR`: absolute path of the backend repo on VM (example: `/home/ubuntu/Aissis_back`).

## VM prerequisites

- The backend repository must already exist in `ORACLE_APP_DIR`.
- The VM user must be able to run `sudo docker compose` (passwordless sudo recommended for CI).
- Port `8000` must be reachable locally on the VM for `http://127.0.0.1:8000/health`.

## Deploy flow

1. Push to `main`.
2. CI runs `ruff`, `mypy`, and `pytest`.
3. If CI passes, workflow connects by SSH.
4. On VM it runs:
   - `git fetch --all --prune`
   - `git checkout main && git pull origin main`
   - `sudo docker compose up -d --build iassis-backend`
   - healthcheck on `/health`
