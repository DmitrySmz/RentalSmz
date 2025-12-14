from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, text
from app.database import get_db
from app.dependencies import get_current_user
from app import models, schemas

router = APIRouter()

@router.post("")
def create_order(payload: schemas.RentalOrderCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # begin transaction
    # 1) lock equipment rows FOR UPDATE
    # 2) для каждого equipment_id посчитать уже забронированное на период
    # 3) если хватает — создать order + items, рассчитать total_cost
    ...
