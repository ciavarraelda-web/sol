import streamlit as st
import requests

# Inserisci qui l'URL del tuo backend API (Node.js reale, online e pubblico)
API_URL = "http://TUO_BACKEND_SERVER:3000/api"  # <-- MODIFICA qui con il tuo vero server!

st.title("SOLAY39 Mining Platform")
st.markdown(
    """
    **Connect your Solana wallet and mine SOLAY39 tokens!**  
    [Buy SOLAY39 in presale (Raydium)](https://raydium.io/launchpad/token/?mint=P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray)
    """
)

wallet = st.text_input("Enter your Solana wallet address:")

if wallet:
    try:
        resp = requests.get(f"{API_URL}/user_info", params={"wallet": wallet}, timeout=10)
        if resp.status_code == 200:
            user_info = resp.json()
            if not user_info.get("can_mine", False):
                st.error("You need to hold at least 1 SOLAY39 to mine.")
            else:
                st.success(f"Your balance: **{user_info['balance']} SOLAY39**")
                st.info(f"Reward per click: **{user_info['current_reward']} SOLAY39**")
                st.info(f"Mining quota left today: **{user_info['mining_left']} SOLAY39**")
                st.info(f"SOLAY39 price: **€{user_info['price_eur']}**")
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

st.markdown("""

