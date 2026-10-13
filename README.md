# Mini-Forum (L1)

Skalowalna i bezpieczna platforma wymiany informacji - etap L1: aplikacja bazowa.

Stos: FastAPI + Jinja2 (SSR) + SQLAlchemy, PostgreSQL (lub SQLite do szybkiego startu),
logowanie JWT w ciasteczku HttpOnly, hasła bcrypt.

## Pierwsze uruchomienie

Wymagany Python 3.10+ (Docker nie jest potrzebny).

**Windows (cmd):**

```
git clone https://github.com/MatNycz/Forum_bez.web.git
cd Forum_bez.web
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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Aplikacja: http://localhost:8000, dokumentacja API: http://localhost:8000/docs

Przy pierwszym starcie baza i tabele tworzą się same, a także konto administratora
(login `admin`, hasło `Admin12345!` - domyślne, tylko do developmentu; zmień je w zakładce
Profil albo ustaw własne w `.env` przez `ADMIN_PASSWORD` przed pierwszym startem).

## Kolejne uruchomienia

**Windows:**

```
.venv\Scripts\activate
uvicorn app.main:app --reload
```

**Linux / macOS:**

```
source .venv/bin/activate
uvicorn app.main:app --reload
```

Zatrzymanie serwera: `Ctrl+C`. Po `git pull` z nowymi zależnościami uruchom jeszcze raz
`pip install -r requirements.txt`.

## PostgreSQL zamiast SQLite

```
docker compose up -d db
```

W pliku `.env` zakomentuj linię z SQLite i odkomentuj linię z PostgreSQL.

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
