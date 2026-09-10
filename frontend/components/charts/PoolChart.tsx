"use client";

/**
 * Hand-rolled SVG candlestick chart.
 *
 * Deliberately not a charting library: the pattern overlays here need to
 * draw arbitrary spans tied to specific candle indices (a Head & Shoulders
 * across 30 candles, a support cluster line at a computed price), which is
 * more fighting than help with a general-purpose library's API. The whole
 * chart is one <svg> in a fixed viewBox scaled to the container width.
 */

import { useMemo, useState } from "react";

import { formatDate, formatPrice, formatTimestamp } from "@/lib/api";
import type { Candle, Pattern, PriceLevel } from "@/lib/types";

const VIEW_WIDTH = 1000;
const VIEW_HEIGHT = 460;
const PADDING = { top: 16, right: 74, bottom: 28, left: 12 };
const PLOT_WIDTH = VIEW_WIDTH - PADDING.left - PADDING.right;
const PLOT_HEIGHT = VIEW_HEIGHT - PADDING.top - PADDING.bottom;

const BULL = "#22c55e";
const BEAR = "#ef4444";
const GRID = "#27272a";
const AXIS_TEXT = "#71717a";

interface PoolChartProps {
  candles: Candle[];
  supportResistance?: PriceLevel[];
  patterns?: Pattern[];
  baseSymbol: string;
}

export default function PoolChart({
  candles,
  supportResistance = [],
  patterns = [],
  baseSymbol,
}: PoolChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  /**
   * Only the strongest support and the strongest resistance get drawn.
   * The backend returns up to three of each, and rendering them all
   * turned the chart into a thicket of near-identical dashed lines that
   * obscured the price action they were supposed to annotate. The full
   * ranked list still shows in the levels panel beside the chart.
   */
  const drawnLevels = useMemo(() => {
    const strongest = (kind: PriceLevel["kind"]) =>
      supportResistance
        .filter((level) => level.kind === kind)
        .sort((a, b) => b.strength - a.strength)[0];
    return [strongest("support"), strongest("resistance")].filter(
      (level): level is PriceLevel => Boolean(level),
    );
  }, [supportResistance]);

  const scale = useMemo(() => {
    if (candles.length === 0) return null;

    const lows = candles.map((c) => c.low);
    const highs = candles.map((c) => c.high);
    // Drawn levels can sit outside the candle range; include them so a
    // line never lands off the edge of the plot.
    const levelPrices = drawnLevels.map((l) => l.price);
    const min = Math.min(...lows, ...levelPrices);
    const max = Math.max(...highs, ...levelPrices);
    const span = max - min || Math.max(max * 0.01, 1);
    const paddedMin = min - span * 0.08;
    const paddedMax = max + span * 0.08;

    const priceToY = (price: number) =>
      PADDING.top +
      PLOT_HEIGHT -
      ((price - paddedMin) / (paddedMax - paddedMin)) * PLOT_HEIGHT;

    const slot = PLOT_WIDTH / candles.length;
    const indexToX = (index: number) => PADDING.left + slot * (index + 0.5);

    return { priceToY, indexToX, slot, paddedMin, paddedMax };
  }, [candles, drawnLevels]);

  if (!scale || candles.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950 text-sm text-zinc-500">
        No candles to chart.
      </div>
    );
  }

  const { priceToY, indexToX, slot, paddedMin, paddedMax } = scale;
  const bodyWidth = Math.max(1.4, Math.min(slot * 0.62, 14));

  const gridPrices = Array.from({ length: 5 }, (_, i) => {
    return paddedMin + ((paddedMax - paddedMin) * i) / 4;
  });

  // Multi-candle formations get a box; single-candle shapes get a small
  // arrow marker instead, since a box around one candle is meaningless.
  const spanPatterns = patterns.filter(
    (p) => p.category !== "candlestick" || p.end_timestamp !== p.start_timestamp,
  );
  const markerPatterns = patterns.filter(
    (p) => p.category === "candlestick" && p.end_timestamp === p.start_timestamp,
  );
  const timestampToIndex = new Map(candles.map((c, i) => [c.timestamp, i]));

  const hovered = hoverIndex === null ? null : candles[hoverIndex];

  // A year of daily candles doesn't want "Sep 10, 02:00" on the axis, and
  // three labels is too sparse to read once there are hundreds of bars.
  const spanSeconds =
    candles[candles.length - 1].timestamp - candles[0].timestamp;
  const spansMultipleDays = spanSeconds > 3 * 86400;
  const labelCount = candles.length > 120 ? 5 : 3;
  const axisIndices = Array.from({ length: labelCount }, (_, i) =>
    Math.round((i * (candles.length - 1)) / (labelCount - 1)),
  );

  function handleMove(event: React.MouseEvent<SVGRectElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left) / rect.width;
    const index = Math.floor(ratio * candles.length);
    setHoverIndex(Math.max(0, Math.min(candles.length - 1, index)));
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-2">
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${baseSymbol} price candles`}
      >
        {/* horizontal grid + price axis */}
        {gridPrices.map((price) => (
          <g key={price}>
            <line
              x1={PADDING.left}
              x2={PADDING.left + PLOT_WIDTH}
              y1={priceToY(price)}
              y2={priceToY(price)}
              stroke={GRID}
              strokeWidth={1}
            />
            <text
              x={PADDING.left + PLOT_WIDTH + 6}
              y={priceToY(price) + 4}
              fill={AXIS_TEXT}
              fontSize={11}
              fontFamily="ui-monospace, monospace"
            >
              {formatPrice(price)}
            </text>
          </g>
        ))}

        {/* Bounded boxes around each multi-candle formation.
            Earlier these were full-height tint bands, which read as vague
            vertical stripes and said nothing about *where* the pattern
            sits — a box drawn to the actual high/low of the candles it
            spans shows the formation itself. */}
        {spanPatterns.map((pattern, i) => {
          const start = timestampToIndex.get(pattern.start_timestamp);
          const end = timestampToIndex.get(pattern.end_timestamp);
          if (start === undefined || end === undefined) return null;

          const spanned = candles.slice(start, end + 1);
          if (spanned.length === 0) return null;
          const top = Math.max(...spanned.map((c) => c.high));
          const bottom = Math.min(...spanned.map((c) => c.low));

          const x = indexToX(start) - slot / 2;
          const width = Math.max(indexToX(end) - indexToX(start) + slot, 6);
          // A little breathing room so the box doesn't clip the wicks.
          const yTop = priceToY(top) - 6;
          const height = Math.max(priceToY(bottom) - priceToY(top) + 12, 12);
          const tint =
            pattern.direction === "bullish" ? BULL : pattern.direction === "bearish" ? BEAR : "#a1a1aa";

          return (
            <g key={`${pattern.name}-${pattern.start_timestamp}-${i}`}>
              <rect
                x={x}
                y={yTop}
                width={width}
                height={height}
                fill={tint}
                fillOpacity={0.08}
                stroke={tint}
                strokeOpacity={0.65}
                strokeWidth={1}
                strokeDasharray="4 3"
                rx={3}
              />
              <text
                x={x + 4}
                y={yTop - 4}
                fill={tint}
                fontSize={10}
                opacity={0.95}
              >
                {pattern.name}
              </text>
            </g>
          );
        })}

        {/* Single-candle patterns get a small marker rather than a box —
            a box around one candle is just a thicker candle. */}
        {markerPatterns.map((pattern, i) => {
          const index = timestampToIndex.get(pattern.end_timestamp);
          if (index === undefined) return null;
          const candle = candles[index];
          const bullish = pattern.direction === "bullish";
          const tint = bullish ? BULL : pattern.direction === "bearish" ? BEAR : "#a1a1aa";
          const x = indexToX(index);
          // Bullish markers sit under the low, bearish above the high, so
          // the marker points at the candle from the side the signal implies.
          const y = bullish ? priceToY(candle.low) + 9 : priceToY(candle.high) - 9;
          const dir = bullish ? -1 : 1;
          return (
            <polygon
              key={`m-${pattern.name}-${pattern.end_timestamp}-${i}`}
              points={`${x},${y + dir * -4} ${x - 3.5},${y + dir * 3} ${x + 3.5},${y + dir * 3}`}
              fill={tint}
              opacity={0.85}
            >
              <title>
                {pattern.name} · {Math.round(pattern.confidence * 100)}%
              </title>
            </polygon>
          );
        })}

        {/* strongest support + strongest resistance only */}
        {drawnLevels.map((level) => (
          <g key={`${level.kind}-${level.price}`}>
            <line
              x1={PADDING.left}
              x2={PADDING.left + PLOT_WIDTH}
              y1={priceToY(level.price)}
              y2={priceToY(level.price)}
              stroke={level.kind === "support" ? BULL : BEAR}
              strokeWidth={1.25}
              strokeDasharray="6 4"
              opacity={0.8}
            />
            <text
              x={PADDING.left + 4}
              y={priceToY(level.price) - 5}
              fill={level.kind === "support" ? BULL : BEAR}
              fontSize={10.5}
              opacity={0.95}
            >
              {level.kind === "support" ? "Support" : "Resistance"} {formatPrice(level.price)} ·{" "}
              {level.touches} touches
            </text>
          </g>
        ))}

        {/* candles */}
        {candles.map((candle, i) => {
          const rising = candle.close >= candle.open;
          const color = rising ? BULL : BEAR;
          const x = indexToX(i);
          const bodyTop = priceToY(Math.max(candle.open, candle.close));
          const bodyBottom = priceToY(Math.min(candle.open, candle.close));
          return (
            <g key={candle.timestamp}>
              <line
                x1={x}
                x2={x}
                y1={priceToY(candle.high)}
                y2={priceToY(candle.low)}
                stroke={color}
                strokeWidth={1}
              />
              <rect
                x={x - bodyWidth / 2}
                y={bodyTop}
                width={bodyWidth}
                height={Math.max(bodyBottom - bodyTop, 1)}
                fill={color}
              />
            </g>
          );
        })}

        {/* time axis: evenly-spaced labels, date-only once the window is
            wide enough that the clock time is noise */}
        {axisIndices.map((i, position) => (
          <text
            key={`t-${i}`}
            x={indexToX(i)}
            y={VIEW_HEIGHT - 8}
            fill={AXIS_TEXT}
            fontSize={11}
            textAnchor={
              position === 0 ? "start" : position === axisIndices.length - 1 ? "end" : "middle"
            }
          >
            {spansMultipleDays
              ? formatDate(candles[i].timestamp)
              : formatTimestamp(candles[i].timestamp)}
          </text>
        ))}

        {/* crosshair + tooltip */}
        {hovered && hoverIndex !== null && (
          <g pointerEvents="none">
            <line
              x1={indexToX(hoverIndex)}
              x2={indexToX(hoverIndex)}
              y1={PADDING.top}
              y2={PADDING.top + PLOT_HEIGHT}
              stroke="#a1a1aa"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <g
              transform={`translate(${Math.min(
                indexToX(hoverIndex) + 10,
                PADDING.left + PLOT_WIDTH - 190,
              )}, ${PADDING.top + 8})`}
            >
              <rect width={186} height={92} rx={6} fill="#18181b" stroke="#3f3f46" />
              <text x={10} y={20} fill="#e4e4e7" fontSize={11} fontFamily="ui-monospace, monospace">
                {formatTimestamp(hovered.timestamp)}
              </text>
              {[
                ["O", hovered.open],
                ["H", hovered.high],
                ["L", hovered.low],
                ["C", hovered.close],
              ].map(([label, value], row) => (
                <text
                  key={label as string}
                  x={10 + (row % 2) * 92}
                  y={40 + Math.floor(row / 2) * 16}
                  fill="#a1a1aa"
                  fontSize={11}
                  fontFamily="ui-monospace, monospace"
                >
                  {label as string}{" "}
                  <tspan fill="#e4e4e7">{formatPrice(value as number)}</tspan>
                </text>
              ))}
              <text x={10} y={80} fill="#a1a1aa" fontSize={11} fontFamily="ui-monospace, monospace">
                {hovered.trade_count} trades
              </text>
            </g>
          </g>
        )}

        {/* invisible hit area drives the crosshair */}
        <rect
          x={PADDING.left}
          y={PADDING.top}
          width={PLOT_WIDTH}
          height={PLOT_HEIGHT}
          fill="transparent"
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
        />
      </svg>
    </div>
  );
}
