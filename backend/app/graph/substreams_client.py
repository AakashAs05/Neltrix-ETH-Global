"""Stub for a custom Substreams OHLCV module.

Not built for the hackathon deadline: standardized_query.py + candle_builder.py
already satisfy the Graph composability requirement (one query shape across
Uniswap V3 and SushiSwap, both Messari "dex-amm" subgraphs) without needing
a hand-authored Substreams package. This file is a placeholder in case
Day 4-5 leave slack to add a real Substreams module (e.g. via the
Substreams SKILLs one-prompt generator) that streams swap events directly
from Firehose instead of querying an already-indexed subgraph.
"""

from __future__ import annotations


def get_candles_via_substreams(*_args, **_kwargs):
    raise NotImplementedError(
        "Substreams path not implemented, the standardized-subgraph query "
        "path (standardized_query.py + candle_builder.py) is the one in use."
    )
