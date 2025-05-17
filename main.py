# main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pybit.unified_trading import HTTP as BybitHTTP

# ==== Конфигурация ключей ====
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

# ==== Инициализация ====
app = FastAPI(title="Bybit Crypto Assistant", version="1.0")

# Аутентификация: Bearer token
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token != PLUGIN_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# Подключение к Bybit Testnet
session = BybitHTTP(
    testnet=True,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

# Сохраняем начальный баланс для расчета PnL
initial_balance = 0.0

@app.on_event("startup")
def startup_event():
    global initial_balance
    try:
        wallet = session.get_wallet_balance(accountType="UNIFIED")
        initial_balance = float(wallet["result"]["list"][0]["totalWalletBalance"])
    except Exception as e:
        print("Не удалось получить начальный баланс:", e)

@app.get("/portfolio", dependencies=[Depends(verify_api_key)])
def get_portfolio():
    """Получить текущие балансы портфеля."""
    try:
        return session.get_wallet_balance(accountType="UNIFIED")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запроса: {e}")

@app.post("/buy", dependencies=[Depends(verify_api_key)])
def buy(symbol: str, amount: float):
    """Купить по рынку: сумма в валюте котировки."""
    try:
        order = session.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=str(amount),
            timeInForce="IOC",
            orderFilter="Order",
            isLeverage=0
        )
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка покупки: {e}")

@app.post("/sell", dependencies=[Depends(verify_api_key)])
def sell(symbol: str, amount: float):
    """Продать по рынку: сумма в базовой валюте."""
    try:
        order = session.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=str(amount),
            timeInForce="IOC",
            orderFilter="Order",
            isLeverage=0
        )
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка продажи: {e}")

@app.get("/pnl", dependencies=[Depends(verify_api_key)])
def get_pnl():
    """Вычислить текущий PnL по сравнению с изначальным балансом."""
    try:
        wallet = session.get_wallet_balance(accountType="UNIFIED")
        current_total = float(wallet["result"]["list"][0]["totalWalletBalance"])
        pnl_value = current_total - initial_balance
        return {
            "initial_portfolio_usd": initial_balance,
            "current_portfolio_usd": current_total,
            "pnl_usd": pnl_value,
            "pnl_percent": round((pnl_value / initial_balance) * 100, 2) if initial_balance > 0 else 0.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка PnL: {e}")




