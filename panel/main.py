from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from panel.database import init_db, reset_db, AsyncSessionLocal, User

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="panel/templates")

@app.get("/", response_class=HTMLResponse)
async def user_list(request: Request, q: str = ""):
    async with AsyncSessionLocal() as session:
        stmt = select(User)
        if q:
            # Using icontains for easy generalized searching
            stmt = stmt.where(or_(User.name.icontains(q), User.email.icontains(q)))
        result = await session.execute(stmt)
        users = result.scalars().all()
        
    return templates.TemplateResponse("users.html", {
        "request": request, "users": users, "q": q
    })

@app.get("/users/create", response_class=HTMLResponse)
async def create_form(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})

@app.post("/users/create")
async def create_user(
    name: str = Form(...),
    email: str = Form(...),
    license: str = Form("none")
):
    async with AsyncSessionLocal() as session:
        new_user = User(name=name, email=email, license=license)
        session.add(new_user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(409, "Email already exists")
            
    return RedirectResponse("/", status_code=303)

@app.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        
    if not user:
        raise HTTPException(404, "User not found")
        
    return templates.TemplateResponse("detail.html", {
        "request": request, "user": user,
        "licenses": ["none", "microsoft365", "google-workspace", "adobe-cc"]
    })

@app.post("/users/{user_id}/update")
async def update_user(
    user_id: int,
    license: str = Form(...),
    password: str = Form(None)
):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user:
            user.license = license
            if password:  # Handled: skip if password is empty/none
                user.password = password
            await session.commit()
            
    return RedirectResponse(f"/users/{user_id}", status_code=303)

@app.post("/reset")
async def reset():
    """Hard reset to known seed state. Use before every demo recording."""
    await reset_db()
    return {"status": "reset complete"}
