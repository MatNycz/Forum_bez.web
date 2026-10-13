"""Tworzy konto administratora (albo nadaje rolę admin istniejącemu kontu).

Użycie:
    python create_admin.py [nazwa] [email]

Domyślnie nazwa = admin. Hasło jest pobierane z promptu (lub ze zmiennej
ADMIN_PASSWORD). Baza zgodnie ze zmienną DATABASE_URL.
"""
import getpass
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, ensure_schema
from app.security import hash_password


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    email = sys.argv[2] if len(sys.argv) > 2 else f"{username}@example.com"

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Hasło admina (min. 8 znaków): ")
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        sys.exit("Hasło musi mieć od 8 do 72 bajtów.")

    ensure_schema()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.role = "admin"
            user.password_hash = hash_password(password)
            action = "Zaktualizowano istniejące konto"
        else:
            db.add(
                User(
                    username=username,
                    email=email.lower(),
                    password_hash=hash_password(password),
                    role="admin",
                )
            )
            action = "Utworzono konto"
        db.commit()
    print(f"{action}: {username} (rola: admin)")


if __name__ == "__main__":
    main()
