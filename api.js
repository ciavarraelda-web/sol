// SOLAY39 Mining Backend API - Node.js/Express
// Versione reale: invia token SPL su Solana

const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");
const { Connection, PublicKey, Keypair, sendAndConfirmTransaction, Transaction } = require("@solana/web3.js");
const { getOrCreateAssociatedTokenAccount, createTransferInstruction } = require("@solana/spl-token");
const axios = require("axios");

// ---------------- CONFIG ----------------
const TOKEN_MINT = new PublicKey("P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray"); // Mint SPL SOLAY39
const DAILY_LIMIT = 2000;                   // Quota mining giornaliera per utente
const FULL_REWARD_BALANCE = 100000;         // Saldo per reward piena
const BASE_REWARD = 50.0;                   // Reward massima per mining
const MIN_HOLD = 1;                         // Minimo token per minare

// Chiave privata del wallet sender come variabile env: APP_WALLET_SECRET (base58)
const APP_WALLET_SECRET = process.env.APP_WALLET_SECRET;
if (!APP_WALLET_SECRET) {
  console.error("Missing APP_WALLET_SECRET env variable!");
  process.exit(1);
}
const bs58 = require("bs58");
const APP_WALLET = Keypair.fromSecretKey(bs58.decode(APP_WALLET_SECRET));

const CONNECTION = new Connection("https://api.mainnet-beta.solana.com");

const USER_MINING_DB = {}; // Demo: in memoria. Usa un DB vero in produzione!

const app = express();
app.use(bodyParser.json());
app.use(cors());

// --------- Helpers ---------
async function getTokenPriceEUR() {
  try {
    let resp = await axios.get("https://public-api.birdeye.so/public/price", {
      params: { address: TOKEN_MINT.toString() },
      headers: { "x-api-key": process.env.BIRDEYE_API_KEY || "" }
    });
    return resp.data.data.value || 1;
  } catch (err) {
    return 1;
  }
}

async function getUserBalance(wallet) {
  try {
    const parsed = await CONNECTION.getParsedTokenAccountsByOwner(new PublicKey(wallet), { mint: TOKEN_MINT });
    if (parsed.value.length === 0) return 0;
    return parseFloat(parsed.value[0].account.data.parsed.info.tokenAmount.uiAmountString || "0");
  } catch (err) {
    return 0;
  }
}

function getUserMiningToday(wallet) {
  const today = new Date().toISOString().slice(0,10);
  if (!USER_MINING_DB[wallet] || USER_MINING_DB[wallet].date !== today) {
    USER_MINING_DB[wallet] = { date: today, mined: 0 };
  }
  return USER_MINING_DB[wallet].mined;
}

function updateUserMining(wallet, amount) {
  const today = new Date().toISOString().slice(0,10);
  if (!USER_MINING_DB[wallet] || USER_MINING_DB[wallet].date !== today) {
    USER_MINING_DB[wallet] = { date: today, mined: 0 };
  }
  USER_MINING_DB[wallet].mined += amount;
}

function calcReward(balance, price_eur) {
  let reward = balance >= FULL_REWARD_BALANCE ? BASE_REWARD : Math.round(BASE_REWARD * (balance / FULL_REWARD_BALANCE) * 100) / 100;
  let reduction = Math.floor(price_eur) * 0.1;
  reward = Math.round(reward * (1 - reduction) * 100) / 100;
  if (reward < 0.1) reward = 0.1;
  return reward;
}

// --------- API ENDPOINTS ---------

// Info utente
app.get("/api/user_info", async (req, res) => {
  const wallet = req.query.wallet;
  if (!wallet) return res.status(400).json({ error: "Missing wallet address" });
  const balance = await getUserBalance(wallet);
  const price_eur = await getTokenPriceEUR();
  let can_mine = balance >= MIN_HOLD;
  let reward = calcReward(balance, price_eur);
  const mining_today = getUserMiningToday(wallet);
  let mining_left = DAILY_LIMIT - mining_today;
  if (mining_left < 0) mining_left = 0;

  res.json({
    balance,
    price_eur,
    current_reward: reward,
    mining_left,
    can_mine
  });
});

// Mining
app.post("/api/mine", async (req, res) => {
  const wallet = req.body.wallet;
  if (!wallet) return res.status(400).json({ success: false, message: "Missing wallet address" });
  const balance = await getUserBalance(wallet);
  const price_eur = await getTokenPriceEUR();
  if (balance < MIN_HOLD) return res.json({ success: false, message: "You do not hold SOLAY39." });

  let reward = calcReward(balance, price_eur);
  const mining_today = getUserMiningToday(wallet);
  let mining_left = DAILY_LIMIT - mining_today;
  if (mining_left < reward) return res.json({ success: false, message: "Daily mining limit reached." });

  // Invio token SPL reale
  try {
    const recipientTokenAccount = await getOrCreateAssociatedTokenAccount(CONNECTION, APP_WALLET, TOKEN_MINT, new PublicKey(wallet));
    const senderTokenAccount = await getOrCreateAssociatedTokenAccount(CONNECTION, APP_WALLET, TOKEN_MINT, APP_WALLET.publicKey);

    const tx = new Transaction().add(
      createTransferInstruction(
        senderTokenAccount.address,
        recipientTokenAccount.address,
        APP_WALLET.publicKey,
        Math.round(reward * 1_000_000) // Decimali SPL
      )
    );

    const signature = await sendAndConfirmTransaction(CONNECTION, tx, [APP_WALLET]);
    updateUserMining(wallet, reward);

    res.json({ success: true, reward, tx: signature });
  } catch (err) {
    res.json({ success: false, message: "Token transfer failed.", error: err.message });
  }
});

// --------- AVVIO SERVER ---------
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`SOLAY39 backend listening on port ${PORT}`));
