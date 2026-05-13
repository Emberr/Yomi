# Frontend Dependencies

## Production

- Next.js
  - Purpose: App Router frontend framework for Yomi.
  - License: MIT.
  - Why needed: Matches the project architecture and provides routing, build, and server runtime.
  - Security/operational implications: Runs behind nginx in Compose; keep updated for React/Next security releases.

- React
  - Purpose: UI rendering library used by Next.js.
  - License: MIT.
  - Why needed: Required foundation for the Next.js app.
  - Security/operational implications: No direct network or secret handling.

- React DOM
  - Purpose: Browser DOM renderer for React.
  - License: MIT.
  - Why needed: Required runtime package for React in the browser.
  - Security/operational implications: No direct network or secret handling.

## Development

- TypeScript
  - Purpose: Static type checking.
  - License: Apache-2.0.

- ESLint, `@eslint/js`, and `typescript-eslint`
  - Purpose: JavaScript/TypeScript linting.
  - License: MIT.

- `@types/node`, `@types/react`, `@types/react-dom`
  - Purpose: Type declarations for Node and React APIs.
  - License: MIT.

