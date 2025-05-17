BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

import os
from decimal import Decimal
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pybit.unified_trading import HTTP

app = FastAPI()


if not BYBIT_API_KEY or not BYBIT_API_SECRET:
    raise Exception("Не настроены ключи Bybit API: BYBIT_API_KEY или BYBIT_API_SECRET")

@app.post("/buy")
async def buy(request: Request):
    # Проверяем заголовок авторизации Bearer
    auth_header = request.headers.get("Authorization")
    if auth_header != f"Bearer {PLUGIN_AUTH_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    symbol = data.get("symbol")
    amount = data.get("amount")
    price = data.get("price", None)
    # Валидация входных данных
    if not symbol or not amount:
        return JSONResponse(content={"order": {}, "message": "Параметры symbol и amount обязательны"})
    side = "Buy"
    # Определяем тип ордера: Limit, если указан price, иначе Market
    order_type = "Limit" if price is not None else "Market"
    try:
        amount_dec = Decimal(str(amount))
    except Exception:
        return JSONResponse(content={"order": {}, "message": "Некорректное значение amount"})
    if order_type == "Limit":
        try:
            price_dec = Decimal(str(price))
        except Exception:
            return JSONResponse(content={"order": {}, "message": "Некорректное значение price"})
    # Создаем сессию Bybit
    client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    # Получаем информацию об инструменте для проверки ограничений
    info = client.get_instruments_info(category="spot", symbol=symbol)
    if info.get("retCode") != 0 or not info.get("result", {}).get("list"):
        return JSONResponse(content={"order": {}, "message": f"Не удалось получить информацию о символе {symbol}"})
    instrument = info["result"]["list"][0]
    lot = instrument.get("lotSizeFilter", {})
    price_filter = instrument.get("priceFilter", {})
    # Параметры ограничения
    min_qty = Decimal(lot.get("minOrderQty", "0"))
    base_prec = int(lot.get("basePrecision", 0))
    # Шаг количества = 10^(-basePrecision)
    qty_step = Decimal(10) ** (-base_prec) if base_prec > 0 else Decimal("1")
    min_notional = Decimal(lot.get("minNotionalValue", lot.get("minOrderAmt", "0")))
    tick_size = Decimal(price_filter.get("tickSize", "1"))
    min_price = Decimal(price_filter.get("minPrice", "0"))
    # Округляем количество по шагу вниз
    qty = (amount_dec // qty_step) * qty_step
    if qty < min_qty:
        return JSONResponse(content={"order": {}, "message": f"Минимальное количество для {symbol} = {min_qty}"})
    # Подготовка параметров ордера
    order_params = {
        "category": "spot",
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": str(qty),
        "isLeverage": 0,
        "orderFilter": "Order"
    }
    if order_type == "Limit":
        # Округляем цену по тиковому шагу вниз
        price_quant = (price_dec // tick_size) * tick_size
        if price_quant < min_price:
            return JSONResponse(content={"order": {}, "message": f"Минимальная цена для {symbol} = {min_price}"})
        notional = qty * price_quant
        if min_notional and notional < min_notional:
            return JSONResponse(content={"order": {}, "message": f"Минимальная сумма ордера (notional) = {min_notional}"})
        order_params["price"] = str(price_quant)
        order_params["timeInForce"] = "GTC"
    else:
        # Для Market Buy задание unit = baseCoin, чтобы qty трактовался в базовой валюте
        order_params["marketUnit"] = "baseCoin"
    # Исполняем ордер через Bybit API
    try:
        order = client.place_order(**order_params)
    except Exception as e:
        return JSONResponse(content={"order": {}, "message": f"Ошибка при отправке ордера: {str(e)}"})
    # Формируем ответ
    if order.get("retCode") == 0:
        message = "Ордер размещен успешно"
    else:
        message = f"Ошибка при размещении ордера: {order.get('retMsg', '')}"
    return JSONResponse(content={"order": order, "message": message})

@app.post("/sell")
async def sell(request: Request):
    # Проверяем заголовок авторизации Bearer
    auth_header = request.headers.get("Authorization")
    if auth_header != f"Bearer {PLUGIN_AUTH_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = await request.json()
    symbol = data.get("symbol")
    amount = data.get("amount")
    price = data.get("price", None)
    # Валидация входных данных
    if not symbol or not amount:
        return JSONResponse(content={"order": {}, "message": "Параметры symbol и amount обязательны"})
    side = "Sell"
    order_type = "Limit" if price is not None else "Market"
    try:
        amount_dec = Decimal(str(amount))
    except Exception:
        return JSONResponse(content={"order": {}, "message": "Некорректное значение amount"})
    if order_type == "Limit":
        try:
            price_dec = Decimal(str(price))
        except Exception:
            return JSONResponse(content={"order": {}, "message": "Некорректное значение price"})
    client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
    info = client.get_instruments_info(category="spot", symbol=symbol)
    if info.get("retCode") != 0 or not info.get("result", {}).get("list"):
        return JSONResponse(content={"order": {}, "message": f"Не удалось получить информацию о символе {symbol}"})
    instrument = info["result"]["list"][0]
    lot = instrument.get("lotSizeFilter", {})
    price_filter = instrument.get("priceFilter", {})
    min_qty = Decimal(lot.get("minOrderQty", "0"))
    base_prec = int(lot.get("basePrecision", 0))
    qty_step = Decimal(10) ** (-base_prec) if base_prec > 0 else Decimal("1")
    min_notional = Decimal(lot.get("minNotionalValue", lot.get("minOrderAmt", "0")))
    tick_size = Decimal(price_filter.get("tickSize", "1"))
    min_price = Decimal(price_filter.get("minPrice", "0"))
    qty = (amount_dec // qty_step) * qty_step
    if qty < min_qty:
        return JSONResponse(content={"order": {}, "message": f"Минимальное количество для {symbol} = {min_qty}"})
    order_params = {
        "category": "spot",
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": str(qty),
        "isLeverage": 0,
        "orderFilter": "Order"
    }
    if order_type == "Limit":
        price_quant = (price_dec // tick_size) * tick_size
        if price_quant < min_price:
            return JSONResponse(content={"order": {}, "message": f"Минимальная цена для {symbol} = {min_price}"})
        notional = qty * price_quant
        if min_notional and notional < min_notional:
            return JSONResponse(content={"order": {}, "message": f"Минимальная сумма ордера (notional) = {min_notional}"})
        order_params["price"] = str(price_quant)
        order_params["timeInForce"] = "GTC"
    try:
        order = client.place_order(**order_params)
    except Exception as e:
        return JSONResponse(content={"order": {}, "message": f"Ошибка при отправке ордера: {str(e)}"})
    if order.get("retCode") == 0:
        message = "Ордер размещен успешно"
    else:
        message = f"Ошибка при размещении ордера: {order.get('retMsg', '')}"
    return JSONResponse(content={"order": order, "message": message})









