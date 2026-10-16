# Mini-Forum (L1)

Skalowalna i bezpieczna platforma wymiany informacji - etap L1: aplikacja bazowa.

Stos: FastAPI + Jinja2 (SSR) + SQLAlchemy + **PostgreSQL**, logowanie JWT w ciasteczku HttpOnly, hasła bcrypt.

## Wymagania

Python 3.10+, Docker (tylko dla bazy PostgreSQL), Git.

## Pierwsze uruchomienie

**Windows (cmd):**

```
git clone https://github.com/MatNycz/Forum_bez.web.git
cd Forum_bez.web
docker compose up -d db
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

**Linux / macOS:**

```
git clone https://github.com/MatNycz/Forum_bez.web.git
cd Forum_bez.web
docker compose up -d db
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Aplikacja: http://localhost:8000, dokumentacja API: http://localhost:8000/docs

Przy pierwszym starcie tabele tworzą się same, a także konto administratora
(login `admin`, hasło `Admin12345!` - domyślne, tylko do developmentu; własne hasło ustaw
w `.env` przez `ADMIN_PASSWORD` przed pierwszym startem albo zmień w zakładce Profil).

## Kolejne uruchomienia

**Windows:**

```
docker compose up -d db
.venv\Scripts\activate
uvicorn app.main:app --reload
```

**Linux / macOS:**

```
docker compose up -d db
source .venv/bin/activate
uvicorn app.main:app --reload
```

Zatrzymanie serwera: `Ctrl+C`. Zatrzymanie bazy: `docker compose stop` (dane zostają w wolumenie).
Wyczyszczenie bazy do zera: `docker compose down -v`.

## Bez Dockera (SQLite)

W pliku `.env` zakomentuj linię z PostgreSQL i odkomentuj `DATABASE_URL=sqlite:///./forum.db`.
Wtedy `docker compose` nie jest potrzebny.

## Konto admina ręcznie

Gdyby nie było admina (np. nazwa `admin` była już zajęta zwykłym kontem):

```
python create_admin.py nazwa email@x.pl
```

## Funkcje (wymagania L1)

- rejestracja i logowanie (sesja przez JWT w ciasteczku HttpOnly, SameSite=Lax)
- wątki w 11 kategoriach, komentarze, lajki wpisów i komentarzy, wyszukiwarka
- użytkownik: profil, zmiana hasła, usuwanie własnych wpisów, komentarzy i konta
- admin: usuwanie dowolnych wpisów i komentarzy, blokowanie i usuwanie kont (`/admin/users`)
- baza: tabele `users`, `posts`, `comments`, `post_likes`, `comment_likes`

## Zespół

Przemysław Babij, Mateusz Nycz, Bartosz Wzorek, Piotr Przychodzeń - grupa 5
