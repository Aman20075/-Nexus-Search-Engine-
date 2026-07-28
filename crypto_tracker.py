import tkinter as tk
import requests

def get_crypto_price():
    try:
        # Live Bitcoin Price API
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
        response = requests.get(url).json()
        
        btc_price = response['bitcoin']['usd']
        eth_price = response['ethereum']['usd']

        btc_label.config(text=f"Bitcoin (BTC): ${btc_price:,}")
        eth_label.config(text=f"Ethereum (ETH): ${eth_price:,}")
        status_label.config(text="Status: Updated Successfully! ✅", fg="#a6e3a1")
    except Exception as e:
        status_label.config(text="Status: Connection Error! ❌", fg="#f38ba8")

# GUI Setup
root = tk.Tk()
root.title("Crypto Live Tracker 📈")
root.geometry("400x300")
root.configure(bg="#1e1e2e")

title_label = tk.Label(
    root, text="⚡ LIVE CRYPTO TRACKER", 
    font=("Segoe UI", 16, "bold"), bg="#1e1e2e", fg="#cba6f7"
)
title_label.pack(pady=20)

btc_label = tk.Label(
    root, text="Bitcoin (BTC): Loading...", 
    font=("Segoe UI", 12, "bold"), bg="#313244", fg="#f9e2af", width=30, height=2
)
btc_label.pack(pady=10)

eth_label = tk.Label(
    root, text="Ethereum (ETH): Loading...", 
    font=("Segoe UI", 12, "bold"), bg="#313244", fg="#89b4fa", width=30, height=2
)
eth_label.pack(pady=10)

update_btn = tk.Button(
    root, text="Refresh Prices 🔄", font=("Segoe UI", 10, "bold"),
    bg="#a6e3a1", fg="#11111b", relief="flat", cursor="hand2", command=get_crypto_price
)
update_btn.pack(pady=10)

status_label = tk.Label(root, text="", font=("Segoe UI", 9), bg="#1e1e2e")
status_label.pack()

# Initial Call
get_crypto_price()

root.mainloop()