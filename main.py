from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from decimal import Decimal, ROUND_DOWN
from bybit import usdt_perpetual  # Предполагаем, что используем Bybit SDK или API-клиент
import os

app = FastAPI()

# Реальные API-ключи Bybit и ключ плагина
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

# Клиент Bybit (пример; важно, чтобы клиент поддерживал методы spot)
client = usdt_perpetual.HTTP()  # или другой клиент для спота
client.api_key = BYBIT_API_KEY
client.api_secret = BYBIT_API_SECRET

# Настраиваем Bearer-авторизацию
security = HTTPBearer()

def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Проверка Bearer-токена в заголовке Authorization.
    Если токен не совпадает с PLUGIN_AUTH_KEY, возвращается ошибка 401.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=403, detail="Отсутствует или неверный тип токена")
    if credentials.credentials != PLUGIN_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Неверный токен авторизации")
    return credentials.credentials

class TradeRequest(BaseModel):
    symbol: str
    quantity: float
    orderType: str  # "Market" или "Limit"
    price: float = None  # Обязательно для Limit, игнорируется для Market

class TradeResponse(BaseModel):
    order_id: str
    status: str
    executed_qty: float
    executed_price: float

@app.post("/buy", response_model=TradeResponse, summary="Купить актив")
def buy(request: TradeRequest, token: str = Depends(get_api_key)):
    """
    Размещает ордер на покупку.
    Поддерживает Market и Limit ордера.
    Параметры price и quantity приводятся к допустимым шагам,
    проверяются ограничения min_qty, qty_step, tick_size и min_notional:contentReference[oaicite:3]{index=3}.
    """
    # Получаем информацию об инструменте
    info = client.get_instruments_info(category="spot", symbol=request.symbol)
    if not info or 'result' not in info:
        raise HTTPException(status_code=400, detail="Неверный символ или не удалось получить информацию об инструменте")
    inst = info['result'][0]
    price_filter = inst["priceFilter"]
    lot_filter = inst["lotSizeFilter"]
    tick_size = Decimal(price_filter["tickSize"])
    qty_step = Decimal(lot_filter["qtyStep"])
    min_qty = Decimal(lot_filter["minOrderQty"])
    min_notional = Decimal(lot_filter.get("minNotionalValue", 0))

    # Подготовка параметров
    qty = Decimal(str(request.quantity))
    if qty < min_qty:
        raise HTTPException(status_code=400, detail=f"Количество меньше минимального {min_qty}")
    # Округляем количество вниз до ближайшего шага qty_step
    qty = (qty / qty_step).quantize(Decimal('1.'), rounding=ROUND_DOWN) * qty_step

    if request.orderType == "Market":
        # Для Market-ордера цена не требуется; отправляем market buy
        result = client.place_active_order(
            symbol=request.symbol, side="Buy", order_type="Market", qty=str(qty), time_in_force="IOC"
        )
    elif request.orderType == "Limit":
        if request.price is None:
            raise HTTPException(status_code=400, detail="Для лимитного ордера необходимо указать цену")
        price = Decimal(str(request.price))
        if price < Decimal(price_filter["minPrice"]):
            raise HTTPException(status_code=400, detail="Цена ниже минимальной")
        # Округляем цену до tick_size
        price = (price / tick_size).quantize(Decimal('1.'), rounding=ROUND_DOWN) * tick_size
        # Проверяем минимальный нотионал (price * qty)
        if price * qty < min_notional:
            raise HTTPException(status_code=400, detail=f"Стоимость ордера ниже минимального {min_notional}")
        result = client.place_active_order(
            symbol=request.symbol, side="Buy", order_type="Limit",
            qty=str(qty), price=str(price), time_in_force="GTC"
        )
    else:
        raise HTTPException(status_code=400, detail="Неверный тип ордера")

    # Обработка ответа Bybit
    if result.get("ret_code") != 0:
        raise HTTPException(status_code=400, detail=result.get("ret_msg", "Ошибка от Bybit"))
    order_id = result["result"]["order_id"]
    return TradeResponse(
        order_id=order_id,
        status=result["result"]["status"],
        executed_qty=float(qty),
        executed_price=float(request.price or 0)
    )

@app.post("/sell", response_model=TradeResponse, summary="Продать актив")
def sell(request: TradeRequest, token: str = Depends(get_api_key)):
    """
    Размещает ордер на продажу.
    Поддерживает Market и Limit ордера.
    Принцип работы аналогичен /buy, только side="Sell".
    """
    # Логика аналогична методу buy, только side="Sell"
    info = client.get_instruments_info(category="spot", symbol=request.symbol)
    if not info or 'result' not in info:
        raise HTTPException(status_code=400, detail="Неверный символ или не удалось получить информацию об инструменте")
    inst = info['result'][0]
    price_filter = inst["priceFilter"]
    lot_filter = inst["lotSizeFilter"]
    tick_size = Decimal(price_filter["tickSize"])
    qty_step = Decimal(lot_filter["qtyStep"])
    min_qty = Decimal(lot_filter["minOrderQty"])
    min_notional = Decimal(lot_filter.get("minNotionalValue", 0))

    qty = Decimal(str(request.quantity))
    if qty < min_qty:
        raise HTTPException(status_code=400, detail=f"Количество меньше минимального {min_qty}")
    qty = (qty / qty_step).quantize(Decimal('1.'), rounding=ROUND_DOWN) * qty_step

    if request.orderType == "Market":
        result = client.place_active_order(
            symbol=request.symbol, side="Sell", order_type="Market", qty=str(qty), time_in_force="IOC"
        )
    elif request.orderType == "Limit":
        if request.price is None:
            raise HTTPException(status_code=400, detail="Для лимитного ордера необходимо указать цену")
        price = Decimal(str(request.price))
        if price < Decimal(price_filter["minPrice"]):
            raise HTTPException(status_code=400, detail="Цена ниже минимальной")
        price = (price / tick_size).quantize(Decimal('1.'), rounding=ROUND_DOWN) * tick_size
        if price * qty < min_notional:
            raise HTTPException(status_code=400, detail=f"Стоимость ордера ниже минимального {min_notional}")
        result = client.place_active_order(
            symbol=request.symbol, side="Sell", order_type="Limit",
            qty=str(qty), price=str(price), time_in_force="GTC"
        )
    else:
        raise HTTPException(status_code=400, detail="Неверный тип ордера")

    if result.get("ret_code") != 0:
        raise HTTPException(status_code=400, detail=result.get("ret_msg", "Ошибка от Bybit"))
    order_id = result["result"]["order_id"]
    return TradeResponse(
        order_id=order_id,
        status=result["result"]["status"],
        executed_qty=float(qty),
        executed_price=float(request.price or 0)
    )






