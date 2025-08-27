import os
import streamlit as st
import requests

# CHANGE THIS: Set your real backend API URL here
API_URL = "https://your-real-api-server.com/api"  # <--- Set your real API endpoint

# Show logo if present
if os.path.exists("IMG_20250728_223508.jpg"):
    st.image("IMG_20250728_223508.jpg", width=200)

st.title("SOLAY39 Mining Platform")
st.markdown(
    """
    **Welcome to SOLAY39 Mining!**
    Mine SOLAY39 tokens by connecting your Solana wallet.  
    - You must hold at least 1 SOLAY39 in your wallet to mine and earn more tokens.
    - Each mining action rewards you with SOLAY39 based on your quota.
    - Check your balance, daily mining limit, and reward directly on this page.

    [Buy SOLAY39 in presale on Raydium](https://raydium.io/launchpad/token/?mint=P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray)

    *Paste your Solana wallet address (from Phantom/Solflare):*
    """
)

wallet = st.text_input("Solana Wallet Address", help="Paste your public Solana address here")

if wallet:
    try:
        resp = requests.get(f"{API_URL}/user_info", params={"wallet": wallet}, timeout=10)
        if resp.status_code == 200:
            user_info = resp.json()
            if not user_info.get("can_mine", False):
                st.error("You need to hold at least 1 SOLAY39 to mine.")
            else:
                st.success(f"Balance: **{user_info['balance']} SOLAY39**")
                st.info(f"Reward per mining: **{user_info['current_reward']} SOLAY39**")
                st.info(f"Daily mining quota left: **{user_info['mining_left']} SOLAY39**")
                st.info(f"SOLAY39 current price: **€{user_info['price_eur']}**")
                if st.button("Mine!"):
                    mine_resp = requests.post(f"{API_URL}/mine", json={"wallet": wallet}, timeout=15)
                    result = mine_resp.json()
                    if result.get("success"):
                        st.success(f"Mined! You received {result['reward']} SOLAY39.")
                        st.info(f"Transaction: {result['tx']}")
                    else:
                        st.error(result.get("message", "Mining failed."))
        else:
            st.error(f"API error: {resp.status_code} - {resp.text}")
    except Exception as e:
        st.error(f"API connection error: {e}")

st.markdown(
    """
---
**Troubleshooting**
- Make sure your backend API is online and accessible from the internet.
- If using Streamlit Cloud, your backend must have a public domain (not localhost/private IP).
- Test API manually with Postman or `curl` to ensure connection:
