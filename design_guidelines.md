# WIRALIS Coming Soon Page - Design Guidelines

## Design Approach

**Selected Approach:** Custom Brand-Focused Design  
This is a coming soon/placeholder page for WIRALIS that must reflect the brand's modern, energetic identity while maintaining elegance and professionalism. The design draws from contemporary web trends with a focus on clean geometry and smooth animations, avoiding cyberpunk aesthetics in favor of refined sophistication.

**Key Design Principles:**
- Modern minimalism with bold brand presence
- Elegant geometric accents without excessive decoration
- Smooth, purposeful animations that enhance rather than distract
- Professional presentation with energetic undertones
- Single-page centered experience optimized for immediate impact

## Brand Color Requirements
Per user requirements, the design uses WIRALIS brand colors: vibrant purple and green gradients with diagonal stripe patterns as shown in reference image.

## Typography System

**Primary Headline ("В РАЗРАБОТКЕ"):**
- Font: Inter or Montserrat Bold/Black, 900 weight
- Size: text-6xl (desktop), text-4xl (mobile)
- Letter spacing: tracking-tight
- Text transform: uppercase for impact

**Logo (Header):**
- Font: Orbitron or Rajdhana Bold for tech-forward aesthetic
- Size: text-2xl to text-3xl
- Weight: 700-800
- Letter spacing: tracking-wide

**Body Text (Benefits Section):**
- Font: Inter Regular/Medium
- Size: text-lg (desktop), text-base (mobile)
- Weight: 400-500
- Line height: leading-relaxed

**Footer Text:**
- Font: Inter Regular
- Size: text-sm
- Weight: 400

## Layout System

**Spacing Primitives:**
Primary spacing units: 4, 6, 8, 12, 16, 20, 24
- Micro spacing: space-4, space-6 (between related elements)
- Section padding: py-12, py-16, py-20
- Container margins: mx-8, mx-12
- Element gaps: gap-6, gap-8, gap-12

**Page Structure:**
- Full viewport height (min-h-screen) centered layout
- Three-section vertical structure: Header (fixed/absolute top), Main Content (centered), Footer (absolute bottom)
- Maximum content width: max-w-4xl for main content, max-w-7xl for full sections
- Centered alignment for all text elements

**Grid System for Benefits:**
- Desktop: 3-column grid (grid-cols-3)
- Tablet: 2-column grid (md:grid-cols-2)
- Mobile: single column (grid-cols-1)
- Gap: gap-8 between cards

## Component Library

### Header Component
- Position: Absolute top, full width
- Elements: WIRALIS logo (text-based)
- Padding: py-6 to py-8
- Logo positioning: Centered or left-aligned with px-8
- Gradient text effect for logo with subtle glow

### Hero/Main Content Section
**Primary Headline:**
- "В РАЗРАБОТКЕ" as dominant centerpiece
- Gradient text treatment with subtle glow effect
- Margin bottom: mb-8 to mb-12

**Subheadline:**
- "Мы ещё строим сайт" positioned directly below main headline
- Size: text-xl to text-2xl
- Margin bottom: mb-12 to mb-16
- Opacity: 90% for visual hierarchy

**Geometric Diamond Element:**
- SVG-based geometric diamond/crystal shape
- Size: 200-300px on desktop, 150-200px on mobile
- Positioned behind or integrated with text
- Subtle rotation animation (0-360deg, 20-30s duration)
- Semi-transparent (opacity 10-20%)
- CSS blur backdrop effect for depth

### Benefits Cards Section
**Card Structure:**
- Background: Semi-transparent overlay with backdrop-blur
- Padding: p-6 to p-8
- Border radius: rounded-xl to rounded-2xl
- Border: 1px subtle border with partial transparency

**Card Content:**
- Icon area (if using icon library): mb-4, size 32-40px
- Title: text-lg to text-xl, font-semibold, mb-3
- Description: text-base, leading-relaxed

**Three Benefits to Display:**
1. "Красивые новостные посты"
2. "Вход через WIRALIS-бот"
3. "И многое другое"

### Footer Component
- Position: Absolute bottom, full width
- Padding: py-8
- Content: "WIRALIS - Все права защищены"
- Telegram Links Section:
  - Two link buttons: "Telegram-канал" and "Telegram-бот"
  - Display: Inline or flex with gap-4
  - Icon: Heroicons or Font Awesome Telegram icon
  - Styling: Subtle border, rounded-lg, px-4 py-2
  - Hover: Scale transform (scale-105)

### Background Treatment
- Full-page gradient background
- Diagonal stripe overlay pattern (SVG or CSS)
- Stripe angle: -45deg or 45deg
- Stripe spacing: Consistent intervals
- Overall background: Fixed attachment for depth

## Animation Strategy

**Page Load Sequence:**
1. Logo fades in first (0.3s delay)
2. Main headline fades in with slight upward movement (0.5s delay)
3. Subheadline appears (0.7s delay)
4. Benefits cards stagger in (0.8s, 1s, 1.2s delays)
5. Footer fades in last (1.4s delay)

**Continuous Animations:**
- Diamond rotation: Slow 20-30s rotation (transform: rotate)
- Background gradient: Subtle 10-15s color shift animation
- Diagonal stripes: Optional slow diagonal movement

**Interaction Animations:**
- Benefit cards: Hover lift effect (translateY(-4px) + shadow increase)
- Footer links: Hover scale (scale-105) + opacity change
- Logo: Subtle pulse glow on hover

**Animation Implementation:**
- Use CSS transitions for hover states
- CSS keyframe animations for continuous effects
- Intersection Observer for scroll-triggered animations (if expanded)
- Transform and opacity for performance
- Duration range: 0.3s (interactions) to 30s (ambient)
- Easing: ease-in-out, cubic-bezier for custom curves

## Responsive Behavior

**Breakpoints:**
- Mobile: < 640px (base)
- Tablet: 640px - 1024px (md:)
- Desktop: > 1024px (lg:)

**Mobile Adaptations:**
- Reduce headline sizes significantly
- Stack benefit cards vertically
- Reduce diamond size
- Increase vertical spacing between sections
- Ensure touch-friendly link sizes (min 44px height)

**Tablet:**
- Two-column benefit grid
- Moderate headline sizes
- Maintain spatial hierarchy

## Accessibility Considerations

- Semantic HTML structure (header, main, footer)
- Proper heading hierarchy (h1 for "В РАЗРАБОТКЕ")
- Alt text for any decorative elements marked as such
- Focus visible states for all interactive elements
- Color contrast meeting WCAG AA standards despite gradient backgrounds
- Reduced motion support: Disable animations for prefers-reduced-motion
- Keyboard navigation for footer links

## Technical Implementation Notes

**Frameworks & Libraries:**
- Tailwind CSS for utility styling
- Framer Motion or CSS animations for transitions
- Heroicons or Font Awesome for Telegram icons
- Google Fonts for typography (Inter, Montserrat/Orbitron)

**Performance:**
- Optimize gradient rendering
- Use CSS transforms (GPU-accelerated)
- Lazy load any background images if used
- Minimize JavaScript for simple animations

**Browser Support:**
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Graceful degradation for older browsers (static version without animations)
- CSS fallbacks for backdrop-filter

This creates a polished, modern coming soon page that respects WIRALIS brand identity while maintaining professional elegance without cyberpunk excess.