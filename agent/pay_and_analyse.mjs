/**
 * An agent that BUYS A DATA PRODUCT — one analysis report — autonomously.
 *
 * To be unambiguous about what "pays" means here: this agent is a
 * *customer of an API*. It spends 0.1 HBAR to purchase a single
 * /api/analyse response, the way you might pay per query for market data.
 * It does not trade, does not swap tokens, does not act on the analysis
 * it receives, and holds no position anywhere. The only money that moves
 * is the API fee.
 *
 * What that demonstrates is the payment rail, not a trading strategy.
 * Normally software can only use a paid API after a *human* creates an
 * account, enters a card and pastes an API key into config. An autonomous
 * agent can do none of those things. x402 removes all of it: the agent
 * calls an endpoint it has never seen, is told the price in the 402
 * response, pays, and is served — with no account and no prior
 * relationship with the service.
 *
 * Swap this analysis for any other paid API and the mechanism is identical.
 *
 * Demonstrates the full x402 handshake against the Neltrix paywall with
 * no human in the loop and no prior arrangement with the service:
 *
 *   1. Call POST /api/analyse cold. No API key, no account, no payment.
 *   2. Receive 402 Payment Required. The response *itself* carries the
 *      price, the asset, the recipient and the network — everything
 *      needed to pay is discovered here, not configured ahead of time.
 *   3. Build and sign a Hedera transfer for exactly that amount. The
 *      transaction is only partially signed: the facilitator's fee-payer
 *      account co-signs and covers network fees.
 *   4. Retry the same call with the signed transaction in X-PAYMENT.
 *   5. The service verifies, settles on Hedera testnet, and returns the
 *      analysis plus a settlement receipt.
 *
 * Run with `npm start` from this directory.
 */

import dotenv from "dotenv";
import { PrivateKey } from "@hiero-ledger/sdk";
import { x402Client, x402HTTPClient } from "@x402/core/client";
import { ExactHederaScheme } from "@x402/hedera/exact/client";
import { createClientHederaSigner } from "@x402/hedera";

dotenv.config({ path: "../.env" });

const {
  HEDERA_NETWORK = "hedera:testnet",
  HEDERA_AGENT_ACCOUNT_ID,
  HEDERA_AGENT_PRIVATE_KEY,
} = process.env;

const PAYWALL_URL = process.env.PAYWALL_URL ?? "http://127.0.0.1:8402";
// Hard ceiling this agent will pay for a single call, in tinybars.
const MAX_PAYMENT_TINYBARS = process.env.AGENT_MAX_PAYMENT_TINYBARS ?? "50000000";
const MIRROR_NODE = "https://testnet.mirrornode.hedera.com";

const REQUEST = {
  protocol: "uniswap-v4-ethereum",
  pool: "0x21c67e77068de97969ba93d4aab21826d33ca12bb9f565d8496e8fda8a82ca27",
  interval: "1h",
  range: "1w",
};

if (!HEDERA_AGENT_ACCOUNT_ID || !HEDERA_AGENT_PRIVATE_KEY) {
  console.error("Set HEDERA_AGENT_ACCOUNT_ID and HEDERA_AGENT_PRIVATE_KEY in .env");
  process.exit(1);
}

const step = (n, msg) => console.log(`\n[${n}] ${msg}`);
const hbar = (tinybars) => `${(Number(tinybars) / 1e8).toFixed(4)} HBAR`;

async function balanceOf(accountId) {
  const res = await fetch(`${MIRROR_NODE}/api/v1/accounts/${accountId}`);
  if (!res.ok) return null;
  return (await res.json()).balance.balance;
}

async function main() {
  console.log("Neltrix x402 agent");
  console.log(`  paywall : ${PAYWALL_URL}`);
  console.log(`  payer   : ${HEDERA_AGENT_ACCOUNT_ID} on ${HEDERA_NETWORK}`);

  const before = await balanceOf(HEDERA_AGENT_ACCOUNT_ID);
  console.log(`  balance : ${hbar(before)}`);
  console.log(`  budget  : max ${hbar(MAX_PAYMENT_TINYBARS)} per call`);

  // --- 1. Call without paying, to discover the price -------------------
  step(1, "Requesting the analysis with no payment attached…");
  const unpaid = await fetch(`${PAYWALL_URL}/api/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(REQUEST),
  });

  if (unpaid.status !== 402) {
    console.error(`Expected 402 Payment Required, got ${unpaid.status}.`);
    console.error(await unpaid.text());
    process.exit(1);
  }
  console.log("    -> 402 Payment Required");

  // --- 2. Read the terms out of the 402 itself -------------------------
  const signer = createClientHederaSigner(
    HEDERA_AGENT_ACCOUNT_ID,
    PrivateKey.fromStringECDSA(HEDERA_AGENT_PRIVATE_KEY),
    { network: HEDERA_NETWORK },
  );
  const client = new x402Client().register(HEDERA_NETWORK, new ExactHederaScheme(signer));

  // An autonomous payer needs a ceiling. By default the client only
  // permits assets it recognizes (USDC and friends) under a $1 cap, which
  // rejects native HBAR outright — so HBAR is opted in explicitly, with a
  // hard per-payment cap in tinybars. A service that answered the 402 with
  // a larger price than this would be refused before anything is signed,
  // which is the behaviour you want from an agent spending real money.
  client.setSpendControls({
    allowedAssets: [
      {
        network: HEDERA_NETWORK,
        asset: "0.0.0",
        maxAmountPerPayment: MAX_PAYMENT_TINYBARS,
      },
    ],
  });

  const http = new x402HTTPClient(client);

  const paymentRequired = http.getPaymentRequiredResponse(
    (name) => unpaid.headers.get(name),
    await unpaid.clone().json().catch(() => undefined),
  );
  const terms = paymentRequired.accepts[0];

  step(2, "Payment terms discovered from the 402 response:");
  console.log(`    scheme   : ${terms.scheme} on ${terms.network}`);
  console.log(`    price    : ${hbar(terms.amount)} (${terms.amount} tinybars)`);
  console.log(`    asset    : ${terms.asset === "0.0.0" ? "HBAR (native)" : terms.asset}`);
  console.log(`    payTo    : ${terms.payTo}`);
  console.log(`    feePayer : ${terms.extra?.feePayer} (facilitator covers network fees)`);

  // --- 3. Sign a transfer for exactly that amount ----------------------
  step(3, "Building and signing the Hedera transfer…");
  const payload = await client.createPaymentPayload(paymentRequired);
  const headers = http.encodePaymentSignatureHeader(payload);
  console.log(`    -> signed, ${Object.keys(headers).join(", ")} header prepared`);

  // --- 4. Retry with payment attached ----------------------------------
  step(4, "Retrying the same request with payment…");
  const paid = await fetch(`${PAYWALL_URL}/api/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(REQUEST),
  });
  console.log(`    -> HTTP ${paid.status}`);

  if (!paid.ok) {
    console.error("Payment was rejected:");
    console.error(await paid.text());
    process.exit(1);
  }

  // --- 5. Settlement receipt + the thing we actually bought ------------
  const receiptHeader = paid.headers.get("payment-response");
  if (receiptHeader) {
    const receipt = JSON.parse(Buffer.from(receiptHeader, "base64").toString("utf8"));
    step(5, "Settlement receipt:");
    console.log(`    success     : ${receipt.success}`);
    console.log(`    network     : ${receipt.network ?? HEDERA_NETWORK}`);
    if (receipt.transaction) {
      console.log(`    transaction : ${receipt.transaction}`);
      console.log(`    explorer    : https://hashscan.io/testnet/transaction/${receipt.transaction}`);
    }
    if (receipt.payer) console.log(`    payer       : ${receipt.payer}`);
  } else {
    console.warn("    (no PAYMENT-RESPONSE header returned — settlement receipt unavailable)");
  }

  const analysis = await paid.json();
  step(6, "Data product received — this is the goods the 0.1 HBAR bought:");
  console.log(`    pool      : ${analysis.protocol} ${analysis.pool.slice(0, 10)}…`);
  console.log(`    candles   : ${analysis.candles.length} × ${analysis.interval} over ${analysis.range}`);
  console.log(`    source    : ${analysis.series.source}`);
  console.log(`    patterns  : ${analysis.patterns.length} significant of ${analysis.total_detected} raw`);
  console.log(`    verdict   : ${analysis.verdict.direction.toUpperCase()} @ ${Math.round(analysis.verdict.confidence * 100)}% confidence`);
  console.log(`    latest    : $${analysis.candles.at(-1).close.toFixed(2)} ${analysis.base_symbol}`);
  console.log(`\n    "${analysis.explanation}"`);

  // Mirror node lags consensus slightly; a short wait makes the balance
  // delta visible in the same run rather than looking like nothing moved.
  await new Promise((r) => setTimeout(r, 6000));
  const after = await balanceOf(HEDERA_AGENT_ACCOUNT_ID);
  step(7, "Cost of the purchase, on Hedera testnet:");
  console.log(`    before : ${hbar(before)}`);
  console.log(`    after  : ${hbar(after)}`);
  console.log(`    delta  : ${hbar(after - before)}`);
  console.log(`\n✅ Purchased 1 analysis report for ${hbar(terms.amount)}.`);
  console.log("   No account, no API key, no subscription — the price was");
  console.log("   discovered from the 402 response and paid in the same exchange.");
  console.log("   (This agent buys data only. It places no trades and holds no position.)");
}

main().catch((err) => {
  console.error("\nAgent failed:", err.message);
  process.exit(1);
});
