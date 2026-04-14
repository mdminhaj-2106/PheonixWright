from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from panel.database import init_db
from panel.routes.user import router as user_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="panel/static"), name="static")

app.include_router(user_router)
