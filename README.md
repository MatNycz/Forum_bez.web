# Mini-Forum (L1)

Skalowalna i bezpieczna platforma wymiany informacji - etap L1: aplikacja bazowa.

Stos: FastAPI + Jinja2 (SSR) + PostgreSQL + SQLAlchemy, logowanie JWT w ciasteczku HttpOnly, hasła bcrypt.

## Uruchomienie lokalne

```bash
cp .env.example .env
docker compose up -d db          # sama baza (pełna konteneryzacja aplikacji to L2)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --reload
```

Aplikacja: http://localhost:8000, dokumentacja API: http://localhost:8000/docs

## Funkcje (wymagania L1)

- rejestracja i logowanie (sesja przez JWT w ciasteczku HttpOnly, SameSite=Lax)
- wątki w kategoriach, komentarze, wyszukiwarka
- baza PostgreSQL: tabele `users`, `posts`, `comments`

## Zespół

Przemysław Babij, Mateusz Nycz, Bartosz Wzorek, Piotr Przychodzeń - grupa 5
