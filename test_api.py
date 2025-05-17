BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"

from fastapi import FastAPI
from pybit import usdt_perpetual

app = FastAPI()

client = usdt_perpetual.HTTP(
    endpoint="https://api.bybit.com",
    api_key="mWC5xhURKakJkC9Dri",
    api_secret="xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
)


@app.get("/")
async def read_root():
    return {"message": "Welcome to FastAPI for Bybit trading!"}

