# Light/Dark Theme Toggle — Reusable Component

## Overview

CSS variable-based light/dark mode that follows system preference, with manual override saved to `localStorage`. Trigger via floating button in the top-right toolbar.

## Architecture

```
prefers-color-scheme (system)
     │
     ├── localStorage has "hs-theme" ? ──→ use saved value
     │
     └── no saved value ──→ follow system
                              │
                              └── listen to OS changes via matchMedia
```

## Implementation

### CSS Variables

Define all colors as CSS custom properties on `:root` (dark as default). Override in `[data-theme="light"]`.

```css
:root {
  --bg-page: #0d1117;
  --bg-card: #161b22;
  --text-primary: #f0f6fc;
  --text-body: #c9d1d9;
  --text-secondary: #8b949e;
  --text-muted: #484f58;
  --text-code: #ffa657;
  --text-link: #58a6ff;
  --text-check: #3fb950;
  --text-accent: #bc8cff;
  --border-default: #30363d;
  --border-light: #21262d;
  --gh-corner-fill: #30363d;
  --gh-corner-hover: #58a6ff;
  --lang-switch-bg: rgba(22, 27, 34, 0.9);
  --lang-toggle-active-bg: #fff;
  --lang-toggle-active-color: #333;
}

[data-theme="light"] {
  --bg-page: #ffffff;
  --bg-card: #f6f8fa;
  --text-primary: #1f2328;
  --text-body: #1f2328;
  --text-secondary: #656d76;
  --text-muted: #656d76;
  --text-code: #0550ae;
  --text-link: #0969da;
  --text-check: #1a7f37;
  --text-accent: #8250df;
  --border-default: #d0d7de;
  --border-light: #d0d7de;
  --gh-corner-fill: #d0d7de;
  --gh-corner-hover: #0969da;
  --lang-switch-bg: rgba(255, 255, 255, 0.9);
  --lang-toggle-active-bg: #0969da;
  --lang-toggle-active-color: #fff;
}
```

### CSS Variable Usage

Every hardcoded color must be replaced with `var(--xxx)`:

```css
body {
  background: var(--bg-page);
  color: var(--text-body);
}

.install-box {
  background: var(--bg-card);
  border: 1px solid var(--border-default);
}
```

**Transition** for smooth switching:

```css
body {
  transition: background 0.2s, color 0.2s;
}
```

### Toggle Button HTML

```html
<button class="theme-btn" onclick="toggleTheme()" id="themeBtn">🌙</button>
```

```css
.theme-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px; border-radius: 50%;
  border: 1px solid var(--border-default);
  background: transparent; color: var(--text-secondary);
  cursor: pointer; font-size: 14px; transition: all 0.2s;
}
.theme-btn:hover {
  color: var(--text-body);
  border-color: var(--gh-corner-hover);
}
```

### Light Mode Colors (override via `[data-theme="light"]`)

| Semantic | Dark (GitHub Dark) | Light (GitHub Light) |
|:---|:---|:---|
| Page bg | `#0d1117` | `#ffffff` |
| Card bg | `#161b22` | `#f6f8fa` |
| Title | `#f0f6fc` | `#1f2328` |
| Body text | `#c9d1d9` | `#1f2328` |
| Secondary | `#8b949e` | `#656d76` |
| Code | `#ffa657` | `#0550ae` |
| Link | `#58a6ff` | `#0969da` |
| Border | `#30363d` | `#d0d7de` |

### JavaScript

```js
function setTheme(theme) {
  var isLight = theme === 'light';
  document.documentElement.dataset.theme = isLight ? 'light' : '';
  document.getElementById('themeBtn').textContent = isLight ? '☀️' : '🌙';
}

function toggleTheme() {
  var isLight = document.documentElement.dataset.theme === 'light';
  setTheme(isLight ? '' : 'light');
  try { localStorage.setItem('hs-theme', isLight ? 'dark' : 'light'); } catch(e) {}
}

(function initTheme() {
  // Priority: localStorage > default dark
  var saved;
  try { saved = localStorage.getItem('hs-theme'); } catch(e) {}
  if (saved) setTheme(saved);
  // default = dark (no data-theme attribute = :root values)
})();
```

## Pitfalls

- **Hardcoded colors in SVG elements** — hs-icon circle/text are hardcoded `#e0e0e0` and `#333` (looks fine on both backgrounds). Do not use CSS variables inside inline SVG fill unless using `currentColor`.
- **`transition` on body** — causes a slight flash on page load. Acceptable trade-off for smooth manual toggle.
- **`localStorage` guard** — always wrap in `try/catch` (private browsing may throw).
- **Theme sync across pages** — each page initializes independently. OK for static site; for SPA use a shared store.
