from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def main():
    return "Hello from itsm-agent!"
