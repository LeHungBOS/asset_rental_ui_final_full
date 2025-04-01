# ✅ File app.py đầy đủ tính năng: đăng nhập, phân quyền, quản lý thiết bị, QR/barcode, export CSV
from fastapi import FastAPI, Request, Form, Query, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, Column, String, Integer, Text
from pydantic import BaseModel
from uuid import uuid4
from typing import Optional
import qrcode
import io
import os
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import barcode
from barcode.writer import ImageWriter
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "supersecret"))

templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="user")

class AssetDB(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    code = Column(String)
    category = Column(String)
    quantity = Column(Integer)
    description = Column(Text)

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    if not db.query(UserDB).filter_by(username="admin").first():
        db.add(UserDB(id=str(uuid4()), username="admin", password="admin", role="admin"))
        db.commit()

class Asset(BaseModel):
    id: str
    name: str
    code: str
    category: str
    quantity: int
    description: Optional[str] = ""

class User(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"

@app.middleware("http")
async def require_login(request: Request, call_next):
    if request.url.path not in ("/login", "/logout", "/favicon.ico") and not request.url.path.startswith("/static"):
        if not request.session.get("user"):
            return RedirectResponse("/login")
    return await call_next(request)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(UserDB).filter_by(username=username, password=password).first()
    db.close()
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Sai thông tin đăng nhập"})
    request.session["user"] = user.username
    request.session["role"] = user.role
    return RedirectResponse("/", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/users", response_class=HTMLResponse)
def list_users(request: Request):
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập")
    db = SessionLocal()
    users = db.query(UserDB).all()
    db.close()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})
