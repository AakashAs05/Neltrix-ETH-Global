/**
 * Thin fetch wrappers around the FastAPI backend.
 *
 * The backend surfaces its failures as FastAPI `{ "detail": "..." }` bodies
 * (a 502 when The Graph's indexers misbehave, a 400 when a pool has too
 * little history to build candles from). Those messages are genuinely
 * useful to show the user, so unwrapError pulls them out instead of
 * throwing a bare "Request failed".
 */

import type {
  AnalyseRequest,
  AnalyseResponse,
  OhlcvResponse,
  Pool,
  Protocol,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function unwrapError(response: Response): Promise<never> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // Non-JSON error body (a proxy error page, say) — keep the status text.
  }
  throw new ApiError(detail, response.status);
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    return unwrapError(response);
  }
  return (await response.json()) as T;
}

export function fetchProtocols(): Promise<Protocol[]> {
  return getJson<Protocol[]>("/api/protocols");
}

export function fetchPools(protocol: string, limit = 20): Promise<Pool[]> {
  const params = new URLSearchParams({ protocol, limit: String(limit) });
  return getJson<Pool[]>(`/api/pools?${params}`);
}

export function fetchOhlcv(params: {
  protocol: string;
  pool: string;
  interval?: string;
  range?: string;
}): Promise<OhlcvResponse> {
  const query = new URLSearchParams({
    protocol: params.protocol,
    pool: params.pool,
    interval: params.interval ?? "1h",
    range: params.range ?? "1w",
  });
  return getJson<OhlcvResponse>(`/api/ohlcv?${query}`);
}

export function analyse(request: AnalyseRequest): Promise<AnalyseResponse> {
  return getJson<AnalyseResponse>("/api/analyse", {
    method: "POST",
    body: JSON.stringify({
      interval: "1h",
      range: "1w",
      ...request,
    }),
  });
}

/** Compact USD formatting for TVL/volume figures that run into the billions. */
export function formatUsd(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(2)}`;
}

export function formatPrice(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: value < 1 ? 6 : 2,
  });
}

/** Date without the clock, for axes spanning more than a few days. */
export function formatDate(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "2-digit",
  });
}

export function formatTimestamp(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Pool ids are 42-char addresses on V3/Sushi and 66-char hashes on V4. */
export function shortenId(id: string): string {
  return id.length <= 14 ? id : `${id.slice(0, 8)}…${id.slice(-6)}`;
}
