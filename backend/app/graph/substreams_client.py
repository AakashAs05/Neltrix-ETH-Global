"""Placeholder for a custom Substreams OHLCV module.

Not built: the standardized-subgraph path already satisfies the Graph
composability requirement without hand-authoring a Substreams package.
"""

from __future__ import annotations


def get_candles_via_substreams(*_args, **_kwargs):
    raise NotImplementedError(
        "Substreams path not implemented, the standardized-subgraph query "
        "path (standardized_query.py + candle_builder.py) is the one in use."
    )
