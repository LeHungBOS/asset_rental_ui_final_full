# ✅ File chuyển sang dùng PostgreSQL với SQLAlchemy và phân quyền user/admin
from fastapi import FastAPI, Request, Form, Query, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import create_engine, Column, String, Integer, Text
from pydantic import BaseModel
from uuid import uuid4
from typing import Optional
from pathlib import Path
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

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://user:password@localhost/asset_db")
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

@app.get("/users", response_class=HTMLResponse)
def list_users(request: Request):
    admin_required(request)
    db = SessionLocal()
    users = db.query(UserDB).all()
    db.close()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.get("/users/add", response_class=HTMLResponse)
def add_user_form(request: Request):
    admin_required(request)
    return templates.TemplateResponse("user_form.html", {"request": request})

@app.post("/users/add")
def add_user(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form("user")):
    admin_required(request)
    db = SessionLocal()
    user = UserDB(id=str(uuid4()), username=username, password=password, role=role)
    db.add(user)
    db.commit()
    db.close()
    return RedirectResponse("/users", status_code=302)

@app.get("/users/edit/{user_id}", response_class=HTMLResponse)
def edit_user_form(request: Request, user_id: str):
    admin_required(request)
    db = SessionLocal()
    user = db.query(UserDB).filter_by(id=user_id).first()
    db.close()
    return templates.TemplateResponse("user_form.html", {"request": request, "user": user})

@app.post("/users/edit/{user_id}")
def update_user(request: Request, user_id: str, username: str = Form(...), password: str = Form(...), role: str = Form(...)):
    admin_required(request)
    db = SessionLocal()
    user = db.query(UserDB).filter_by(id=user_id).first()
    if user:
        user.username = username
        user.password = password
        user.role = role
        db.commit()
    db.close()
    return RedirectResponse("/users", status_code=302)

@app.get("/users/delete/{user_id}")
def delete_user(request: Request, user_id: str):
    admin_required(request)
    db = SessionLocal()
    user = db.query(UserDB).filter_by(id=user_id).first()
    if user:
        db.delete(user)
        db.commit()
    db.close()
    return RedirectResponse("/users", status_code=302)

@app.get("/change-password", response_class=HTMLResponse)
def change_password_form(request: Request):
    return templates.TemplateResponse("change_password.html", {"request": request})

@app.post("/change-password")
def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    username = request.session.get("user")
    db = SessionLocal()
    user = db.query(UserDB).filter_by(username=username, password=old_password).first()
    if not user:
        return templates.TemplateResponse("change_password.html", {"request": request, "error": "Sai mật khẩu hiện tại"})
    user.password = new_password
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=302)
