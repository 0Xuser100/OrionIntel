from fastapi import FastAPI
from dotenv import load_dotenv #should we call it before routes to see env variables in routes?
#we should call it in main.py to see env variables in routes
load_dotenv(".env")
from routes import base
app = FastAPI()

app.include_router(base.base_router)
