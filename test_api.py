import pytest
import httpx
import time

BASE_URL = "https://bybit-gpt-1.onrender.com"
AUTH_TOKEN = "ba4b7246-3660-4ab2-a5dd-715f1a4a9a5a"
HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}
TIMEOUT = 30


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_portfolio():
    response = httpx.get(f"{BASE_URL}/portfolio", headers=HEADERS, timeout=TIMEOUT)
    assert response.status_code == 200
    return response.json()


# === ТЕСТЫ ПОКУПКИ ===

@pytest.mark.parametrize("symbol,amount", [
    ("BTCUSDT", 0.1),
    ("ETHUSDT", 0.1),
    ("SOLUSDT", 1)
])
def test_buy(symbol, amount):
    response = httpx.post(
        f"{BASE_URL}/buy",
        headers=HEADERS,
        json={"symbol": symbol, "amount": amount},
        timeout=TIMEOUT
    )
    assert response.status_code == 200, f"Failed to buy {symbol}"
    json_data = response.json()
    assert "order" in json_data or "message" in json_data


# === ТЕСТЫ ПРОДАЖИ ===

@pytest.mark.parametrize("symbol,amount", [
    ("BTCUSDT", 0.0001),
    ("ETHUSDT", 0.001),
    ("SOLUSDT", 0.01)
])
def test_sell(symbol, amount):
    response = httpx.post(
        f"{BASE_URL}/sell",
        headers=HEADERS,
        json={"symbol": symbol, "amount": amount},
        timeout=TIMEOUT
    )
    assert response.status_code == 200, f"Failed to sell {symbol}"
    json_data = response.json()
    assert "order" in json_data or "message" in json_data


# === ПРОВЕРКА ИЗМЕНЕНИЯ ПОРТФЕЛЯ ===

def test_portfolio_changes_after_buy_and_sell():
    symbol = "BTCUSDT"
    small_amount = 5
    small_sell = 0.0001

    portfolio_before = get_portfolio()
    time.sleep(2)

    httpx.post(f"{BASE_URL}/buy", headers=HEADERS, json={"symbol": symbol, "amount": small_amount}, timeout=TIMEOUT)
    time.sleep(5)

    httpx.post(f"{BASE_URL}/sell", headers=HEADERS, json={"symbol": symbol, "amount": small_sell}, timeout=TIMEOUT)
    time.sleep(5)

    portfolio_after = get_portfolio()

    assert portfolio_before != portfolio_after, "Портфель не изменился после покупки и продажи"

