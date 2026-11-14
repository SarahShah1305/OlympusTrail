# OlympusTrail design plan

## Revised direction

The map carries the character: retain NASA Mars Trek's blue, green and ochre shaded relief, while the surrounding interface uses quiet basalt charcoal and pale mineral grey. This avoids the skill's generic cream-and-terracotta pairing and keeps map colors visible.

- Color: basalt `#202726`, chalk `#F1F2ED`, slate `#66716D`, sea-glass `#176D78`, sun ochre `#E4B84A`, danger `#A43F35`.
- Type: DM Sans for interface and reading; system sans fallbacks. No second display family.
- Layout: the map fills the viewport beneath one compact header; a narrow floating mission sheet occupies the left, while layer controls and the key sit on the map.

```text
┌ OlympusTrail  Base ─ Gear ─ Result         Example trip  Ask guide ┐
│                                                                    │
│  Mission sheet         NASA blue / green / ochre map                │
│  candidate / gear      layer chips · legend     A → ice → return   │
│  verdict and actions                                                  │
└────────────────────────────────────────────────────────────────────┘
```

- Keep one clear action per step and short plain-language labels.
- Use overlays only when selected; their palettes must remain distinguishable from the colored basemap.
- Place all detailed source and model caveats in About, retaining short ice evidence and mission-estimate notes where decisions happen.
- Give the map room; avoid decorative cards and extra labels.

## Self-review against the skill

The earlier cream and terracotta palette matched the skill's named generic default, so the revised palette uses mineral chalk, basalt, sea-glass and map-derived ochre. The map itself supplies the memorable color and texture, so the panel is deliberately quiet. Numbering remains only on the real Base/Gear/Result sequence.
