from fastapi import FastAPI
from pybit.unified_trading import HTTP as BybitHTTP
from contextlib import asynccontextmanager
import traceback

# ==== Конфигурация ключей ====
BYBIT_API_KEY = "yQ6vPLh9DcWvDgbRlz"
BYBIT_API_SECRET = "7T2mItvuA4fmvCvOzQCuQHixxllAsBikr55B "
USE_TESTNET = True  # 👉 Измени на False, если хочешь перейти на Mainnet

# ==== Инициализация клиента Bybit ====
session = BybitHTTP(
    testnet=USE_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

# ==== Диагностика подключения ====
def test_bybit_connection():
    print(f"🔌 Инициализация Bybit с testnet={USE_TESTNET}")
    print("🚀 Тестирование подключения к Bybit...")

    account_types = ["UNIFIED", "SPOT", "CONTRACT"]

    for acc_type in account_types:
        try:
            print(f"\n📦 Пробуем accountType = {acc_type}")
            res = session.get_wallet_balance(accountType=acc_type)
            balances = res.get("result", {}).get("list", [])
            if balances:
                print(f"✅ УСПЕШНО: Баланс получен для {acc_type}")
                for b in balances:
                    print(f" - {b['coin']}: {b['walletBalance']}")
            else:
                print(f"⚠️ Получен пустой список для {acc_type}")
        except Exception as e:
            print(f"❌ Ошибка при accountType = {acc_type}")
            print(traceback.format_exc())

# ==== Lifespan вместо on_event ====
@asynccontextmanager
async def lifespan(app: FastAPI):
    test_bybit_connection()
    yield
    print("🛑 Завершение приложения")

# ==== FastAPI-приложение ====
app = FastAPI(title="Bybit Diagnostic App", lifespan=lifespan)


