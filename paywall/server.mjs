/**
 * x402 payment gateway for the Neltrix analysis API.
 *
 * Sits in front of the FastAPI service and gates exactly one route,
 * POST /api/analyse, behind a per-call HBAR payment settled on Hedera
 * testnet through the Blocky402 facilitator. Everything else — protocol
 * and pool discovery, health — proxies through free, so the UI can still
 * browse pools without paying and only the expensive call costs money.
 *
 * Why a Node sidecar rather than doing this inside FastAPI: the x402
 * reference implementation (@x402/hedera, @x402/express) is TypeScript,
 * and re-implementing Hedera transaction construction and signature
 * verification in Python would mean hand-rolling the parts of the spec
 * most likely to be subtly wrong. The sidecar speaks the official
 * implementation and forwards verified requests over localhost.
 *
 * Flow:
 *   client -> POST /api/analyse (no payment)
 *          <- 402 + PaymentRequirements (payTo, amount, hedera:testnet)
 *   client -> POST /api/analyse + X-PAYMENT (signed Hedera transfer)
 *          -> facilitator /verify, then the upstream call, then /settle
 *          <- 200 + analysis JSON + X-PAYMENT-RESPONSE (tx hash)
 */

import express from "express";
import dotenv from "dotenv";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { paymentMiddlewareFromConfig } from "@x402/express";
import { ExactHederaScheme } from "@x402/hedera/exact/server";

dotenv.config({ path: "../.env" });

const {
  HEDERA_NETWORK = "hedera:testnet",
  X402_FACILITATOR_URL = "https://api.testnet.blocky402.com",
  HEDERA_MERCHANT_ACCOUNT_ID,
  X402_PRICE_TINYBARS = "10000000",
  X402_ASSET = "0.0.0",
} = process.env;

const UPSTREAM = process.env.NELTRIX_API_URL ?? "http://127.0.0.1:8000";
const PORT = Number(process.env.PAYWALL_PORT ?? 8402);
const PAID_ROUTE = "POST /api/analyse";

if (!HEDERA_MERCHANT_ACCOUNT_ID) {
  console.error("HEDERA_MERCHANT_ACCOUNT_ID is not set — see .env.example");
  process.exit(1);
}

const app = express();
app.use(express.json({ limit: "1mb" }));

// The browser UI calls this from a different origin, and the x402 headers
// are custom ones that CORS blocks by default unless explicitly allowed
// and exposed — without X-PAYMENT-RESPONSE being *exposed*, a browser
// client can read the body but never the settlement receipt.
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", req.headers.origin ?? "*");
  // x402 v2 uses unprefixed header names: the client sends
  // PAYMENT-SIGNATURE, the 402 carries PAYMENT-REQUIRED, and the
  // settlement receipt comes back as PAYMENT-RESPONSE. X-PAYMENT is kept
  // allowed for v1-style clients.
  res.header("Access-Control-Allow-Headers", "Content-Type, PAYMENT-SIGNATURE, X-PAYMENT");
  res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.header("Access-Control-Expose-Headers", "PAYMENT-RESPONSE, PAYMENT-REQUIRED");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

const facilitator = new HTTPFacilitatorClient({ url: X402_FACILITATOR_URL });

const routes = {
  [PAID_ROUTE]: {
    accepts: [
      {
        scheme: "exact",
        network: HEDERA_NETWORK,
        payTo: HEDERA_MERCHANT_ACCOUNT_ID,
        // HBAR, denominated in tinybars (1 HBAR = 100_000_000).
        price: { asset: X402_ASSET, amount: String(X402_PRICE_TINYBARS) },
        maxTimeoutSeconds: 120,
      },
    ],
    description: "Onchain pattern analysis for one DEX pool",
    serviceName: "Neltrix Onchain",
    mimeType: "application/json",
  },
};

app.use(
  paymentMiddlewareFromConfig(routes, facilitator, [
    { network: HEDERA_NETWORK, server: new ExactHederaScheme() },
  ]),
);

/** Forward a request upstream to FastAPI once payment has been verified. */
async function proxy(req, res) {
  const url = `${UPSTREAM}${req.originalUrl}`;
  try {
    const hasBody = req.method !== "GET" && req.method !== "HEAD";
    const upstream = await fetch(url, {
      method: req.method,
      headers: { "Content-Type": "application/json" },
      body: hasBody ? JSON.stringify(req.body ?? {}) : undefined,
    });
    const text = await upstream.text();
    res.status(upstream.status);
    res.type(upstream.headers.get("content-type") ?? "application/json");
    res.send(text);
  } catch (err) {
    // The sidecar is useless without the analysis service behind it, and
    // "connection refused" is far more actionable than a generic 500.
    res.status(502).json({
      detail: `Paywall could not reach the analysis API at ${UPSTREAM}: ${err.message}`,
    });
  }
}

app.get("/paywall/health", (_req, res) =>
  res.json({
    status: "ok",
    paidRoute: PAID_ROUTE,
    network: HEDERA_NETWORK,
    facilitator: X402_FACILITATOR_URL,
    payTo: HEDERA_MERCHANT_ACCOUNT_ID,
    priceTinybars: X402_PRICE_TINYBARS,
    priceHbar: Number(X402_PRICE_TINYBARS) / 1e8,
    upstream: UPSTREAM,
  }),
);

app.all("/{*any}", proxy);

app.listen(PORT, () => {
  console.log(`x402 paywall listening on http://127.0.0.1:${PORT}`);
  console.log(`  paid route : ${PAID_ROUTE}`);
  console.log(`  price      : ${Number(X402_PRICE_TINYBARS) / 1e8} HBAR -> ${HEDERA_MERCHANT_ACCOUNT_ID}`);
  console.log(`  network    : ${HEDERA_NETWORK} via ${X402_FACILITATOR_URL}`);
  console.log(`  upstream   : ${UPSTREAM}`);
});
