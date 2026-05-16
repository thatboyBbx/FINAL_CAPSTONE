```markdown
# Design System Specification: The Sovereign Intelligence

## 1. Overview & Creative North Star
### The Creative North Star: "The Private Ledger"
This design system is not a dashboard; it is a bespoke digital vault. It rejects the frantic, "widget-heavy" aesthetic of traditional fintech in favor of a **High-End Editorial** experience. The visual language is inspired by the tactile quality of a private banker’s leather-bound ledger and the atmospheric depth of a high-end luxury watch boutique.

**Breaking the Template:**
We move beyond the "grid-of-boxes" by employing intentional **asymmetry** and **tonal layering**. Elements are not merely placed on a screen; they are curated. We utilize expansive white space (or "dark space") to allow data to breathe, treating financial metrics as if they were headlines in a premium financial journal. 

---

## 2. Colors & Surface Architecture

### The "No-Line" Rule
Traditional 1px solid borders are strictly prohibited for sectioning. Boundaries must be defined through **Background Color Shifts** or **Subtle Tonal Transitions**. A section is defined by its depth (e.g., a `surface-container-low` section sitting on a `surface` background), not by a stroke.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers—stacked sheets of frosted glass.
*   **Base Layer (`surface` / #131313):** The foundation.
*   **Secondary Layer (`surface-container-low` / #1c1b1b):** Primary content areas.
*   **Tertiary Layer (`surface-container-high` / #2a2a2a):** Inset cards or active modules.
*   **Floating Layer (Glassmorphism):** Used for navigation or overlays. Use `rgba(18, 18, 18, 0.85)` with a **16px backdrop-blur**.

### Signature Textures
Avoid flat, "dead" colors. For primary CTAs and key headers, apply a subtle linear gradient from `primary` (#f2ca50) to `primary-container` (#d4af37) at a 135-degree angle. This mimics the way light hits physical gold leaf.

---

## 3. Typography
The typography system uses a pairing of **Manrope** for authoritative headers and **Inter** for precision data.

*   **Display & Headline (Manrope):** Set with tight letter-spacing (-0.02em) and generous line-height to convey an editorial, high-fashion intelligence feel.
*   **Body (Manrope):** Warm tones. Use `on-surface-variant` (#d0c5af) for secondary body text to reduce eye strain and maintain the "warm parchment" feel even in dark mode.
*   **Labels (Inter):** All-caps for `label-sm` (#0.6875rem) to provide a "technical" contrast to the organic feel of Manrope.

| Level | Token | Font | Size | Weight |
| :--- | :--- | :--- | :--- | :--- |
| **Display** | `display-lg` | Manrope | 3.5rem | 700 |
| **Headline** | `headline-md` | Manrope | 1.75rem | 600 |
| **Title** | `title-lg` | Manrope | 1.375rem | 500 |
| **Body** | `body-lg` | Manrope | 1rem | 400 |
| **Label** | `label-md` | Inter | 0.75rem | 500 |

---

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved through **Tonal Layering** rather than structural lines.
*   **Level 0:** `surface-container-lowest` (#0e0e0e) – for background "wells."
*   **Level 1:** `surface` (#131313) – the main canvas.
*   **Level 2:** `surface-container-low` (#1c1b1b) – for standard cards.
*   **Level 3:** `surface-container-highest` (#353534) – for hover states or active items.

### Ambient Shadows
Floating elements (modals, dropdowns) must use **Ambient Shadows**.
*   **Shadow Color:** `rgba(0, 0, 0, 0.6)`
*   **Shadow Specs:** 0px 24px 48px -12px.
*   **The Ghost Border:** If containment is needed for accessibility, use `outline-variant` (#4d4635) at **15% opacity**. Never use 100% opaque borders.

---

## 5. Components

### Interactive Elements (The Glass Rule)
All interactive elements must feel "lit from within." Use semi-transparent surfaces rather than flat fills.

*   **Buttons:** 
    *   **Primary:** `rgba(212, 175, 55, 0.15)` background, `primary` (#f2ca50) border at 1px, and 16px blur. No flat fills.
    *   **States:** Hover increases border opacity to 100%; Pressed shifts background to `primary-container` (#d4af37) at 20% opacity.
*   **Cards & Lists:** 
    *   **Strictly No Dividers.** Use the **Spacing Scale** (specifically `spacing-4` / 1.4rem) to create separation through "white space." For grouped list items, use a subtle background shift to `surface-container-low`.
*   **Input Fields:** 
    *   Underlined only or "Well" style (`surface-container-lowest`). No boxed borders. Focus state glows with a subtle `primary` shadow (4% opacity).
*   **Bespoke Component: The Intelligence Ribbon:**
    *   A thin, vertical 2px gold gradient strip (`primary`) placed to the left of "Critical" or "High" priority financial insights to draw the eye without cluttering the UI.

---

## 6. Do’s and Don’ts

### Do:
*   **Use Asymmetric Layouts:** Position a large `display-md` metric off-center to create a modern, editorial feel.
*   **Embrace the "Warmth":** Use the `on-surface-variant` (#d0c5af) for most text to keep the interface feeling premium and "aged," not clinical.
*   **Nesting:** Place a `surface-container-highest` card inside a `surface-container-low` section to create natural focus.

### Don’t:
*   **No Purple/Blue Hues:** Under no circumstances use violet, indigo, or lavender. If a "cool" tone is needed, use the `Info` (#4a8fc2) sparingly.
*   **No Heavy Borders:** Never use a solid 100% opacity border to separate content blocks.
*   **No Default Shadows:** Avoid "drop shadows" that look like they belong on a standard OS. Use the ambient, tinted shadows defined in Section 4.
*   **No Flat Buttons:** Even "Primary" buttons must maintain a level of transparency to adhere to the glassmorphism ethos.```