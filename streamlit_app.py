import os
import streamlit as st
import requests

# Inserisci qui l'URL del tuo backend API (Node.js reale, online e pubblico)
API_URL = "http://TUO_BACKEND_SERVER:3000/api"  # <-- MODIFICA qui con il tuo vero server!

# Mostra il logo se il file esiste
if os.path.exists("IMG_20250728_223508.jpg"):
    st.image("IMG_20250728_223508.jpg", width=200)
else:
    st.info("Carica il file 'IMG_20250728_223508.jpg' nella cartella dell'app per vedere il logo!")

st.title("SOLAY39 Mining Platform")
st.markdown(
    """
    **Connect your Solana wallet and mine SOLAY39 tokens!**  
    [Buy SOLAY39 in presale (Raydium)](https://raydium.io/launchpad/token/?mint=P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray)
    ---
    *Inserisci il tuo indirizzo Solana (lo trovi nel wallet Phantom/Solflare):*
    """
)

wallet = st.text_input("Solana Wallet Address", help="Copia qui il tuo indirizzo Solana dal wallet")

if wallet:
    try:
        resp = requests.get(f"{API_URL}/user_info", params={"wallet": wallet}, timeout=10)
        if resp.status_code == 200:
            user_info = resp.json()
            if not user_info.get("can_mine", False):
                st.error("Devi possedere almeno 1 SOLAY39 per minare.")
            else:
                st.success(f"Saldo: **{user_info['balance']} SOLAY39**")
                st.info(f"Reward mining: **{user_info['current_reward']} SOLAY39**")
                st.info(f"Quota mining giornaliera residua: **{user_info['mining_left']} SOLAY39**")
                st.info(f"Prezzo SOLAY39: **€{user_info['price_eur']}**")
                if st.button("Mine!"):
                    mine_resp = requests.post(f"{API_URL}/mine", json={"wallet": wallet}, timeout=15)
                    result = mine_resp.json()
                    if result.get("success"):
                        st.success(f"Mining completato! Hai ricevuto {result['reward']} SOLAY39.")
                        st.info(f"Transazione: {result['tx']}")
                    else:
                        st.error(result.get("message", "Mining fallito."))
        else:
            st.error(f"Errore API: {resp.status_code} - {resp.text}")
    except Exception as e:
        st.error(f"Errore di connessione API: {e}")

st.markdown(
    """
---
**Debug & Help**
- Assicurati che il backend API sia online e accessibile da Streamlit.
- Se usi Streamlit Cloud, il backend deve essere pubblico (NON localhost).
- Test API manuale: usa un client tipo **Postman** o `curl` per verificare la connessione.
- Il mining reale avviene SOLO se il backend è configurato con la chiave privata e ha token nel wallet premi.
- Per vedere la risposta grezza dell'API, puoi aggiungere `st.write(user_info)` o `st.write(result)` dove preferisci.
"""
)
