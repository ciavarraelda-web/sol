import streamlit as st
import requests

API_URL = "http://localhost:3000/api"  # Change to your backend URL if deployed

# Show logo (make sure IMG_20250728_223508.jpg is in the same folder as this script)
st.image("IMG_20250728_223508.jpg", width=300)
st.title("SOLAY39 Mining Platform")

st.markdown(
    """
    **Connect your Solana wallet and mine SOLAY39 tokens!**  
    [Buy SOLAY39 in presale (Raydium)](https://raydium.io/launchpad/token/?mint=P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray)
    """
)

wallet = st.text_input("Enter your Solana wallet address:")

if wallet:
    resp = requests.get(f"{API_URL}/user_info?wallet={wallet}")
    if resp.status_code == 200:
        user_info = resp.json()
        if not user_info.get("can_mine", False):
            st.error("You need to hold at least 1 SOLAY39 to mine.")
        else:
            st.write(f"Your balance: **{user_info['balance']} SOLAY39**")
            st.write(f"Reward per click: **{user_info['current_reward']} SOLAY39**")
            st.write(f"Mining quota left today: **{user_info['mining_left']} SOLAY39**")
            st.write(f"SOLAY39 price: **€{user_info['price_eur']}**")
            if st.button("Mine!"):
                mine_resp = requests.post(f"{API_URL}/mine", json={"wallet": wallet})
                result = mine_resp.json()
                if result.get("success"):
                    st.success(f"Mined! You received {result['reward']} SOLAY39.")
                else:
                    st.error(result.get("message", "Mining failed."))
    else:
        st.error("Error connecting to backend. Please try again.")
