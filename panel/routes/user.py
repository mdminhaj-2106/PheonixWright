from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from panel.controllers.user import get_all_users, create_user_db, get_user_by_id, update_user_db
from panel.database import reset_db

router = APIRouter()
templates = Jinja2Templates(directory="panel/templates")

@router.get("/", response_class=HTMLResponse)
async def user_list(request: Request, q: str = ""):
    users = await get_all_users(q)
    return templates.TemplateResponse(request=request, name="users.html", context={
        "users": users, "q": q
    })

@router.get("/users/create", response_class=HTMLResponse)
async def create_form(request: Request):
    return templates.TemplateResponse(request=request, name="create.html")

@router.post("/users/create")
async def create_user(
    name: str = Form(...),
    email: str = Form(...),
    license: str = Form("none")
):
    user = await create_user_db(name=name, email=email, license=license)
    if not user:
        raise HTTPException(409, "Email already exists")
    return RedirectResponse("/", status_code=303)

@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
        
    return templates.TemplateResponse(request=request, name="detail.html", context={
        "user": user,
        "licenses": ["none", "microsoft365", "google-workspace", "adobe-cc"]
    })

@router.post("/users/{user_id}/update")
async def update_user(
    user_id: int,
    license: str = Form(...),
    password: str = Form(None)
):
    user = await update_user_db(user_id, license, password)
    if not user:
        raise HTTPException(404, "User not found")
            
    return RedirectResponse(f"/users/{user_id}", status_code=303)

@router.post("/reset")
async def reset():
    """Hard reset to known seed state. Use before every demo recording."""
    await reset_db()
    return {"status": "reset complete"}
