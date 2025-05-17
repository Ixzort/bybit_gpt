BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
#PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os


# Инициализируем клиент pybit (основной Bybit API, testnet=False)
session = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)

app = FastAPI(title="Bybit Trading API", version="1.0")

class OrderRequest(BaseModel):
    symbol: str              # Символ пары (например, "BTCUSDT")
    amount: float = None     # Количество монеты (базовой валюты)
    quote: float = None      # Сумма в USDT (котируемой валюте)

# Функция для расчёта общей стоимости портфеля в USD
def get_total_usd_value():
    total = 0.0
    balances = session.get_wallet_balance(accountType="SPOT")
    for asset in balances['result']['list']:
        coin = asset['coin']
        free = float(asset.get('free', 0) or 0)
        if free <= 0 or coin == "USDT":
            # USDT считаем просто как долларовую стоимость (1:1)
            if coin == "USDT":
                total += free
            continue
        # Запрашиваем текущий тикер (последнюю цену) для пары COIN/USDT
        symbol = f"{coin}USDT"
        ticker = session.get_tickers(category="spot", symbol=symbol)
        price = float(ticker['result']['list'][0]['lastPrice'])
        total += free * price
    return total

# Начальная стоимость портфеля (в USD) при старте приложения
initial_value = get_total_usd_value()

@app.get("/portfolio")
async def get_portfolio():
    """
    GET /portfolio — возвращает все монеты с ненулевым балансом (Spot Unified Account).
    """
    resp = session.get_wallet_balance(accountType="SPOT")
    result = []
    for asset in resp['result']['list']:
        coin = asset['coin']
        free = float(asset.get('free', 0) or 0)
        if free > 0:
            result.append({"coin": coin, "free": free, "locked": float(asset.get('locked', 0) or 0)})
    return {"assets": result}

@app.post("/buy")
async def buy_crypto(req: OrderRequest):
    """
    POST /buy — купить криптовалюту. Можно указать либо количество монеты (amount), либо сумму в USDT (quote).
    """
    if (req.amount is None and req.quote is None) or (req.amount and req.quote):
        raise HTTPException(status_code=400, detail="Нужно указать либо amount, либо quote.")
    params = {
        "category": "SPOT",
        "symbol": req.symbol,
        "side": "Buy",
        "orderType": "Market",
    }
    # Устанавливаем marketUnit в зависимости от типа запроса
    if req.amount:
        params["qty"] = str(req.amount)
        params["marketUnit"] = "baseCoin"    # покупаем заданное количество базовой валюты
    else:
        params["qty"] = str(req.quote)
        params["marketUnit"] = "quoteCoin"   # покупаем на указанную сумму в USDT
    # Отправляем рыночный ордер на покупку
    result = session.place_order(**params)
    return {"result": result.get("result", {})}

@app.post("/sell")
async def sell_crypto(req: OrderRequest):
    """
    POST /sell — продать криптовалюту. Можно указать либо количество (amount), либо сумму в базовой валюте (quote).
    """
    if (req.amount is None and req.quote is None) or (req.amount and req.quote):
        raise HTTPException(status_code=400, detail="Нужно указать либо amount, либо quote.")
    params = {
        "category": "SPOT",
        "symbol": req.symbol,
        "side": "Sell",
        "orderType": "Market",
    }
    if req.amount:
        params["qty"] = str(req.amount)
        params["marketUnit"] = "baseCoin"    # продаём указанное количество монеты
    else:
        params["qty"] = str(req.quote)
        params["marketUnit"] = "quoteCoin"   # продаём на указанную сумму в USDT
    result = session.place_order(**params)
    return {"result": result.get("result", {})}

@app.get("/pnl")
async def get_pnl():
    """
    GET /pnl — рассчитывает PnL (доходность) портфеля с момента старта приложения.
    Возвращает текущую стоимость портфеля в USD, начальную стоимость и разницу (прибыль/убыток).
    """
    current_value = get_total_usd_value()
    diff = current_value - initial_value
    pnl_percent = (diff / initial_value * 100) if initial_value != 0 else 0
    return {
        "initial_usd": initial_value,
        "current_usd": current_value,
        "pnl_usd": diff,
        "pnl_percent": pnl_percent
    }







