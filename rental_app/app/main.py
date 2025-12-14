# app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth, equipment, rentals, admin
from fastapi.staticfiles import StaticFiles
from .routes import pages
app = FastAPI(title="Rental App", version="0.1.0")

# если Swagger открыт в браузере — куки будут ходить нормально и без этого,
# но CORS не помешает для фронта/шаблонов/отдельного UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(equipment.router)
app.include_router(pages.router)
app.include_router(rentals.router)
app.include_router(admin.router)

