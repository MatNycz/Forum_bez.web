import re
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import security
from .database import Base, engine, get_db
from .models import Comment, Post, User

BASE_DIR = Path(__file__).resolve().parent
CATEGORIES = ["Ogólne", "Pytania", "Projekty", "Bezpieczeństwo", "Offtopic"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")

app = FastAPI(title="Mini-Forum")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(security.COOKIE_NAME)
    if not token:
        return None
    user_id = security.decode_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def render(request: Request, name: str, user: User | None, status_code: int = 200, **ctx):
    return templates.TemplateResponse(
        request, name, {"user": user, "categories": CATEGORIES, **ctx}, status_code=status_code
    )


def login_required(user: User | None) -> RedirectResponse | None:
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return None


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
    return render(request, "post.html", user, post=post, error=None)


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
            error="Komentarz: 1-2000 znaków.",
        )
    db.add(Comment(post_id=post.id, user_id=user.id, content=content))
    db.commit()
    return RedirectResponse(f"/posts/{post.id}", status_code=303)
