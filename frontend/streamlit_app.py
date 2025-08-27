import os
import streamlit as st
import requests

st.set_page_config(page_title="SOLAY39 Mining", page_icon="⛏️")

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Logo opzionale
if os.path.exists("IMG_20250728_223508.jpg"):
    st.image("IMG_20250728_223508.jpg", width=200)

st.title("SOLAY39 Mining Platform")
st.markdown("""
**Benvenuto in SOLAY39 Mining!**  
Inserisci il tuo indirizzo wallet Solana (Phantom/Glow/Solflare) per controllare il bilancio e, se idoneo, raccogliere la tua ricompensa giornaliera.
- Per visualizzare la possibilità di minare serve almeno **1 SOLAY39** nel wallet.
- Per avere diritto alla **quota giornaliera di 50 SOLAY39** devi possedere **≥ 100000 SOLAY39**.
""")

wallet = st.text_input("Solana Wallet Address", help="Incolla il tuo indirizzo pubblico")

if wallet:
    try:
        resp = requests.get(f"{API_URL}/user_info", params={"wallet": wallet}, timeout=10)
        if resp.status_code == 200:
            u = resp.json()
            if not u.get("can_mine", False):
                st.error("Devi avere almeno 1 SOLAY39 nel wallet per interagire con il sistema.")
            else:
                st.success(f"Balance: **{u['balance']} SOLAY39**")
                st.info(f"Quota giornaliera assegnata: **{u['current_reward']} SOLAY39**")
                st.info(f"Già minati oggi: **{u['mined_today']} SOLAY39**")
                st.info(f"Rimanenti oggi: **{u['mining_left']} SOLAY39**")
                st.info(f"Prezzo attuale (EUR): **€{u['price_eur']}**")

                if u.get("has_quota", False):
                    if st.button("Mine! (richiedi quota restante oggi)"):
                        mine_resp = requests.post(f"{API_URL}/mine", json={"wallet": wallet}, timeout=30)
                        if mine_resp.status_code == 200:
                            result = mine_resp.json()
                            if result.get("success"):
                                st.success(f"Mined! Ricevuti: {result['reward']} SOLAY39")
                                st.write(f"Transaction: `{result['tx']}`")
                            else:
                                st.error(result.get("message", "Errore mining"))
                        else:
                            st.error(f"Errore API: {mine_resp.status_code} - {mine_resp.text}")
                else:
                    st.warning("Non hai la quota giornaliera (servono >= 100000 SOLAY39 per ricevere 50 SOLAY39/giorno).")
        else:
            st.error(f"API error: {resp.status_code} - {resp.text}")
    except Exception as e:
        st.error(f"Errore connessione API: {e}")

st.markdown("""
---
**Troubleshooting**
- Assicurati che il backend sia online e raggiungibile (modifica API_URL se necessario).
- Testa le API con `curl` o Postman: `GET /user_info?wallet=...` e `POST /mine`.
""")
