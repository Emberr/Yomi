"""Bootstrap the first Yomi admin account."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from yomi.config import Settings
from yomi.db.sqlite import initialize_user_db, open_user_db
from yomi.users.repository import active_admin_exists, create_user

USERNAME_ENV = "YOMI_BOOTSTRAP_ADMIN_USERNAME"
DISPLAY_NAME_ENV = "YOMI_BOOTSTRAP_ADMIN_DISPLAY_NAME"
PASSWORD_ENV = "YOMI_BOOTSTRAP_ADMIN_PASSWORD"


class BootstrapAdminError(RuntimeError):
    pass


def bootstrap_admin(
    *,
    user_db_path: Path,
    username: str,
    display_name: str,
    password: str,
) -> int:
    initialize_user_db(user_db_path)
    with open_user_db(user_db_path) as connection:
        if active_admin_exists(connection):
            raise BootstrapAdminError("active admin already exists")

        user = create_user(
            connection,
            username=username,
            display_name=display_name,
            password=password,
            is_admin=True,
            is_active=True,
        )
        connection.commit()
        return user.id


def has_active_admin(user_db_path: Path) -> bool:
    initialize_user_db(user_db_path)
    with open_user_db(user_db_path) as connection:
        return active_admin_exists(connection)


def _prompt_value(prompt: str, env_name: str) -> str:
    value = os.getenv(env_name)
    if value:
        return value
    return input(prompt).strip()


def _prompt_password() -> str:
    value = os.getenv(PASSWORD_ENV)
    if value:
        return value

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm admin password: ")
    if password != confirm:
        raise BootstrapAdminError("password confirmation did not match")
    return password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-db-path", type=Path, default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--display-name", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    user_db_path = args.user_db_path or settings.user_db_path
    if has_active_admin(user_db_path):
        print("Bootstrap refused: active admin already exists", file=sys.stderr)
        return 1

    username = args.username or _prompt_value("Admin username: ", USERNAME_ENV)
    display_name = (
        args.display_name
        or os.getenv(DISPLAY_NAME_ENV)
        or username
    )
    password = _prompt_password()

    try:
        user_id = bootstrap_admin(
            user_db_path=user_db_path,
            username=username,
            display_name=display_name,
            password=password,
        )
    except BootstrapAdminError as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 1

    print(f"Created admin user {username!r} with id {user_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
