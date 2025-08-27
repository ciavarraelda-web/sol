const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");
const { Connection, PublicKey, Keypair, sendAndConfirmTransaction, Transaction } = require("@solana/web3.js");
const { getOrCreateAssociatedTokenAccount, transfer } = require("@solana/spl-token");
const axios = require("axios");

const app = express();
app.use(bodyParser.json());
app.use(cors());

// CONFIGURATION
const TOKEN_MINT = new PublicKey("P7rFSsngQyDaJb3fqDP49XJBz2qLnVkLxdD9yt4Yray");
const APP_WALLET = Keypair.fromSecretKey(Buffer.from(process.env.APP_WALLET_SECRET, "base64")); // secret from environment
const CONNECTION = new Connection("https://api.mainnet-beta.solana.com");
const DAILY_LIMIT = 2000;
const FULL_REWARD_BALANCE = 100000;
const BASE_REWARD = 50.0;
const MIN_HOLD = 1;
const USER_MINING_DB = {}; // For demo, use DB in production

// Helper: get token price (Birdeye API)
async function getTokenPriceEUR() {
    try {
        let resp = await axios.get("https://public-api.birdeye.so/public/price", {
            params: { address: TOKEN_MINT.toString() },
            headers: { "x-api-key": process.env.BIRDEYE_API_KEY }
        });
        return resp.data.data.value || 1; // fallback
    } catch (err) {
        return 1;
    }
}

// Helper: get user balance
async function getUserBalance(wallet) {
    try {
        const tokenAccountInfos = await CONNECTION.getParsedTokenAccountsByOwner(
            new PublicKey(wallet),
            { mint: TOKEN_MINT }
        );
        if (tokenAccountInfos.value.length === 0) return 0;
        return parseFloat(tokenAccountInfos.value[0].account.data.parsed.info.tokenAmount.uiAmountString || "0");
    } catch (err) {
        return 0;
    }
}

// Helper: get user's mining today
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

// Reward calculation function
function calcReward(balance, price_eur) {
    let reward = balance >= FULL_REWARD_BALANCE ? BASE_REWARD : Math.round(BASE_REWARD * (balance / FULL_REWARD_BALANCE) * 100) / 100;
    let reduction = Math.floor(price_eur) * 0.1;
    reward = Math.round(reward * (1 - reduction) * 100) / 100;
    if (reward < 0.1) reward = 0.1;
    return reward;
}

// USER INFO ENDPOINT
app.get("/api/user_info", async (req, res) => {
    const wallet = req.query.wallet;
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

// MINE ENDPOINT
app.post("/api/mine", async (req, res) => {
    const wallet = req.body.wallet;
    const balance = await getUserBalance(wallet);
    const price_eur = await getTokenPriceEUR();
    if (balance < MIN_HOLD) return res.json({ success: false, message: "You do not hold SOLAY39." });

    let reward = calcReward(balance, price_eur);
    const mining_today = getUserMiningToday(wallet);
    let mining_left = DAILY_LIMIT - mining_today;
    if (mining_left < reward) return res.json({ success: false, message: "Daily mining limit reached." });

    // Send token to user
    try {
        const senderTokenAccount = await getOrCreateAssociatedTokenAccount(CONNECTION, APP_WALLET, TOKEN_MINT, APP_WALLET.publicKey);
        const recipientTokenAccount = await getOrCreateAssociatedTokenAccount(CONNECTION, APP_WALLET, TOKEN_MINT, new PublicKey(wallet));
        const tx = new Transaction().add(
            transfer(
                senderTokenAccount.address,
                recipientTokenAccount.address,
                APP_WALLET.publicKey,
                Math.round(reward * 1_000_000) // decimals=6
            )
        );
        const signature = await sendAndConfirmTransaction(CONNECTION, tx, [APP_WALLET]);
        updateUserMining(wallet, reward);
        res.json({ success: true, reward, tx: signature });
    } catch (err) {
        res.json({ success: false, message: "Token transfer failed." });
    }
});

app.listen(3000, () => console.log("API listening on port 3000"));
