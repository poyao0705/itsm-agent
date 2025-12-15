from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def main():
    """Main endpoint for the home page"""
    return "Hello from itsm-agent!"
