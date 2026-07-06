# CN/EN Language Toggle — Reusable Component

## Overview

A bilingual (Chinese/English) toggle for static HTML pages. Two separate HTML files (`index.html` / `index.zh.html`) linked by a fixed-position toggle in the top-right corner.

## Structure

```
project-root/
├── index.html          # English version
└── index.zh.html       # Chinese version
```

## Implementation

### CSS

```css
/* Toolbar container — fixed top-right */
.toolbar {
  position: fixed; top: 16px; right: 88px; z-index: 10;
  display: flex; gap: 6px; align-items: center;
  background: var(--lang-switch-bg, rgba(22, 27, 34, 0.9));
  backdrop-filter: blur(12px);
  border: 1px solid var(--border-default, #30363d);
  border-radius: 28px; padding: 4px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.35);
}

/* Pill-style toggle */
.lang-toggle {
  display: flex; border-radius: 24px; overflow: hidden;
  border: 1px solid var(--border-default, #30363d);
}
.lang-toggle a {
  display: inline-block; padding: 5px 12px; font-size: 0.8rem;
  font-weight: 600; text-decoration: none;
  color: var(--text-secondary, #8b949e); transition: all 0.2s;
}
.lang-toggle a.active {
  background: var(--lang-toggle-active-bg, #fff);
  color: var(--lang-toggle-active-color, #333);
}
.lang-toggle a:hover:not(.active) {
  color: var(--text-body, #c9d1d9);
  background: rgba(88, 166, 255, 0.08);
}
```

### HTML

**index.html** (English — EN active):
```html
<div class="toolbar">
  <div class="lang-toggle">
    <a href="./index.zh.html">🇨🇳</a>
    <a href="./index.html" class="active">🇺🇸</a>
  </div>
</div>
```

**index.zh.html** (Chinese — CN active):
```html
<div class="toolbar">
  <div class="lang-toggle">
    <a href="./index.zh.html" class="active">🇨🇳</a>
    <a href="./index.html">🇺🇸</a>
  </div>
</div>
```

## Conventions

- **Two separate files** — not a single file with show/hide. Clean URLs, SEO-friendly, no JS for basic switching.
- **Relative paths** — `./index.zh.html` not `/index.zh.html`. Works on both root and subdirectory deployments.
- **Active class on current language** — provides visual feedback and prevents circular navigation.
- **No JS required** — pure HTML/CSS. Theme toggle adds JS but lang toggle itself is static.

## Extending

To add more languages, expand the `.lang-toggle` container:
```html
<div class="lang-toggle">
  <a href="./index.ja.html">🇯🇵</a>
  <a href="./index.zh.html" class="active">🇨🇳</a>
  <a href="./index.html">🇺🇸</a>
</div>
```
