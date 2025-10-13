# # test.py
# import os
# from dotenv import load_dotenv
# from alpaca_trade_api import REST
#
# # 1) 加载项目根目录的 .env
# load_dotenv()
#
# # 2) 兼容读取（优先 APCA_，退回 ALPACA_）
# key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY_ID")
# secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET_KEY")
# base_url = os.getenv("APCA_API_BASE_URL") or os.getenv("ALPACA_API_BASE_URL") or "https://paper-api.alpaca.markets"
#
# assert key and secret, "环境变量里没有找到 Alpaca Key/Secret（APCA_* 或 ALPACA_*）"
#
# api = REST(key, secret, base_url)
#
# acct = api.get_account()
# print("Cash:", acct.cash)
# print("Buying Power:", acct.buying_power)
# print("Portfolio Value:", acct.portfolio_value)
