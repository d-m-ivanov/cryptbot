import requests

resp = requests.get("https://api1.binance.com/api/v3/exchangeInfo")
res_js = resp.json()
with open("all_pairs.txt", "w") as f:
    for data in res_js['symbols']:
        f.write(data['symbol'] + "\n")
