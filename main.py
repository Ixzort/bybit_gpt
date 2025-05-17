import os
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pybit.unified_trading import HTTP

# ======= Конфигурация ключей =======
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"        # TODO: вставьте сюда ваш Bybit Testnet API-ключ
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"  # TODO: вставьте сюда ваш Bybit Testnet API-секрет
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"     # TODO: укажите секретный ключ для доступа к API (авторизация плагина)

# Создаем сессию Bybit API (Testnet)
try:
    session = HTTP(
        testnet=True,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
except Exception as e:
    # Если ключи неверные или при подключении ошибка
    print("Ошибка инициализации сессии Bybit:", e)
    raise

# Получаем начальное состояние портфеля (USD эквивалент) для расчета PnL
initial_portfolio_usd = 0.0
try:
    balance_data = session.get_wallet_balance(accountType="UNIFIED")  # получаем баланс по Unified Account:contentReference[oaicite:3]{index=3}
    if balance_data.get("result"):
        # Берем суммарный баланс в USD (totalWalletBalance) если доступен
        account_list = balance_data["result"].get("list", [])
        if account_list:
            initial_portfolio_usd = float(account_list[0].get("totalWalletBalance", 0))
except Exception as e:
    print("Не удалось получить начальный баланс портфеля:", e)

app = FastAPI(title="Bybit Crypto Assistant", version="1.0")

# Подключаем раздачу статических файлов из директории .well-known (для манифеста и спецификации)
app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Зависимость для проверки API-ключа авторизации
def verify_api_key(authorization: str = Header(None)):
    """Проверяет заголовок Authorization: Bearer <KEY>"""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет заголовка Authorization")
    token = authorization.split("Bearer ")[1]
    if token != PLUGIN_AUTH_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный API-ключ плагина")
    return True

@app.get("/portfolio", dependencies=[Depends(verify_api_key)])
def get_portfolio():
    """Получить баланс активов с Bybit (Testnet)"""
    try:
        # Запрос баланса по всем не нулевым валютам (Unified аккаунт)
        data = session.get_wallet_balance(accountType="UNIFIED")  # Bybit API запрос баланса:contentReference[oaicite:4]{index=4}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запроса к Bybit: {e}")
    # Проверяем ответ Bybit API
    if data.get("retCode") != 0:
        err_msg = data.get("retMsg") or "Unknown error"
        raise HTTPException(status_code=500, detail=f"Bybit API error: {err_msg}")
    # Формируем удобный ответ: список валют и балансов
    assets = []
    for entry in data["result"]["list"]:
        for coin in entry.get("coin", []):
            coin_name = coin.get("coin")
            wallet_balance = coin.get("walletBalance")
            available_balance = coin.get("availableToWithdraw") or coin.get("free") or wallet_balance
            assets.append({
                "coin": coin_name,
                "wallet_balance": float(wallet_balance) if wallet_balance is not None else 0.0,
                "available_balance": float(available_balance) if available_balance is not None else 0.0
            })
    return {"portfolio": assets}

@app.post("/buy", dependencies=[Depends(verify_api_key)])
def buy_asset(symbol: str, amount: float):
    """
    Купить актив по рынку: symbol (например BTCUSDT), amount — сумма в валюте котировки (например, 10 USDT).
    """
    try:
        order = session.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=str(amount),
            marketUnit="quoteCoin",
            timeInForce="IOC"
        )
        if order["retCode"] != 0:
            raise HTTPException(status_code=400, detail=order["retMsg"])
        return {"message": "Ордер на покупку размещён", "order": order["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при покупке: {e}")

@app.post("/sell", dependencies=[Depends(verify_api_key)])
def sell_asset(symbol: str, amount: float):
    """
    Продать актив по рынку: symbol (например BTCUSDT), amount — количество базовой валюты (например, 0.001 BTC).
    """
    try:
        order = session.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=str(amount),
            marketUnit="baseCoin",
            timeInForce="IOC"
        )
        if order["retCode"] != 0:
            raise HTTPException(status_code=400, detail=order["retMsg"])
        return {"message": "Ордер на продажу размещён", "order": order["result"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при продаже: {e}")




@app.get("/pnl", dependencies=[Depends(verify_api_key)])
def get_pnl():
    """
    Рассчитать прибыль/убыток портфеля с момента запуска (в USD).
    PnL = текущая стоимость портфеля (USD) - начальная стоимость портфеля (USD).
    """
    global initial_portfolio_usd
    try:
        data = session.get_wallet_balance(accountType="UNIFIED")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка запроса к Bybit: {e}")
    if data.get("retCode") != 0:
        err_msg = data.get("retMsg") or "Unknown error"
        raise HTTPException(status_code=500, detail=f"Bybit API error: {err_msg}")
    # Текущий суммарный баланс в USD
    current_usd = 0.0
    account_list = data["result"].get("list", [])
    if account_list:
        current_usd = float(account_list[0].get("totalWalletBalance", 0.0))
    # Вычисляем PnL
    pnl_value = current_usd - initial_portfolio_usd
    percent = None
    if initial_portfolio_usd > 0:
        percent = (pnl_value / initial_portfolio_usd) * 100.0
    return {"initial_portfolio_usd": initial_portfolio_usd, "current_portfolio_usd": current_usd,
            "pnl_usd": pnl_value, "pnl_percent": percent}


