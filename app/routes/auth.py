from fastapi import APIRouter, Depends

from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "user_id": current_user["id"],
        "email": current_user["email"],
    }