# UI, security, and accessibility audit — 2026-08-24

## Scope

This audit deliberately changed no game mechanics and added no environment. It
covered the local Python lobby, the zero-backend public build, the hosted Worker
runtime, and real desktop/mobile browser paths.

## Reproduced findings

1. The rules dialog trapped keyboard focus, but the header and game behind it
   remained exposed to assistive technology and the page could still scroll.
2. The banker-offer dialog had no equivalent initial-focus or focus-loop
   behavior. Keyboard users could move behind the modal decision surface.
3. At 390 px, the lobby did not overflow horizontally, but cards were roughly
   353–387 px tall and the two language controls had unequal 42/35 px widths.
   Browsing fifteen games therefore required avoidable scrolling and provided
   inconsistent touch targets.
4. Local and Worker responses declared content types correctly but did not send
   defense-in-depth browser headers. The static GitHub Pages build also lacked a
   document-level content security policy.

## Fixes

- Both dialogs now lock background scrolling, mark the header and main content
  `inert`, and keep Tab/Shift+Tab inside the active dialog.
- Rules still close with Escape and restore focus to their launcher. The banker
  offer focuses its counter-offer field (or Deal when negotiation is unavailable)
  and cannot be dismissed without making a game decision.
- Mobile cards now use a compact single-column treatment. In the verified 390 px
  viewport, the first four cards fell to 242–267 px and both language controls
  became 44 px wide, with no horizontal overflow.
- Local and Worker responses now include CSP, `nosniff`, no-referrer,
  permissions restrictions, and same-origin opener isolation. The static HTML
  includes a CSP meta policy for the zero-backend GitHub Pages path.

## Validation

- All 199 Python tests and all 12 Worker/static-build tests pass.
- The full browser-engine decision-loop suite still completes all 15 playable
  games.
- A real local browser verified game entry at scroll position zero, rules focus
  restoration, offer-dialog forward and reverse focus wrapping, background
  isolation, compact mobile dimensions, and an empty warning/error console.
- The CSP intentionally retains `style-src 'unsafe-inline'` because several
  existing visual probability bars and board nodes use computed inline style
  values. Removing that allowance requires a separate bounded refactor; this
  update does not claim a strict nonce/hash CSP.

These changes improve the delivery boundary and interaction safety. They do not
alter or strengthen any strategic-policy optimality claim.
