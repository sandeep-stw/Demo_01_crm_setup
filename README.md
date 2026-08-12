# Demo CRM Setup

A minimal customer relationship management (CRM) demo built with Next.js, Prisma, and SQLite. It is designed to validate Cloud Agent development environments end to end.

## Stack

- **Next.js 15** (App Router, TypeScript)
- **Prisma** with SQLite
- **Tailwind CSS**

## Development

```bash
npm ci
npx prisma db push
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to use the CRM UI.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the development server on port 3000 |
| `npm run build` | Production build |
| `npm run lint` | Run ESLint |
| `npm run db:push` | Apply Prisma schema to the local SQLite database |

## Cloud Agent

Environment configuration lives in `.cursor/environment.json`. The install script prepares dependencies and the database; the dev server runs as a named terminal process.
