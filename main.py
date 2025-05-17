from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pybit.unified_trading import HTTP

# 🔐 Ключи Testnet Bybit
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"

# Инициализация FastAPI и pybit с testnet=True
app = FastAPI(title="Bybit GPT Testnet API")
session = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)


# 📦 Модель запроса для покупки и продажи
class OrderRequest(BaseModel):
    symbol: str
    amount: float | None = None  # Кол-во монет
    quote: float | None = None   # Сумма в USDT


@app.get("/portfolio")
def get_portfolio():
    try:
        balance = session.get_wallet_balance(accountType="UNIFIED")
        return balance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def place_order(side: str, req: OrderRequest):
    if not req.amount and not req.quote:
        raise HTTPException(status_code=400, detail="Нужно указать amount или quote")

    if req.amount and req.quote:
        raise HTTPException(status_code=400, detail="Укажи только одно: amount или quote")

    params = {
        "category": "spot",
        "symbol": req.symbol,
        "side": side,
        "orderType": "Market",
    }

    if req.amount:
        params["qty"] = str(req.amount)
        params["marketUnit"] = "baseCoin"
    else:
        params["qty"] = str(req.quote)
        params["marketUnit"] = "quoteCoin"

    # 💰 При продаже — проверим, есть ли нужное количество
    if side == "Sell" and req.amount:
        try:
            coin = req.symbol.replace("USDT", "")  # ETHUSDT → ETH
            balance = session.get_wallet_balance(accountType="UNIFIED")
            coin_list = balance["result"]["list"][0]["coin"]
            match = next((c for c in coin_list if c["coin"] == coin), None)
            if not match or float(match["availableToWithdraw"]) < req.amount:
                raise HTTPException(status_code=400, detail=f"Недостаточно {coin} на счету")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при проверке баланса: {e}")

    try:
        return session.place_order(**params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка ордера: {e}")


@app.post("/buy")
def buy(req: OrderRequest):
    return place_order("Buy", req)


@app.post("/sell")
def sell(req: OrderRequest):
    return place_order("Sell", req)


# 📄 OpenAPI YAML отдаём статично
from fastapi.responses import FileResponse

@app.get("/openapi.yaml")
def get_openapi_yaml():
    return FileResponse("openapi.yaml", media_type="text/yaml")
