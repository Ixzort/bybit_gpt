from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pybit.unified_trading import HTTP
from decimal import Decimal
import traceback

# ==== Конфигурация ====
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

app = FastAPI(title="Bybit Crypto Assistant", version="1.1")
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != PLUGIN_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


client = HTTP(testnet=True, api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)


@app.post("/buy")
async def buy(request: Request, auth: str = Depends(verify_api_key)):
    return await handle_order(request, side="Buy")


@app.post("/sell")
async def sell(request: Request, auth: str = Depends(verify_api_key)):
    return await handle_order(request, side="Sell")


async def handle_order(request: Request, side: str):
    data = await request.json()
    symbol = data.get("symbol")
    amount = data.get("amount")
    price = data.get("price", None)

    if not symbol or not amount:
        return JSONResponse(content={"order": {}, "message": "Нужны параметры symbol и amount"})

    try:
        amount_dec = Decimal(str(amount))
        price_dec = Decimal(str(price)) if price else None
    except Exception:
        return JSONResponse(content={"order": {}, "message": "Некорректные значения"})

    try:
        info = client.get_instruments_info(category="spot", symbol=symbol)
        instrument = info["result"]["list"][0]
        lot = instrument["lotSizeFilter"]
        price_filter = instrument["priceFilter"]

        qty_step = Decimal("1") / (10 ** int(lot["basePrecision"]))
        min_qty = Decimal(lot["minOrderQty"])
        tick_size = Decimal(price_filter["tickSize"])
        min_price = Decimal(price_filter["minPrice"])
        min_notional = Decimal(lot.get("minNotionalValue", lot.get("minOrderAmt", "0")))

        qty = (amount_dec // qty_step) * qty_step
        if qty < min_qty:
            return JSONResponse(content={"order": {}, "message": f"Минимум: {min_qty}"})

        order_type = "Limit" if price else "Market"
        order = {
            "category": "spot",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": str(qty),
            "isLeverage": 0,
            "orderFilter": "Order"
        }

        if order_type == "Limit":
            rounded_price = (price_dec // tick_size) * tick_size
            if rounded_price < min_price:
                return JSONResponse(content={"order": {}, "message": f"Цена меньше минимальной: {min_price}"})
            if qty * rounded_price < min_notional:
                return JSONResponse(content={"order": {}, "message": f"Сумма ордера ниже: {min_notional}"})
            order["price"] = str(rounded_price)
            order["timeInForce"] = "GTC"
        else:
            order["timeInForce"] = "IOC"
            order["marketUnit"] = "baseCoin"

        result = client.place_order(**order)

        if result["retCode"] != 0:
            return JSONResponse(content={"order": result, "message": f"Ошибка: {result['retMsg']}"})

        return JSONResponse(content={"order": result, "message": "Ордер размещен успешно"})

    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(content={"order": {}, "message": f"Ошибка: {str(e)}"})








