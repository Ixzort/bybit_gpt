BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os
from pybit.unified_trading import HTTP as BybitSession

app = FastAPI(title="Bybit Crypto Assistant")
security = HTTPBearer()

BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"


# Инициализируем сессию Bybit Unified Account
bybit_session = BybitSession(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET,
    endpoint="https://api.bybit.com"  # или тестовый https://api-testnet.bybit.com
)

# Словарь для хранения начального портфеля в USD
initial_portfolio_usd = {"total": 0.0}

# Класс модели для запроса на покупку
class BuyRequest(BaseModel):
    symbol: str
    amount: float

@app.on_event("startup")
def load_initial_portfolio():
    """
    При старте приложения получаем начальный портфель (суммарный баланс)
    для дальнейшего расчёта PnL.
    """
    resp = bybit_session.get_wallet_balance(accountType="UNIFIED")
    # resp возвращает структуру {'result': {'totalWalletBalance': "...", ...}, ...}
    total_balance_usd = float(resp['result']['totalWalletBalance'])
    initial_portfolio_usd['total'] = total_balance_usd

def check_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Проверка Bearer-токена для защищённых эндпоинтов.
    """
    if credentials.credentials != API_BEARER_TOKEN:
        raise HTTPException(status_code=403, detail="Недействительный токен")

@app.get("/portfolio")
def get_portfolio(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Возвращает список монет в спотовом портфеле с ненулевым балансом.
    Данные берутся из Unified Account (категория Spot).
    """
    check_token(credentials)
    data = bybit_session.get_wallet_balance(accountType="UNIFIED")
    # Фильтруем монеты с ненулевым балансом
    coins = []
    for coin_info in data['result']['coin']:
        balance = float(coin_info['walletBalance'])
        if balance != 0:
            coins.append({
                "coin": coin_info['coin'],
                "balance": balance,
                "locked": float(coin_info.get('locked', 0)),
                "usdValue": float(coin_info['usdValue'])
            })
    return {"portfolio": coins}

@app.post("/buy")
def buy_crypto(request: BuyRequest, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Покупка криптовалюты по рыночной цене в спотовом аккаунте.
    symbol: торговая пара (напр. 'BTCUSDT'), amount: количество базовой валюты.
    """
    check_token(credentials)
    # Создание рыночного ордера (Market Buy)
    result = bybit_session.place_active_order(
        category="spot",
        symbol=request.symbol,
        side="Buy",
        orderType="Market",
        qty=request.amount,
        timeInForce="GoodTillCancel",
        reduce_only=False,
        close_on_trigger=False,
        marketUnit="baseCoin"  # количество в базовой валюте
    )
    return {"order": result}

@app.get("/pnl")
def get_pnl(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Рассчитывает PnL (прибыль/убыток) текущего портфеля по сравнению
    с начальным балансом при запуске приложения.
    """
    check_token(credentials)
    data = bybit_session.get_wallet_balance(accountType="UNIFIED")
    current_balance = float(data['result']['totalWalletBalance'])
    initial_balance = initial_portfolio_usd['total']
    pnl_value = current_balance - initial_balance
    pnl_percent = (pnl_value / initial_balance * 100) if initial_balance != 0 else 0.0
    return {
        "initial_value_usd": initial_balance,
        "current_value_usd": current_balance,
        "pnl_usd": pnl_value,
        "pnl_percent": pnl_percent
    }






