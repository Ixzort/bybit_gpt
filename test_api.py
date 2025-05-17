from pybit.unified_trading import HTTP

# Тестовые ключи и Testnet включён
session = HTTP(
    testnet=True,
    api_key="mWC5xhURKakJkC9Dri",
    api_secret="xFlQO48iHMwzy7JHpup2WPVhQq1ksgHyYQJq"
)

# Пробуем получить баланс
try:
    resp = session.get_wallet_balance(accountType="UNIFIED")
    print("✅ API работает. Баланс получен:")
    print(resp)
except Exception as e:
    print("❌ Ошибка API:", e)

