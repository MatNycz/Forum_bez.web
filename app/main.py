import os
import re
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import security
from .database import SessionLocal, get_db
from .models import Comment, CommentLike, Post, PostLike, User, ensure_schema

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES = [
    "Ogólne",
    "Ogłoszenia",
    "Pytania",
    "Studia",
    "Programowanie",
    "Bezpieczeństwo",
    "Sieci",
    "Chmura i DevOps",
    "Bazy danych",
    "Projekty",
    "Offtopic",
]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")

app = FastAPI(title="Mini-Forum")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


DEFAULT_ADMIN_PASSWORD = "Admin12345!"


def seed_admin() -> None:
    """Przy pierwszym starcie tworzy konto admina, jeśli żadnego jeszcze nie ma."""
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.getenv("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        print("[seed] ADMIN_PASSWORD musi mieć 8-72 bajtów - pomijam tworzenie admina.")
        return
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role == "admin").limit(1)) is not None:
            return
        taken = db.scalar(
            select(User.id).where(or_(User.username == username, User.email == email))
        )
        if taken is not None:
            print(f"[seed] Nazwa lub e-mail '{username}' są zajęte - użyj create_admin.py.")
            return
        db.add(
            User(
                username=username,
                email=email,
                password_hash=security.hash_password(password),
                role="admin",
            )
        )
        db.commit()
    print(f"[seed] Utworzono konto administratora '{username}'.")
    if password == DEFAULT_ADMIN_PASSWORD:
        print("[seed] UWAGA: użyte domyślne hasło - zmień je (Profil) lub ustaw ADMIN_PASSWORD.")


@app.on_event("startup")
def create_tables() -> None:
    ensure_schema()
    seed_admin()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(security.COOKIE_NAME)
    if not token:
        return None
    user_id = security.decode_token(token)
    if user_id is None:
        return None
    found = db.get(User, user_id)
    if found is None or found.is_blocked:
        return None
    return found


def render(request: Request, name: str, user: User | None, status_code: int = 200, **ctx):
    return templates.TemplateResponse(
        request, name, {"user": user, "categories": CATEGORIES, **ctx}, status_code=status_code
    )


def login_required(user: User | None) -> RedirectResponse | None:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return None


def like_state(post: Post, user: User | None) -> dict:
    if user is None:
        return {"liked_post": False, "liked_comments": set()}
    return {
        "liked_post": any(l.user_id == user.id for l in post.likes),
        "liked_comments": {
            c.id for c in post.comments if any(l.user_id == user.id for l in c.likes)
        },
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(
    request: Request,
    q: str = "",
    category: str = "",
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    stmt = select(Post).order_by(Post.created_at.desc())
    if category in CATEGORIES:
        stmt = stmt.where(Post.category == category)
    q = q.strip()[:100]
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Post.title.ilike(pattern), Post.content.ilike(pattern)))
    posts = db.scalars(stmt).all()
    return render(request, "index.html", user, posts=posts, q=q, selected=category)


@app.get("/register")
def register_form(request: Request, user: User | None = Depends(get_current_user)):
    return render(request, "register.html", user, error=None)


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    username, email = username.strip(), email.strip().lower()
    error = None
    if not USERNAME_RE.match(username):
        error = "Nazwa użytkownika: 3-50 znaków (litery, cyfry, _ . -)."
    elif not EMAIL_RE.match(email) or len(email) > 100:
        error = "Podaj poprawny adres e-mail."
    elif len(password) < 8 or len(password.encode("utf-8")) > 72:
        error = "Hasło musi mieć od 8 do 72 bajtów."
    if error:
        return render(request, "register.html", user, status_code=400, error=error)

    new_user = User(
        username=username, email=email, password_hash=security.hash_password(password)
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return render(
            request, "register.html", user, status_code=400,
            error="Taki użytkownik lub e-mail już istnieje.",
        )
    return RedirectResponse("/login", status_code=303)


@app.get("/login")
def login_form(request: Request, user: User | None = Depends(get_current_user)):
    return render(request, "login.html", user, error=None)


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    found = db.scalar(select(User).where(User.username == username.strip()))
    if found is None or not security.verify_password(password, found.password_hash):
        return render(
            request, "login.html", user, status_code=401,
            error="Nieprawidłowa nazwa użytkownika lub hasło.",
        )
    if found.is_blocked:
        return render(
            request, "login.html", user, status_code=403,
            error="To konto zostało zablokowane przez administratora.",
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        security.COOKIE_NAME,
        security.create_token(found.id, found.role),
        max_age=security.TOKEN_TTL_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=security.COOKIE_SECURE,
    )
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(security.COOKIE_NAME)
    return response


@app.get("/posts/new")
def new_post_form(request: Request, user: User | None = Depends(get_current_user)):
    return login_required(user) or render(request, "new_post.html", user, error=None)


@app.post("/posts/new")
def new_post(
    request: Request,
    title: str = Form(...),
    category: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    title, content = title.strip(), content.strip()
    error = None
    if not title or len(title) > 150:
        error = "Tytuł: 1-150 znaków."
    elif category not in CATEGORIES:
        error = "Wybierz poprawną kategorię."
    elif not content or len(content) > 10000:
        error = "Treść: 1-10000 znaków."
    if error:
        return render(request, "new_post.html", user, status_code=400, error=error)

    post = Post(user_id=user.id, title=title, category=category, content=content)
    db.add(post)
    db.commit()
    return RedirectResponse(f"/posts/{post.id}", status_code=303)


@app.get("/posts/{post_id}")
def view_post(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono wpisu")
    return render(request, "post.html", user, post=post, error=None, **like_state(post, user))


@app.post("/posts/{post_id}/comments")
def add_comment(
    request: Request,
    post_id: int,
    content: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono wpisu")
    content = content.strip()
    if not content or len(content) > 2000:
        return render(
            request, "post.html", user, status_code=400, post=post,
            error="Komentarz: 1-2000 znaków.", **like_state(post, user),
        )
    db.add(Comment(post_id=post.id, user_id=user.id, content=content))
    db.commit()
    return RedirectResponse(f"/posts/{post.id}", status_code=303)


@app.post("/posts/{post_id}/like")
def toggle_post_like(
    post_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    if db.get(Post, post_id) is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono wpisu")
    existing = db.get(PostLike, (user.id, post_id))
    if existing:
        db.delete(existing)
    else:
        db.add(PostLike(user_id=user.id, post_id=post_id))
    db.commit()
    return RedirectResponse(f"/posts/{post_id}", status_code=303)


@app.post("/comments/{comment_id}/like")
def toggle_comment_like(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono komentarza")
    existing = db.get(CommentLike, (user.id, comment_id))
    if existing:
        db.delete(existing)
    else:
        db.add(CommentLike(user_id=user.id, comment_id=comment_id))
    db.commit()
    return RedirectResponse(f"/posts/{comment.post_id}", status_code=303)


def can_delete(user: User, owner_id: int) -> bool:
    return user.role == "admin" or user.id == owner_id


@app.post("/posts/{post_id}/delete")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono wpisu")
    if not can_delete(user, post.user_id):
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    db.delete(post)
    db.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/comments/{comment_id}/delete")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono komentarza")
    if not can_delete(user, comment.user_id):
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    post_id = comment.post_id
    db.delete(comment)
    db.commit()
    return RedirectResponse(f"/posts/{post_id}", status_code=303)


def delete_user_account(db: Session, target: User) -> None:
    """Usuwa konto razem z wpisami, komentarzami i lajkami (niezależnie od bazy)."""
    post_ids = select(Post.id).where(Post.user_id == target.id)
    comment_ids = select(Comment.id).where(
        or_(Comment.user_id == target.id, Comment.post_id.in_(post_ids))
    )
    db.execute(
        delete(CommentLike).where(
            or_(CommentLike.user_id == target.id, CommentLike.comment_id.in_(comment_ids))
        )
    )
    db.execute(
        delete(PostLike).where(
            or_(PostLike.user_id == target.id, PostLike.post_id.in_(post_ids))
        )
    )
    db.execute(
        delete(Comment).where(
            or_(Comment.user_id == target.id, Comment.post_id.in_(post_ids))
        )
    )
    db.execute(delete(Post).where(Post.user_id == target.id))
    db.execute(delete(User).where(User.id == target.id))
    db.commit()
    db.expire_all()


def count_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0


def render_profile(request, db, user, status_code=200, message=None, error=None):
    posts_count = db.scalar(
        select(func.count()).select_from(Post).where(Post.user_id == user.id)
    )
    comments_count = db.scalar(
        select(func.count()).select_from(Comment).where(Comment.user_id == user.id)
    )
    return render(
        request, "profile.html", user, status_code=status_code,
        posts_count=posts_count, comments_count=comments_count,
        message=message, error=error,
    )


@app.get("/profile")
def profile(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    return render_profile(request, db, user)


@app.post("/profile/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    if not security.verify_password(current_password, user.password_hash):
        return render_profile(request, db, user, 400, error="Obecne hasło jest nieprawidłowe.")
    if len(new_password) < 8 or len(new_password.encode("utf-8")) > 72:
        return render_profile(
            request, db, user, 400, error="Nowe hasło musi mieć od 8 do 72 bajtów."
        )
    user.password_hash = security.hash_password(new_password)
    db.commit()
    return render_profile(request, db, user, message="Hasło zostało zmienione.")


@app.post("/profile/delete")
def delete_own_account(
    request: Request,
    current_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := login_required(user)) is not None:
        return redirect
    if not security.verify_password(current_password, user.password_hash):
        return render_profile(request, db, user, 400, error="Hasło jest nieprawidłowe.")
    if user.role == "admin" and count_admins(db) <= 1:
        return render_profile(
            request, db, user, 400, error="Nie możesz usunąć jedynego administratora."
        )
    delete_user_account(db, user)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(security.COOKIE_NAME)
    return response


def admin_guard(user: User | None) -> RedirectResponse | None:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    return None


def get_manageable_user(db: Session, admin: User, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono użytkownika")
    if target.id == admin.id or target.role == "admin":
        raise HTTPException(status_code=403, detail="Nie można wykonać tej operacji na administratorze")
    return target


@app.get("/admin/users")
def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := admin_guard(user)) is not None:
        return redirect
    users = db.scalars(select(User).order_by(User.id)).all()
    return render(request, "admin_users.html", user, users=users)


@app.post("/admin/users/{user_id}/block")
def admin_toggle_block(
    user_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := admin_guard(user)) is not None:
        return redirect
    target = get_manageable_user(db, user, user_id)
    target.is_blocked = not target.is_blocked
    db.commit()
    return RedirectResponse("/admin/users", status_code=303)


@app.post("/admin/users/{user_id}/delete")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    if (redirect := admin_guard(user)) is not None:
        return redirect
    target = get_manageable_user(db, user, user_id)
    delete_user_account(db, target)
    return RedirectResponse("/admin/users", status_code=303)
