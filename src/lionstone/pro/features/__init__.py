"""Lionstone creative feature engine (Pro / Studio).

Effects, transitions, looks, motion, text presets, keyframes, entitlements,
brand kits and the agent that decides when (and when not) to use them.

Everything renders through the open-source core's existing extension points:
compiled FFmpeg filtergraph fragments (``plan.color["filter"]``) for picture
effects, and registered graphic builders for text — so preview and final
render share one implementation and the free core stays unchanged.
"""

SCHEMA_VERSION = 1
