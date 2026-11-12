"""CLI bootstrap script to create an initial EDUCORE PS3 administrator account.

Usage examples:
    python scripts/create_admin.py --username admin.ops --email admin@university.edu --full-name "Operations Admin"
    BOOTSTRAP_ADMIN_PASSWORD="..." python scripts/create_admin.py --username admin.ops --email admin@university.edu --full-name "Operations Admin" --password-env BOOTSTRAP_ADMIN_PASSWORD

Never hardcodes a default password in source code.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import SessionLocal, init_db
from models.schemas import UserCreateRequest
from services.auth_service import create_user_account


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision an EDUCORE PS3 administrator account safely."
    )
    parser.add_argument("--username", required=True, help="Admin username (min 3 chars)")
    parser.add_argument("--email", required=True, help="Admin institutional email")
    parser.add_argument("--full-name", required=True, help="Admin full display name")
    parser.add_argument(
        "--password-env",
        default=None,
        help="Environment variable holding the admin password (if omitted, prompts securely).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password: str | None = None
    if args.password_env:
        password = os.environ.get(args.password_env)
        if not password:
            print(
                f"ERROR: Environment variable '{args.password_env}' is empty or unset.",
                file=sys.stderr,
            )
            return 1
    else:
        first = getpass.getpass("Enter administrator password (min 8 chars, mixed classes): ")
        confirm = getpass.getpass("Confirm administrator password: ")
        if first != confirm:
            print("ERROR: Passwords did not match.", file=sys.stderr)
            return 1
        password = first

    init_db()
    db = SessionLocal()
    try:
        created = create_user_account(
            db=db,
            request=UserCreateRequest(
                username=args.username,
                email=args.email,
                full_name=args.full_name,
                role="administrator",
                password=password,
                is_active=True,
            ),
            actor=None,
            ip_address="cli-bootstrap",
        )
        print(
            f"Created administrator '{created.username}' (id={created.id}, email={created.email})."
        )
        return 0
    except Exception as exc:
        print(f"ERROR: Failed to create administrator: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

