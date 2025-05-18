from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pybit.unified_trading import HTTP


from fastapi.responses import HTMLResponse
from fastapi import FastAPI

app = FastAPI()

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Политика конфиденциальности</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <h1>Политика конфиденциальности</h1>
        <p>Последнее обновление: 18 мая 2025</p>
        <p>Мы уважаем вашу конфиденциальность. Это приложение не собирает, не хранит и не передаёт персональные данные пользователей. 
        Все запросы обрабатываются локально и через официальное API Bybit без стороннего хранения данных.</p>
        <p>Если у вас есть вопросы, вы можете связаться с разработчиком по адресу электронной почты: <a href="mailto:example@email.com">example@email.com</a>.</p>
    </body>
    </html>
    """


# 🔐 Bybit API Testnet ключи
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"

# 🚀 FastAPI + pybit с Testnet
app = FastAPI(title="Bybit GPT Testnet API")
session = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)

# 💰 Сохраняем стартовое значение для PnL
initial_portfolio_usd = 0.0


@app.on_event("startup")
def fetch_initial_portfolio_value():
    global initial_portfolio_usd
    try:
        balance = session.get_wallet_balance(accountType="UNIFIED")
        total = sum(
            float(c.get("usdValue", 0) or 0)
            for c in balance["result"]["list"][0]["coin"]
        )
        initial_portfolio_usd = round(total, 2)
        print(f"🔢 Стартовый портфель: {initial_portfolio_usd} USDT")
    except Exception as e:
        print("⚠️ Ошибка при загрузке стартового баланса:", e)


# 📦 Запрос для торговли
class OrderRequest(BaseModel):
    symbol: str
    amount: Optional[float] = None
    quote: Optional[float] = None


def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


@app.get("/portfolio")
def get_portfolio():
    try:
        balance = session.get_wallet_balance(accountType="UNIFIED")
        return balance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pnl")
def get_pnl():
    try:
        balance = session.get_wallet_balance(accountType="UNIFIED")
        current_total = sum(
            float(c.get("usdValue", 0) or 0)
            for c in balance["result"]["list"][0]["coin"]
        )
        pnl_usd = current_total - initial_portfolio_usd
        pnl_percent = (pnl_usd / initial_portfolio_usd) * 100 if initial_portfolio_usd else 0
        return {
            "initial_usd": round(initial_portfolio_usd, 2),
            "current_usd": round(current_total, 2),
            "pnl_usd": round(pnl_usd, 2),
            "pnl_percent": round(pnl_percent, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчета PnL: {e}")


def place_order(side: str, req: OrderRequest):
    if not req.amount and not req.quote:
        raise HTTPException(status_code=400, detail="Укажи либо amount, либо quote")

    if req.amount and req.quote:
        raise HTTPException(status_code=400, detail="Нельзя одновременно указать amount и quote")

    params = {
        "category": "spot",
        "symbol": req.symbol,
        "side": side,
        "orderType": "Market"
    }

    if req.amount:
        params["qty"] = str(req.amount)
        params["marketUnit"] = "baseCoin"
    else:
        params["qty"] = str(req.quote)
        params["marketUnit"] = "quoteCoin"

    if side == "Sell" and req.amount:
        try:
            coin = req.symbol.replace("USDT", "")
            balance = session.get_wallet_balance(accountType="UNIFIED")
            coin_list = balance["result"]["list"][0]["coin"]
            match = next((c for c in coin_list if c["coin"] == coin), None)
            available = safe_float(match["availableToWithdraw"]) if match else 0.0

            if available < req.amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недостаточно {coin} на счету (доступно: {available})"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при проверке баланса: {e}")

    try:
        return session.place_order(**params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отправки ордера: {e}")


@app.post("/buy")
def buy(req: OrderRequest):
    return place_order("Buy", req)


@app.post("/sell")
def sell(req: OrderRequest):
    return place_order("Sell", req)


@app.get("/openapi.yaml")
def get_openapi_yaml():
    return FileResponse("openapi.yaml", media_type="text/yaml")

