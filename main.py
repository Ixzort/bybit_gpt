

#BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
#YBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
#PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pybit.unified_trading import HTTP
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (если используется)
load_dotenv()

# Инициализация FastAPI
app = FastAPI(
    title="Bybit Unified Trading API",
    description="API для управления портфелем и ордерами на Bybit Unified Account (Spot)",
    version="1.0"
)

# Получаем ключи API из окружения
API_KEY = "mWC5xhURKakJkC9Dri"
API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
if not API_KEY or not API_SECRET:
    raise RuntimeError("Не заданы BYBIT_API_KEY и BYBIT_API_SECRET в окружении")

# Клиент pybit для Unified Trading (основной API, не тестнет)
client = HTTP(testnet=True, api_key=API_KEY, api_secret=API_SECRET)


def get_total_portfolio_usd() -> float:
    """
    Рассчитывает суммарную стоимость портфеля в USD (включая все монеты).
    Для каждой монеты:
      - если монета USDT или USDC, курс = 1.
      - иначе берется пара монета/USDT через метод market tickers.
    """
    try:
        # Получаем балансы на спотовом (spot) счету Unified Account
        resp = client.get_wallet_balance(accountType="UNIFIED")
    except Exception as e:
        raise RuntimeError(f"Ошибка получения баланса: {e}")

    total_usd = 0.0
    # В структуре ответа pybit -> resp["result"]["list"][0]["coin"] – список монет
    coins = resp.get("result", {}).get("list", [])
    if coins:
        coins = coins[0].get("coin", [])
    for coin_info in coins:
        coin = coin_info.get("coin")
        # Доступный и заблокированный баланс
        free = float(coin_info.get("walletBalance", 0))
        locked = float(coin_info.get("locked", 0))
        amount = free + locked
        if amount == 0:
            continue  # пропускаем монеты с нулевым балансом
        # Определяем цену в USD
        if coin in ("USDT", "USDC"):
            price = 1.0
        else:
            symbol = f"{coin}USDT"
            try:
                ticker_data = client.get_tickers(category="spot", symbol=symbol)
                # Предполагаем, что возвращается список { "lastPrice": ... }
                price = float(ticker_data["result"]["list"][0]["lastPrice"])
            except Exception:
                # Не удалось получить цену для пары — пропускаем монету
                continue
        total_usd += amount * price
    return total_usd


# Запоминаем начальную стоимость портфеля при запуске
initial_portfolio_usd = get_total_portfolio_usd()


# Pydantic модели для запросов BUY и SELL
class TradeRequest(BaseModel):
    symbol: str  # например "BTCUSDT"
    amount: float  # количество базового актива


@app.get("/portfolio")
async def get_portfolio():
    """
    GET /portfolio
    Возвращает список монет со спотового счета Unified Account с ненулевым балансом.
    Формат ответа:
    [ {"coin": "BTC", "free": 0.01, "locked": 0.0, "total": 0.01}, ... ]
    """
    try:
        resp = client.get_wallet_balance(accountType="UNIFIED")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка API Bybit: {e}")

    coins = resp.get("result", {}).get("list", [])
    result = []
    if coins:
        for coin_info in coins[0].get("coin", []):
            free = float(coin_info.get("walletBalance", 0))
            locked = float(coin_info.get("locked", 0))
            total = free + locked
            if total > 0:
                result.append({
                    "coin": coin_info.get("coin"),
                    "free": free,
                    "locked": locked,
                    "total": total
                })
    return result


@app.post("/buy")
async def buy_order(trade: TradeRequest):
    """
    POST /buy
    Рыночная покупка указанной монеты.
    Запрос JSON: { "symbol": "BTCUSDT", "amount": 0.01 }
    """
    try:
        order = client.place_order(
            category="spot",
            symbol=trade.symbol,
            side="Buy",
            orderType="Market",
            qty=str(trade.amount),  # Bybit требует строковый формат числа
            timeInForce="IOC"
        )
        return order  # возвращаем полный ответ API Bybit
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка покупки: {e}")


@app.post("/sell")
async def sell_order(trade: TradeRequest):
    """
    POST /sell
    Рыночная продажа указанной монеты.
    Запрос JSON: { "symbol": "BTCUSDT", "amount": 0.01 }
    """
    try:
        order = client.place_order(
            category="spot",
            symbol=trade.symbol,
            side="Sell",
            orderType="Market",
            qty=str(trade.amount),
            timeInForce="IOC"
        )
        return order
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка продажи: {e}")


@app.get("/pnl")
async def get_pnl():
    """
    GET /pnl
    Рассчитывает PNL: разницу между текущей стоимостью портфеля и начальной (в USD).
    Возвращает JSON { "initial_balance": ..., "current_balance": ..., "pnl": ... }.
    """
    try:
        current_usd = get_total_portfolio_usd()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчёта PNL: {e}")
    pnl_value = current_usd - initial_portfolio_usd
    return {
        "initial_balance": initial_portfolio_usd,
        "current_balance": current_usd,
        "pnl": pnl_value
    }






