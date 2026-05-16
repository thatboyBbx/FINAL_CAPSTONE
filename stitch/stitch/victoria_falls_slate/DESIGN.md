# Design System Strategy: InsureIntel Zimbabwe

## 1. Overview & Creative North Star: "The Digital Ledger"
The design system for InsureIntel Zimbabwe is built upon the Creative North Star of **"The Digital Ledger."** In the Zimbabwean insurance context, trust is not just a value; it is a currency. This system moves away from the "disruptive" tech aesthetic toward an editorial, authoritative, and high-fidelity experience that mirrors the precision of a high-end financial broadsheet.

We break the "SaaS template" look through **intentional layering and tonal depth**. By leveraging sophisticated font pairings—the technical precision of *Inter* and the architectural elegance of *Manrope*—we create a UI that feels curated, not generated. We prioritize "Breathing Room" over "Information Density," ensuring that even the most complex data dashboards feel calm and controlled.

## 2. Color & Surface Architecture
We utilize a sophisticated Material-based palette to establish brand authority. Blue represents the stability of the Zimbabwean financial sector, while the tertiary "Terracotta" accents provide a subtle nod to the regional landscape without falling into cliché.

### The "No-Line" Rule
**Borders are prohibited for sectioning.** To define high-level content areas, use background color shifts only. 
*   **Action:** Place a `surface_container_low` dashboard section directly onto a `surface` background. The change in hex value is the boundary. 1px solid lines are strictly for decorative "accents" or required accessibility indicators.

### Surface Hierarchy & Nesting
Treat the interface as a physical stack of premium materials.
*   **Level 0 (Base):** `surface` (#f8f9fb) – The canvas.
*   **Level 1 (Sections):** `surface_container_low` (#f3f4f6) – For secondary content areas.
*   **Level 2 (Cards/Modules):** `surface_container_lowest` (#ffffff) – Pure white cards sitting on top of the gray sections to create a "lifted" effect.
*   **Level 3 (Interactive):** `surface_bright` – For active states and high-priority modals.

### The "Glass & Gradient" Rule
To elevate the "Dark Navy Sidebar," avoid flat colors. Apply a subtle linear gradient from `on_secondary_fixed` to `on_secondary_fixed_variant`. For floating utility panels (like quick-calculators), use **Glassmorphism**:
*   **Backdrop Blur:** 12px to 20px.
*   **Fill:** `surface_container_lowest` at 70% opacity.

## 3. Typography: Editorial Authority
The type system creates a dialogue between "The Record" (Body) and "The Statement" (Headlines).

*   **Display & Headlines (Manrope):** Used for data summaries and page titles. The wide apertures of Manrope convey transparency and modernism.
*   **Body & Labels (Inter):** Used for the "ledger" details. Inter’s high x-height ensures readability in complex insurance tables and policy terms.
*   **Hierarchy Note:** Always pair a `headline-sm` in `on_surface` with a `label-md` in `outline` to create a clear "Title/Caption" relationship that mimics financial reporting.

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are often "dirty." We achieve depth through light and tone.

*   **The Layering Principle:** Instead of a shadow, place a `surface_container_lowest` card on a `surface_container` background. The 2-3% difference in lightness creates a sophisticated, "quiet" elevation.
*   **Ambient Shadows:** For high-priority floating elements (e.g., a "New Claim" modal), use an ultra-diffused shadow: `0px 24px 48px rgba(25, 28, 30, 0.06)`. The tint is derived from `on_surface`, making it feel like a natural light obstruction.
*   **The "Ghost Border" Fallback:** If a container requires definition against a white background, use the `outline_variant` token at **15% opacity**. High-contrast borders are forbidden.

## 5. Components & Interaction Patterns

### Cards & Data Modules
*   **Structure:** No dividers. Separate the "Header" from the "Body" using a 1.75rem (`8`) vertical gap.
*   **Styling:** Use `xl` (0.75rem) corner radius for a modern, approachable feel.
*   **Zimbabwean Context:** Include a "Trust Badge" area in `surface_container_high` for regulatory IDs (IPEC numbers) to reinforce credibility.

### Tables & Badges
*   **The Stripeless Table:** Avoid zebra stripping. Use `surface_container_low` on hover states only. 
*   **Badges:** Use "Soft Status" styling. A `success` badge should be a `success_container` background with `on_success_container` text. Avoid high-vibrancy "neon" reds and greens.

### Buttons
*   **Primary:** A gradient from `primary` (#004ac6) to `primary_container` (#2563eb). Radius: `md`.
*   **Secondary/Tertiary:** No background. Use `on_surface` text with a `primary` icon to draw the eye without competing with the main CTA.

### Detailed Dashboards (The "Pulse" View)
*   **Component:** **The Claim Velocity Gauge.** Instead of a standard bar chart, use a series of nested `surface_container` tiers to create a "sunken" track for progress bars.

## 6. Do’s and Don'ts

### Do:
*   **Use Asymmetry:** In the dashboard, balance a large "Total Premium" display (left) with a smaller, high-density "Recent Claims" list (right).
*   **Respect the Spacing Scale:** Stick strictly to the `4` (0.9rem) and `8` (1.75rem) increments for internal padding to maintain the "editorial" rhythm.
*   **Tint Your Grays:** Ensure all neutral surfaces have a slight blue/cool undertone to match the `primary` blue.

### Don't:
*   **No "Pure" Black:** Never use #000000. Use `on_surface` (#191c1e) for all text to maintain a premium, ink-on-paper look.
*   **No Crowding:** If a table has more than 8 columns, utilize a horizontal scroll within a `surface_container` rather than shrinking text size below `body-sm`.
*   **No Default Icons:** Avoid generic, thin-line icons. Use solid/duotone icons that feel weighted and significant.

## 7. Spacing & Rhythm
Consistency is the bedrock of trust.
*   **Container Padding:** Always `8` (1.75rem).
*   **Section Gaps:** Always `16` (3.5rem) to allow the "eye to reset" between different data sets.
*   **Text Leading:** For `body-lg`, use a generous 1.6 line-height to ensure policy documents are readable and non-threatening.