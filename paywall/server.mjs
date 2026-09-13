/**
 * x402 payment gateway for the Neltrix analysis API.
 *
 * Gates POST /api/analyse behind a per-call HBAR payment on Hedera testnet
 * and proxies everything else through free. Runs as a Node sidecar because
 * the x402 reference implementation is TypeScript.
 */

import { pathToFileURL } from "node:url";

import express from "express";
import dotenv from "dotenv";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { paymentMiddlewareFromConfig } from "@x402/express";
import { ExactHederaScheme } from "@x402/hedera/exact/server";

dotenv.config({ path: "../.env" });  // no-op in deployment, env comes from the platform

const {
  HEDERA_NETWORK = "hedera:testnet",
  X402_FACILITATOR_URL = "https://api.testnet.blocky402.com",
  HEDERA_MERCHANT_ACCOUNT_ID,
  X402_PRICE_TINYBARS = "10000000",
  X402_ASSET = "0.0.0",
} = process.env;

const UPSTREAM = process.env.NELTRIX_API_URL ?? "http://127.0.0.1:8000";
const PORT = Number(process.env.PAYWALL_PORT ?? 8402);

// Candle fetching is the expensive half of this service: a long window means
// paginating up to 10,000 swap events and spending Graph quota. Detection on
// top of it is arithmetic. So the ceiling on free candles is what actually
// caps our cost, not gating the analysis.
const PAID_ANALYSE = "POST /api/analyse";
const PAID_OHLCV = "GET /api/ohlcv";
const FREE_RANGE = "1d";

if (!HEDERA_MERCHANT_ACCOUNT_ID) {
  console.error("HEDERA_MERCHANT_ACCOUNT_ID is not set, see .env.example");
  process.exit(1);
}

const app = express();
app.use(express.json({ limit: "1mb" }));

// The browser UI calls this from a different origin, and the x402 headers
// are custom ones that CORS blocks by default unless explicitly allowed
// and exposed, without X-PAYMENT-RESPONSE being *exposed*, a browser
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

// Each route gets its own copy: the middleware enriches these in place, so
// sharing one array between routes leaves the second one misconfigured.
const accepts = () => [
  {
    scheme: "exact",
    network: HEDERA_NETWORK,
    payTo: HEDERA_MERCHANT_ACCOUNT_ID,
    // HBAR, denominated in tinybars (1 HBAR = 100_000_000).
    price: { asset: X402_ASSET, amount: String(X402_PRICE_TINYBARS) },
    maxTimeoutSeconds: 120,
  },
];

const routes = {
  [PAID_ANALYSE]: {
    accepts: accepts(),
    description: "Onchain pattern analysis for one DEX pool",
    serviceName: "Neltrix Onchain",
    mimeType: "application/json",
  },
  [PAID_OHLCV]: {
    accepts: accepts(),
    description: `OHLCV candles beyond the free ${FREE_RANGE} window`,
    serviceName: "Neltrix Onchain",
    mimeType: "application/json",
  },
};

// Free tier: one day of candles, no payment. Anything longer falls through to
// the payment middleware below. Registering the route as paid and short
// circuiting the cheap case keeps one price definition rather than two.
function freeTierBypass(req, res, next) {
  if (req.method !== "GET" || !req.path.startsWith("/api/ohlcv")) return next();
  const range = req.query.range ?? FREE_RANGE;
  if (range === FREE_RANGE) return proxy(req, res);
  return next();
}

app.use(freeTierBypass);

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
    paidRoutes: [PAID_ANALYSE, `${PAID_OHLCV} (range beyond ${FREE_RANGE})`],
    freeTier: `GET /api/ohlcv?range=${FREE_RANGE}`,
    network: HEDERA_NETWORK,
    facilitator: X402_FACILITATOR_URL,
    payTo: HEDERA_MERCHANT_ACCOUNT_ID,
    priceTinybars: X402_PRICE_TINYBARS,
    priceHbar: Number(X402_PRICE_TINYBARS) / 1e8,
    upstream: UPSTREAM,
  }),
);

app.all("/{*any}", proxy);

// Serverless platforms import this module and drive it themselves, so only
// bind a port when the file is run directly. Vercel uses the default export.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  app.listen(PORT, () => {
    console.log(`x402 paywall listening on http://127.0.0.1:${PORT}`);
    console.log(`  paid       : ${PAID_ANALYSE}`);
    console.log(`             : ${PAID_OHLCV} beyond range=${FREE_RANGE}`);
    console.log(`  free tier  : GET /api/ohlcv?range=${FREE_RANGE}`);
    console.log(`  price      : ${Number(X402_PRICE_TINYBARS) / 1e8} HBAR -> ${HEDERA_MERCHANT_ACCOUNT_ID}`);
    console.log(`  network    : ${HEDERA_NETWORK} via ${X402_FACILITATOR_URL}`);
    console.log(`  upstream   : ${UPSTREAM}`);
  });
}

export default app;
