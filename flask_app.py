from flask import Flask, request
import requests

app = Flask(__name__)

# Home Page (Choice 2: User Input Form)
@app.route("/")
def home():
    return """
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #6c5ce7;'>Welcome to Python Web App! 🚀</h1>
        <p style='font-size: 18px;'>Apna naam enter karke personalised greeting dekhein:</p>
        
        <form action='/greet' method='GET' style='margin-top: 20px;'>
            <input type='text' name='username' placeholder='Enter your name...' style='padding: 10px; font-size: 16px; border-radius: 5px; border: 1px solid #ccc;' required>
            <button type='submit' style='padding: 10px 20px; font-size: 16px; background-color: #6c5ce7; color: white; border: none; border-radius: 5px; cursor: pointer;'>Submit</button>
        </form>
        
        <br><br>
        <a href='/crypto' style='color: #00b894; font-size: 18px; font-weight: bold;'>📈 Check Live Crypto Prices Page ➔</a>
    </div>
    """

# Personalised Greeting Page
@app.route("/greet")
def greet():
    name = request.args.get('username', 'Guest')
    return f"""
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #00b894;'>Hello, {name}! 👋</h1>
        <p style='font-size: 18px;'>Aapka Python backend successful input handle kar raha hai.</p>
        <br>
        <a href='/' style='color: #6c5ce7;'>← Back to Home Page</a>
    </div>
    """

# Crypto Tracker Page (Choice 1)
@app.route("/crypto")
def crypto():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
        res = requests.get(url).json()
        btc = res['bitcoin']['usd']
        eth = res['ethereum']['usd']
        status = f"<p style='color: green;'>Live Data Fetched Successfully!</p>"
    except:
        btc, eth = "N/A", "N/A"
        status = f"<p style='color: red;'>API Connection Error</p>"

    return f"""
    <div style='text-align: center; font-family: Arial; margin-top: 50px;'>
        <h1 style='color: #f39c12;'>📈 Live Crypto Rates (Web Portal)</h1>
        {status}
        <div style='display: inline-block; background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin: 10px;'>
            <h3>Bitcoin (BTC)</h3>
            <p style='font-size: 24px;'>${btc}</p>
        </div>
        <div style='display: inline-block; background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin: 10px;'>
            <h3>Ethereum (ETH)</h3>
            <p style='font-size: 24px;'>${eth}</p>
        </div>
        <br><br>
        <a href='/' style='color: #6c5ce7;'>← Back to Home Page</a>
    </div>
    """

if __name__ == "__main__":
    app.run(debug=True)