from dotenv import load_dotenv


from fastapi import FastAPI

from app.api.api_v1 import router as api_v1

load_dotenv()  # Load .env variables into os.environ for libraries (LangSmith, etc.)


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello from itsm-agent!"}


app.include_router(api_v1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
