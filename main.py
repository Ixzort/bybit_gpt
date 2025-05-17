BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"


from fastapi import FastAPI
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

load_dotenv()  # загружаем .env

app = FastAPI()

# Инициализация Bybit-сессии
session = HTTP(
    testnet=True,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

@app.get("/portfolio")
async def get_portfolio():
    # Возвращает баланс монет с ненулевым значением (UNIFIED account)
    balance = session.get_wallet_balance(accountType="UNIFIED")
    return balance  # Pybit возвращает уже JSON-подобный словарь

@app.get("/buy")
async def buy_btc():
    # Маркет-ордер: купить BTC на сумму 100 USDT
    # Для покупки по стоимости (USD) передаём marketUnit="quoteCoin"
    order = session.place_order(
        category="spot",
        symbol="BTCUSDT",
        side="Buy",
        orderType="Market",
        qty="100",
        marketUnit="quoteCoin"  # указывает, что qty = 100 USDT
    )
    return order

@app.get("/sell")
async def sell_eth():
    # Маркет-ордер: продать 0.01 ETH
    order = session.place_order(
        category="spot",
        symbol="ETHUSDT",
        side="Sell",
        orderType="Market",
        qty="0.01"
    )
    return order

from fastapi.responses import FileResponse

@app.get("/openapi.yaml")
def get_openapi_yaml():
    return FileResponse("openapi.yaml", media_type="text/yaml")






