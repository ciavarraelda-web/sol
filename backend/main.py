"""
FastAPI backend per SOLAY39 "mining" (distribuzione centralizzata).
- /user_info?wallet=...    -> restituisce balance, diritto a minare, quota giornaliera residua
- /mine (POST) body: {"wallet": "<pubkey>"} -> invia reward (se diritto valido) e registra in DB

ATTENZIONE: questo codice gestisce la private key del treasury. Proteggere le credenziali.
Testare prima su devnet.
"""

import os
import json
import sqlite3
from datetime import datetime, date
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from solana.rpc.api import Client
from solana.publickey import PublicKey
from solana.keypair import Keypair
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from dotenv import load_dotenv

load_dotenv()

# Config da env
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
TOKEN_MINT = os.getenv("TOKEN_MINT", "F5e7wgt9yfQbEaA4aCcnSW3HaahcEipywusW7piZFakz")
TREASURY_PUBKEY = os.getenv("TREASURY_PUBKEY", "DZoHMBRyTzShZC9dwQ2HgFwhSjUE2xWLEDypKoa2Mcp3")
TREASURY_SECRET = os.getenv("TREASURY_SECRET")  # può essere JSON array (cli) oppure base58
DAILY_QUOTA = int(os.getenv("DAILY_QUOTA", "50"))  # 50 SOLAY39 per wallet idoneo
MIN_HOLD_TO_MINE = float(os.getenv("MIN_HOLD_TO_MINE", "1"))  # almeno 1 token per accedere
MIN_HOLD_FOR_QUOTA = float(os.getenv("MIN_HOLD_FOR_QUOTA", "100000"))  # >=100k => diritto a quota

DB_PATH = os.getenv("DB_PATH", "mining.db")

# Inizializza client Solana
client = Client(RPC_URL)

app = FastAPI(title="SOLAY39 Mining API")

# -------------------------
# DB semplice SQLite
# -------------------------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS mining_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wallet TEXT NOT NULL,
        amount REAL NOT NULL,
        tx TEXT,
        created_at TIMESTAMP NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------------
# Helpers Solana / Token
# -------------------------
def load_treasury_keypair() -> Keypair:
    """
    Accetta TREASURY_SECRET in due formati:
    - JSON array di 64 o 32 ints (come export da solana keypair file)
    - stringa base58 della secret key
    """
    sec = TREASURY_SECRET
    if not sec:
        raise Exception("TREASURY_SECRET non impostata nelle env")
    # prova JSON
    try:
        data = json.loads(sec)
        if isinstance(data, list):
            # keypair array: crea Keypair.from_secret_key
            secret_bytes = bytes(data)
            return Keypair.from_secret_key(secret_bytes)
    except Exception:
        pass
    # altrimenti considera base58 (solana.keypair accetta solo secret_key bytes)
    try:
        import base58
        b = base58.b58decode(sec)
        return Keypair.from_secret_key(b)
    except Exception as e:
        raise Exception("Formato TREASURY_SECRET non supportato. Usa JSON array o base58.") from e

def get_token_balance(wallet_pubkey: str) -> float:
    """
    Restituisce balance (uiAmount) del token mint per il wallet.
    Se non trovato restituisce 0.0
    """
    owner = PublicKey(wallet_pubkey)
    resp = client.get_token_accounts_by_owner(owner, {"mint": PublicKey(TOKEN_MINT)})
    if resp.get("result") is None:
        return 0.0
    items = resp["result"]["value"]
    total = 0.0
    for a in items:
        info = a["account"]["data"]["parsed"]["info"]
        token_amount = info.get("tokenAmount", {})
        ui_amount = token_amount.get("uiAmount")
        if ui_amount is None:
            # fallback a raw amount + decimals
            amount = float(token_amount.get("amount", 0))
            decimals = token_amount.get("decimals", 0)
            ui_amount = amount / (10 ** int(decimals)) if decimals else amount
        total += float(ui_amount)
    return total

def get_wallet_daily_mined(wallet_pubkey: str, for_date: Optional[date] = None) -> float:
    if for_date is None:
        for_date = date.today()
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT SUM(amount) as s FROM mining_log WHERE wallet=? AND DATE(created_at)=?", (wallet_pubkey, for_date.isoformat()))
    row = c.fetchone()
    conn.close()
    return float(row["s"] or 0.0)

def record_mining(wallet_pubkey: str, amount: float, tx_sig: Optional[str]):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO mining_log (wallet, amount, tx, created_at) VALUES (?, ?, ?, ?)",
              (wallet_pubkey, amount, tx_sig, datetime.utcnow()))
    conn.commit()
    conn.close()

# -------------------------
# Token transfer (semplice)
# -------------------------
def send_token_reward(dest_wallet: str, amount: float) -> str:
    """
    Esegue l'invio di `amount` token (UI units) dal treasury al wallet destinatario.
    Usa spl.token.client.Token e gestisce la creazione dell'ATA destinazione se necessario.
    Ritorna signature della transazione.
    """
    kp = load_treasury_keypair()
    treasury_pub = kp.public_key
    token = Token(client, PublicKey(TOKEN_MINT), TOKEN_PROGRAM_ID, kp)

    dest_pub = PublicKey(dest_wallet)

    # ottieni decimals del token
    supply_resp = client.get_token_supply(PublicKey(TOKEN_MINT))
    decimals = 0
    try:
        decimals = int(supply_resp["result"]["value"]["decimals"])
    except Exception:
        decimals = 0

    # ATA addresses
    from spl.token.instructions import get_associated_token_address  # potrebbe non essere presente in versioni molto vecchie
    from spl.token.instructions import create_associated_token_account

    # get treasury ATA
    treasury_ata = token.get_or_create_associated_account_info(treasury_pub).address
    # get or create dest ATA
    try:
        dest_ata_info = token.get_or_create_associated_account_info(dest_pub)
        dest_ata = dest_ata_info.address
    except Exception:
        # fallback: costruisci e invia create_associated_token_account
        dest_ata = token.create_associated_token_account(dest_pub)

    # amount in raw (integer)
    raw_amount = int(amount * (10 ** decimals))

    # Eseguo trasferimento
    # Nota: token.transfer usa owner Keypair (treasury) come owner
    tx_sig = token.transfer(
        source=treasury_ata,
        dest=dest_ata,
        owner=kp,
        amount=raw_amount,
        opts=None
    )
    # token.transfer potrebbe ritornare oggetto complesso; normalizza su stringa
    if isinstance(tx_sig, dict):
        return tx_sig.get("result") or str(tx_sig)
    return str(tx_sig)

# -------------------------
# API models
# -------------------------
class MineRequest(BaseModel):
    wallet: str

# -------------------------
# API endpoints
# -------------------------
@app.get("/user_info")
def user_info(wallet: str):
    # Validazione base
    try:
        PublicKey(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Wallet non valido")

    # leggi balance token
    balance = get_token_balance(wallet)

    # diritto a minare (minimo 1 token per vederlo nella UI)
    can_mine = balance >= MIN_HOLD_TO_MINE

    # calcola se ha diritto alla daily quota
    has_quota = balance >= MIN_HOLD_FOR_QUOTA
    daily_quota = DAILY_QUOTA if has_quota else 0.0

    mined_today = get_wallet_daily_mined(wallet)
    mining_left = max(0.0, daily_quota - mined_today)

    # prezzo eur placeholder: puoi collegare oracolo/servizio esterno
    price_eur = float(os.getenv("PRICE_EUR", "0.01"))

    return {
        "wallet": wallet,
        "balance": balance,
        "can_mine": can_mine,
        "has_quota": has_quota,
        "current_reward": DAILY_QUOTA if has_quota else 0.0,
        "mining_left": mining_left,
        "mined_today": mined_today,
        "price_eur": price_eur
    }

@app.post("/mine")
def mine(req: MineRequest):
    wallet = req.wallet
    try:
        PublicKey(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Wallet non valido")

    balance = get_token_balance(wallet)
    if balance < MIN_HOLD_FOR_QUOTA:
        raise HTTPException(status_code=403, detail=f"Non hai i requisiti per minare la quota giornaliera: servono >= {int(MIN_HOLD_FOR_QUOTA)} SOLAY39")

    # calcola quanto rimane oggi
    mined_today = get_wallet_daily_mined(wallet)
    if mined_today >= DAILY_QUOTA:
        return {"success": False, "message": "Hai già raggiunto la quota giornaliera."}

    reward = DAILY_QUOTA - mined_today  # manda il residuo per semplicità (es. se non ancora minato => 50)
    if reward <= 0:
        return {"success": False, "message": "Nessuna ricompensa disponibile oggi."}

    # Esegui trasferimento
    try:
        tx_sig = send_token_reward(wallet, reward)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore invio token: {e}")

    # registra nel DB
    record_mining(wallet, reward, tx_sig)

    return {"success": True, "reward": reward, "tx": tx_sig}
