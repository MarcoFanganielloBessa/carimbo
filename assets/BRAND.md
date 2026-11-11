# carimbo brand

## Palette

| Name | Hex | Use |
|---|---|---|
| paper | `#F3EFE6` | backgrounds, text on ink |
| ink | `#16151A` | text, lines, dark backgrounds |
| stamp blue | `#2B3BD6` | the mark, the stamp, the hook path in diagrams |
| gray | `#8A8578` | secondary text on paper |
| stamp blue on ink | `#6170F2` | the mark on dark backgrounds (`#2B3BD6` is too dark there) |
| gray on ink | `#A39E90` | secondary text on dark backgrounds |

No gradients, no glow, no shadows.

## The mark

A square office stamp pressed by hand: a thick outer frame, a thin inner frame and a bold lowercase `c`, rotated -6°, in stamp blue. The ink look is geometry, not SVG filters: every outline was sampled into points and pushed by two layers of smooth noise (a slow wobble for uneven pressure and a fine one for ink bleed), and small irregular holes were cut into the inked areas with `fill-rule="evenodd"`. It renders the same in browsers, GitHub `<img>`, and any rasterizer. The square shape is intentional: a `c` inside a circle reads as the copyright sign.

`logo.svg` has a transparent background and works on paper and on white. On dark backgrounds use the stamp-blue-on-ink color, as `banner-dark.svg` does.

## Type

IBM Plex Mono (SemiBold for the wordmark, Regular and Medium for text, Bold for the `c` and the diagram stamp), by IBM, SIL Open Font License 1.1: https://github.com/IBM/plex. License text in `fonts-LICENSE.txt`. All text in the SVGs is converted to outlines, so nothing depends on installed fonts. The wordmark is always lowercase: `carimbo`.

## Files

- `logo.svg`: the mark, 256 x 256
- `banner-light.svg`, `banner-dark.svg`: README header, 1280 x 400
- `social-preview.png`: GitHub social preview, 1280 x 640
- `how-it-works.svg`: flow diagram on its own paper card, readable on light and dark GitHub themes

README header:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
  <img alt="carimbo: decision memory for AI agent teams" src="assets/banner-light.svg">
</picture>
```

## Do and don't

- Do keep the mark in stamp blue only; one color, no outline, no second tint.
- Do keep the -6° tilt and the rough edges; they are what make it a stamp.
- Do leave clear space around the mark of at least a quarter of its width.
- Don't put the `c` in a circle, or redraw the mark with clean geometric strokes.
- Don't add gradients, shadows, emoji, sparkles or brain imagery.
- Don't capitalize the wordmark or set it in another typeface.
- Don't use `#2B3BD6` on the ink background; use `#6170F2`.
- Don't call this palette BOMA's; it belongs to carimbo.
