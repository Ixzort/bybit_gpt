from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from decimal import Decimal, ROUND_DOWN
from pybit.unified_trading import HTTP as BybitHTTP

# ==== Конфигурация ключей ====
BYBIT_API_KEY = "mWC5xhURKakJkC9Dri"
BYBIT_API_SECRET = "xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
PLUGIN_AUTH_KEY = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"

# ==== Инициализация ====
app = FastAPI(title="Bybit Crypto Assistant", version="1.1")
security = HTTPBearer()

session = BybitHTTP(
    testnet=False,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token != PLUGIN_AUTH_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ==== Модели ====
class TradeRequest(BaseModel):
    symbol: str
    quantity: float
    orderType: str  # "Market" или "Limit"
    price: float | None = None

class TradeResponse(BaseModel):
    orderId: str
    status: str
    qty: float
    price: float | None = None

# ==== Хелпер ====
def round_down(value: Decimal, step: Decimal) -> Decimal:
    return (value // step) * step

def get_symbol_info(symbol: str):
    res = session.get_instruments_info(category="spot", symbol=symbol)
    if "result" not in res or not res["result"]["list"]:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not found")
    return res["result"]["list"][0]

# ==== Торговля ====
@app.post("/buy", response_model=TradeResponse, dependencies=[Depends(verify_api_key)])
def buy(trade: TradeRequest):
    return place_order(trade, side="Buy")

@app.post("/sell", response_model=TradeResponse, dependencies=[Depends(verify_api_key)])
def sell(trade: TradeRequest):
    return place_order(trade, side="Sell")

def place_order(trade: TradeRequest, side: str):
    symbol = trade.symbol.upper()
    info = get_symbol_info(symbol)

    # Ограничения
    qty_step = Decimal(info["lotSizeFilter"]["qtyStep"])
    min_qty = Decimal(info["lotSizeFilter"]["minOrderQty"])
    min_notional = Decimal(info["lotSizeFilter"].get("minOrderAmt", "0"))
    tick_size = Decimal(info["priceFilter"]["tickSize"])

    qty = Decimal(str(trade.quantity))
    if qty < min_qty:
        raise HTTPException(status_code=400, detail=f"Минимальный объем: {min_qty}")
    qty = round_down(qty, qty_step)

    params = {
        "category": "spot",
        "symbol": symbol,
        "side": side,
        "orderType": trade.orderType,
        "qty": str(qty)
    }

    if trade.orderType == "Limit":
        if trade.price is None:
            raise HTTPException(status_code=400, detail="Price is required for Limit orders")
        price = Decimal(str(trade.price))
        price = round_down(price, tick_size)
        if price * qty < min_notional:
            raise HTTPException(status_code=400, detail=f"Минимальная сумма сделки: {min_notional} USDT")
        params["price"] = str(price)
        params["timeInForce"] = "GTC"
    else:
        params["timeInForce"] = "IOC"

    try:
        result = session.place_order(**params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка размещения ордера: {e}")

    if result["retCode"] != 0:
        raise HTTPException(status_code=400, detail=f"Ошибка Bybit: {result['retMsg']}")

    return TradeResponse(
        orderId=result["result"]["orderId"],
        status=result["result"]["orderStatus"],
        qty=float(qty),
        price=float(price) if "price" in locals() else None
    )






