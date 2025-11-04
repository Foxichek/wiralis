# WIRALIS Coming Soon Page

## Overview

This is a coming soon/placeholder page for WIRALIS, a cryptocurrency-focused platform currently under development. The application features a single-page design showcasing the brand's modern, energetic identity through vibrant purple and green gradients with diagonal stripe patterns. The page highlights upcoming features including beautiful news posts, WIRALIS-bot login integration, and other platform capabilities.

The application is built as a full-stack TypeScript project with a React frontend and Express backend. It integrates with a Telegram bot through API endpoints for user authentication and registration.

## Telegram Bot Integration

The website integrates with a Telegram bot (@wiralis_bot) through the following workflow:

1. **User requests access**: User sends `/web` command in Telegram bot
2. **Code generation**: Bot calls `/api/bot/generate-code` endpoint with user data
3. **User authentication**: User enters 6-digit code on website via `/register` page
4. **Verification**: Website calls `/api/verify-code` to authenticate user
5. **Profile access**: User gains access to their profile and platform features

### API Endpoints

- `POST /api/bot/generate-code` - Bot endpoint to generate authentication codes (requires API key)
- `POST /api/verify-code` - Website endpoint to verify user codes
- `GET /api/profile/:userId` - Retrieve user profile data

### Environment Variables

- `TELEGRAM_BOT_API_SECRET` - API key for bot authentication (default: US42982557)
- `DATABASE_URL` - PostgreSQL database connection string

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Framework**: React 18 with TypeScript, built using Vite as the build tool and development server.

**UI Component System**: Utilizes shadcn/ui component library with Radix UI primitives for accessible, unstyled components. The design system is based on the "new-york" style variant with extensive customization for the WIRALIS brand.

**Styling Approach**: TailwindCSS with extensive custom configuration including:
- Custom color system using HSL values with CSS variables for theme flexibility
- Custom border radius values (9px, 6px, 3px)
- Elevation system using overlay effects (--elevate-1, --elevate-2)
- Brand-specific color gradients for purple and green themes

**Routing**: Uses Wouter for lightweight client-side routing, though currently only renders the coming soon page.

**State Management**: React Query (@tanstack/react-query) configured for data fetching with conservative defaults (no auto-refetch, infinite stale time), though not actively used in the current implementation.

**Component Structure**: 
- Custom branded components (ComingSoon, BenefitCard, DiamondBackground, FloatingEmojis)
- Comprehensive shadcn/ui component library for future expansion
- Example components for documentation purposes

### Backend Architecture

**Server Framework**: Express.js running on Node.js with TypeScript.

**Development Setup**: Custom Vite middleware integration for hot module replacement during development, with SSR-capable rendering pipeline.

**API Structure**: RESTful API design with `/api` prefix for all endpoints. Currently minimal implementation with placeholder route structure.

**Storage Layer**: Abstracted through an `IStorage` interface with in-memory implementation (`MemStorage`). Designed for easy swapping to database-backed storage (PostgreSQL with Drizzle ORM is configured but not yet implemented).

**Request Logging**: Custom middleware tracking request duration and response payloads for API endpoints.

### Data Storage Solutions

**ORM**: Drizzle ORM configured for PostgreSQL with schema definition and migration support.

**Schema Design**: Simple user authentication schema with:
- UUID primary keys with auto-generation
- Username/password fields for basic authentication
- Unique constraints on usernames

**Database Configuration**: Neon serverless PostgreSQL driver configured via DATABASE_URL environment variable. Migration files outputted to `/migrations` directory.

**Current State**: Database integration is configured but not actively used - application uses in-memory storage for the placeholder page.

### Design System

**Typography**: Multiple font families loaded from Google Fonts:
- DM Sans for body text
- Geist Mono for monospace elements
- Fira Code for code snippets
- Architects Daughter for decorative elements

**Brand Guidelines**: Documented in `design_guidelines.md` specifying:
- Purple and green gradient brand colors
- Diagonal stripe patterns
- Modern minimalist aesthetic with geometric accents
- Responsive typography scale (text-6xl to text-sm)
- Standardized spacing system (4, 6, 8, 12, 16, 20, 24px units)

**Animation**: CSS-based animations for:
- Fade-in effects with staggered delays
- Rotating diamond background
- Floating emoji elements
- Hover elevation effects
- Glass-morphism scrollbar with smooth transitions

**Custom Scrollbar**: Glass-style scrollbar featuring:
- Purple gradient with transparency
- Smooth hover and active states
- Backdrop blur effect
- Border highlights for depth
- Cross-browser support (WebKit and Firefox)

## External Dependencies

### Core Frameworks
- **React 18**: Frontend UI framework
- **Express**: Backend web server
- **Vite**: Build tool and development server
- **TypeScript**: Type-safe development across stack

### UI Component Libraries
- **Radix UI**: Comprehensive set of unstyled, accessible component primitives (@radix-ui/react-*)
- **shadcn/ui**: Pre-styled component library built on Radix UI
- **TailwindCSS**: Utility-first CSS framework with PostCSS processing
- **Lucide React**: Icon library for UI elements
- **React Icons**: Additional icon sets (specifically Simple Icons for Telegram)

### State Management & Data Fetching
- **TanStack React Query**: Server state management and data fetching
- **Wouter**: Lightweight client-side routing
- **React Hook Form**: Form state management with Zod validation (@hookform/resolvers)

### Database & ORM
- **Drizzle ORM**: TypeScript ORM with schema definition and migrations
- **@neondatabase/serverless**: Neon PostgreSQL serverless driver
- **drizzle-zod**: Integration between Drizzle schemas and Zod validation
- **Zod**: TypeScript-first schema validation

### Additional UI Libraries
- **embla-carousel-react**: Carousel/slider component
- **class-variance-authority**: Utility for creating variant-based component APIs
- **clsx & tailwind-merge**: Utility for conditional className composition
- **cmdk**: Command palette component
- **date-fns**: Date manipulation library
- **vaul**: Drawer component library

### Development Tools
- **Replit Plugins**: Development environment enhancements (@replit/vite-plugin-*)
- **esbuild**: JavaScript bundler for production builds
- **tsx**: TypeScript execution for development server

### Session Management
- **connect-pg-simple**: PostgreSQL session store (configured but not actively used)

## Recent Changes (November 4, 2025)

### Bot Integration
- Added API endpoints for Telegram bot integration
- Implemented authentication code generation and verification
- Added user data storage for bot users
- Created database schema for registration codes and WIRALIS users

### UI/UX Improvements
- Added interactive "How it works?" modal explaining bot integration
- Implemented tooltip on "В РАЗРАБОТКЕ" showing release timeline (December 2025 / Early 2026)
- Added custom glass-morphism scrollbar matching brand aesthetic
- Updated footer with copyright © 2025 WIRALIS Team
- Enhanced BenefitCard component with secondary action support

### Technical Updates
- Configured TELEGRAM_BOT_API_SECRET environment variable
- Updated replit.md with integration documentation
- Improved component reusability and type safety