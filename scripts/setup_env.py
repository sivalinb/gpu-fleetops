"""Generate a local .env without displaying or overwriting credentials."""

import secrets
from pathlib import Path


def main():
    destination = Path(".env")
    if destination.exists():
        raise SystemExit(".env already exists; existing credentials were preserved")
    content = (
        f"FLEETOPS_API_TOKEN={secrets.token_urlsafe(32)}\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(24)}\n"
        "FLEETOPS_AI_MODE=baseline\n"
        "FLEETOPS_AI_BASE_URL=https://integrate.api.nvidia.com/v1\n"
        "FLEETOPS_AI_MODEL=\nFLEETOPS_AI_API_KEY=\n"
    )
    with destination.open("x") as stream:
        stream.write(content)
    destination.chmod(0o600)
    print("Created .env with local credentials. Git ignores this file.")


if __name__ == "__main__":
    main()
