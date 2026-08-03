# GitHub Corner — Reusable Component

## Overview

Animated "Fork me on GitHub" SVG ribbon in the top-right corner. Hover triggers an octocat arm wave animation. Available in two placements: `absolute` (within a positioned parent) or `fixed` (always visible).

## Implementation

### HTML

```html
<a href="https://github.com/YOUR_USER/YOUR_REPO"
   class="github-corner" target="_blank"
   aria-label="View source on GitHub">
  <svg viewBox="0 0 250 250" aria-hidden="true">
    <path d="M0,0 L115,115 L130,115 L142,142 L250,250 L250,0 Z"></path>
    <path d="M128.3,109.0 C113.8,99.7 ..." fill="currentColor"
          style="transform-origin:130px 106px;" class="octo-arm">
    </path>
    <path d="M115.0,115.0 C114.9,115.1 ..." fill="currentColor"
          class="octo-body">
    </path>
  </svg>
</a>
```

> The `...` paths above are abbreviated. Full path definition see `index.html` in http-server-cli project.

### CSS

```css
.github-corner { position: absolute; top: 0; right: 0; z-index: 10; }
.github-corner svg {
  fill: var(--gh-corner-fill, #30363d);
  color: var(--gh-octocat, #fff);
  width: 72px; height: 72px;
  transition: fill 0.2s;
}
.github-corner:hover svg { fill: var(--gh-corner-hover, #58a6ff); }

/* Octocat arm animation */
.github-corner .octo-arm { transform-origin: 130px 106px; }
.github-corner:hover .octo-arm { animation: octocat-wave 560ms ease-in-out; }

@keyframes octocat-wave {
  0%, 100% { transform: rotate(0); }
  20%, 60% { transform: rotate(-25deg); }
  40%, 80% { transform: rotate(10deg); }
}

/* Mobile: always animate (no hover on touch) */
@media (max-width: 480px) {
  .github-corner:hover .octo-arm { animation: none; }
  .github-corner .octo-arm { animation: octocat-wave 560ms ease-in-out; }
}
```

## Variants

### Absolute (inside content flow)
Use when the corner should scroll with the page:

```css
body { position: relative; }
.github-corner { position: absolute; top: 0; right: 0; }
```

### Fixed (sticky)
Use when the corner should stay visible regardless of scroll:

```css
.github-corner { position: fixed; top: 0; right: 0; }
```

## Accessibility

- `aria-label` on the anchor provides screen reader context (e.g. "View source on GitHub" or "在 GitHub 上查看源码").
- `aria-hidden="true"` on the SVG prevents decorative icon from being read by screen readers.

## Customization

| Property | CSS Variable | Default | Description |
|:---|:---|:---:|:---|
| Background triangle | `--gh-corner-fill` | `#30363d` | The folded corner triangle |
| Octocat silhouette | `--gh-octocat` | `#ffffff` | The cat and arm paths use `color` |
| Hover color | `--gh-corner-hover` | `#58a6ff` | Both triangle and octocat on hover |

## Pitfalls

- **`position: absolute` requires a positioned parent** — add `position: relative` to `<body>` or a wrapper `<div>`.
- **SVG inline only** — external SVG files lose `currentColor` binding and animation control. Always inline the SVG.
- **`fill` vs `color` in SVG** — triangle uses `fill`, octocat paths use `currentColor` (which reads from the SVG element's `color` property).
- **Right edge padding** — on very narrow screens, 72px corner may overlap content. Set `.toolbar { right: 72px; }` to avoid collision.

## Source

Adapted from [tholman/github-corners](https://github.com/tholman/github-corners).
