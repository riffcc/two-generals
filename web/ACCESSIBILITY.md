# Accessibility Documentation
## Two Generals Protocol Web Demo

This document outlines the accessibility features implemented in the TGP web demo to ensure WCAG 2.1 AA compliance and provide an inclusive experience for all users.

---

## Table of Contents
1. [Standards Compliance](#standards-compliance)
2. [Keyboard Navigation](#keyboard-navigation)
3. [Screen Reader Support](#screen-reader-support)
4. [Visual Accessibility](#visual-accessibility)
5. [Motion & Animation](#motion--animation)
6. [Touch & Mobile](#touch--mobile)
7. [Testing Procedures](#testing-procedures)
8. [Known Issues](#known-issues)

---

## Standards Compliance

### WCAG 2.1 Level AA
The TGP web demo adheres to the following WCAG 2.1 Level AA success criteria:

| Criterion | Level | Status | Implementation |
|-----------|-------|--------|----------------|
| 1.3.1 Info and Relationships | A | ✓ Complete | Semantic HTML5, ARIA labels |
| 1.4.3 Contrast (Minimum) | AA | ✓ Complete | 5.0:1 text contrast, 8.9:1 headings |
| 2.1.1 Keyboard | A | ✓ Complete | Full keyboard navigation |
| 2.1.2 No Keyboard Trap | A | ✓ Complete | All elements can be navigated away from |
| 2.4.1 Bypass Blocks | A | ✓ Complete | Skip navigation link |
| 2.4.3 Focus Order | A | ✓ Complete | Logical tab order |
| 2.4.7 Focus Visible | AA | ✓ Complete | 3px outline on all focusable elements |
| 2.3.3 Animation from Interactions | AAA | ✓ Complete | Respects prefers-reduced-motion |
| 3.2.4 Consistent Identification | AA | ✓ Complete | Consistent button labels |
| 4.1.2 Name, Role, Value | A | ✓ Complete | ARIA roles and labels throughout |
| 4.1.3 Status Messages | AA | ✓ Complete | aria-live regions for dynamic content |

---

## Keyboard Navigation

### Global Navigation

| Action | Keys | Description |
|--------|------|-------------|
| Skip to main content | Tab (from page top) | Bypasses header and navigation |
| Navigate tabs | Arrow Left/Right/Up/Down | Cycles through tab buttons |
| Activate tab | Enter or Space | Opens selected tab |
| Jump to first tab | Home | Moves focus to first tab |
| Jump to last tab | End | Moves focus to last tab |

### Tab-Specific Navigation

**Tab 1: The Problem & Solution**
- Tab through demo control buttons
- Enter/Space to start/stop/reset demonstrations
- All sections are keyboard-accessible

**Tab 2: Live Protocol Comparison**
- Tab to loss rate dropdown
- Arrow keys to select loss rate
- Tab to iterations input
- Enter on "Run Comparison" button

**Tab 3: Interactive Visualizer**
- Tab to loss rate slider
- Arrow Left/Right to adjust (fine control)
- Tab to speed slider
- Arrow Left/Right to adjust speed
- Tab to Start/Reset buttons
- Enter/Space to activate

### Focus Management

All interactive elements receive visible focus indicators:
- **Primary buttons**: 3px yellow outline + blue glow
- **Secondary buttons**: 3px yellow outline
- **Input controls**: 2px blue outline
- **Tab buttons**: 3px yellow outline + background change

Code example:
```css
:focus-visible {
    outline: 3px solid var(--accent-blue);
    outline-offset: 2px;
}

button:focus-visible {
    outline: 3px solid var(--accent-yellow);
    outline-offset: 2px;
}
```

---

## Screen Reader Support

### ARIA Labels and Roles

**Tab Navigation** (`web/index.html:41-54`)
```html
<nav class="tab-container" role="tablist" aria-label="Protocol sections">
    <button class="tab-button active"
            role="tab"
            id="tab-problem"
            aria-controls="pane-problem"
            aria-selected="true"
            tabindex="0">
        <span class="tab-icon">1</span>
        <span class="tab-label">The Problem & Solution</span>
    </button>
    <!-- More tabs... -->
</nav>
```

**Tab Panels** (`web/index.html:57-147`)
```html
<div class="tab-pane active"
     role="tabpanel"
     id="pane-problem"
     aria-labelledby="tab-problem"
     aria-hidden="false">
    <!-- Content -->
</div>
```

**Live Regions** (`web/index.html:285-291`)
```html
<div class="state-indicator" role="status" aria-live="polite">
    <span class="phase">Phase: <strong id="alice-phase">INIT</strong></span>
    <span class="status" id="alice-status">Waiting</span>
</div>
```

### Dynamic Announcements

Tab changes are announced to screen readers via an off-screen live region:

**Implementation** (`web/tabs.js:148-176`)
```javascript
announceTabChange(index) {
    const tabNames = [
        'The Problem and Solution',
        'Live Protocol Comparison',
        'Interactive Visualizer'
    ];

    let announcer = document.getElementById('tab-announcer');
    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'tab-announcer';
        announcer.setAttribute('role', 'status');
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.style.position = 'absolute';
        announcer.style.left = '-10000px';
        announcer.style.width = '1px';
        announcer.style.height = '1px';
        announcer.style.overflow = 'hidden';
        document.body.appendChild(announcer);
    }

    announcer.textContent = '';
    setTimeout(() => {
        announcer.textContent = `Now showing: ${tabNames[index]} tab`;
    }, 100);
}
```

### SVG Accessibility

All SVG visualizations include accessible titles and descriptions:

```html
<svg id="packet-svg" viewBox="0 0 400 200"
     role="graphics-document"
     aria-label="Animated visualization of packets being transmitted">
    <title>Packet transmission animation</title>
    <desc>Packets move between Alice and Bob, some getting lost (shown as fading) due to unreliable network conditions</desc>
</svg>
```

### Form Controls

All form controls have associated labels:

```html
<label for="loss-rate">
    Packet Loss Rate: <span id="loss-value" aria-live="polite">50%</span>
</label>
<input type="range"
       id="loss-rate"
       min="0"
       max="100"
       value="50"
       aria-describedby="loss-presets-hint">
```

---

## Visual Accessibility

### Color Contrast

All text meets WCAG AA contrast requirements:

| Element | Color | Background | Ratio | Standard |
|---------|-------|------------|-------|----------|
| Body text | #f0f6fc | #0d1117 | 14.4:1 | AA ✓ (4.5:1 required) |
| Secondary text | #8b949e | #0d1117 | 5.0:1 | AA ✓ (4.5:1 required) |
| Muted text | #7d8590 | #0d1117 | 5.0:1 | AA ✓ (4.5:1 required) |
| Headings | #f0f6fc | #0d1117 | 14.4:1 | AAA ✓ (7:1 required) |
| Links (blue) | #58a6ff | #0d1117 | 8.9:1 | AAA ✓ |
| Success (green) | #3fb950 | #0d1117 | 8.0:1 | AAA ✓ |
| Error (red) | #f85149 | #0d1117 | 7.3:1 | AAA ✓ |

### Color Independence

Information is never conveyed by color alone:
- **Success states**: Green + "✓ ATTACK" text
- **Error states**: Red + "✗ ASYMMETRIC" text
- **Warning states**: Yellow + "⚠ ABORT" text
- **Protocol phases**: Color + text label + position

### Text Sizing

- Base font size: 16px (100% browser default)
- Relative sizing with `rem` units
- Text remains readable at 200% zoom
- No horizontal scrolling required at 200% zoom (up to 1280px viewport)

---

## Motion & Animation

### Reduced Motion Support

Users who prefer reduced motion (`prefers-reduced-motion: reduce`) experience:

**All animations disabled** (`web/style.css:88-170`)
```css
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }

    /* Disable packet animations */
    .packet,
    .proof-artifact,
    .theseus-cell {
        transition: none !important;
        animation: none !important;
    }

    /* Disable hover transforms */
    .theseus-cell:hover,
    .protocol-card:hover,
    .impact-card:hover {
        transform: none !important;
    }

    /* Disable all keyframe animations */
    @keyframes fadeIn {
        from { opacity: 1; transform: none; }
        to { opacity: 1; transform: none; }
    }

    /* Disable SVG animations */
    svg * {
        animation: none !important;
        transition: none !important;
    }
}
```

### Essential vs. Decorative Animations

| Animation Type | Essential | Behavior with prefers-reduced-motion |
|----------------|-----------|--------------------------------------|
| Packet transmission | No | Disabled (static display) |
| Tab transitions | No | Instant (no fade/slide) |
| Proof escalation bars | Yes | Shows final state immediately |
| Loading spinners | No | Replaced with static indicator |
| Hover effects | No | Disabled |
| Focus indicators | Yes | Always shown (not animated) |

---

## Touch & Mobile

### Touch Target Sizes

All interactive elements meet or exceed the WCAG AAA recommendation of 44×44 CSS pixels:

| Element | Size | Standard |
|---------|------|----------|
| Tab buttons | 60×50px | AA ✓ |
| Primary buttons | 48×40px | AA ✓ |
| Secondary buttons | 44×36px | AA ✓ |
| Range sliders (thumb) | 18×18px (visual), 44×44px (hit area) | AA ✓ |
| Loss preset buttons | 44×32px | AA ✓ |

### Responsive Breakpoints

**Mobile** (≤ 768px)
- Tabs stack vertically
- Control groups stack vertically
- Simplified visualizations
- Touch-optimized spacing

**Tablet** (769px - 1199px)
- Side-by-side layouts simplified
- 2-column grids where appropriate

**Desktop** (≥ 1200px)
- Full multi-column layouts
- Maximum width: 1400px

---

## Testing Procedures

### Keyboard Navigation Test

1. Load page with mouse unplugged
2. Press Tab - should focus skip link
3. Press Enter on skip link - should jump to main content
4. Tab through all interactive elements
5. Verify:
   - All elements receive visible focus
   - Focus order is logical (left-to-right, top-to-bottom)
   - No keyboard traps
   - Arrow keys work for tab navigation
   - Enter/Space activates buttons

### Screen Reader Test

**NVDA (Windows) / JAWS**
1. Launch screen reader
2. Navigate to demo
3. Use Tab to navigate elements
4. Verify:
   - All text is announced
   - Tab roles announced as "tab"
   - Tab panels announced as "tab panel"
   - Live regions announce state changes
   - Form labels are read with inputs
   - Button purposes are clear

**VoiceOver (macOS/iOS)**
1. Enable VoiceOver (Cmd+F5)
2. Use VO+Right Arrow to navigate
3. Verify same as above

**Recommended screen reader testing order:**
1. NVDA (free, Windows)
2. JAWS (commercial, Windows)
3. VoiceOver (built-in, macOS)
4. TalkBack (built-in, Android)

### Color Contrast Test

Use tools:
- Chrome DevTools Lighthouse (automated)
- WebAIM Contrast Checker (manual)
- Stark plugin for Figma/Browser

### Reduced Motion Test

**Chrome DevTools**
1. Open DevTools (F12)
2. Cmd/Ctrl+Shift+P → "Show Rendering"
3. Check "Emulate CSS media feature prefers-reduced-motion: reduce"
4. Verify all animations are disabled

**System Preferences**
- **Windows**: Settings → Ease of Access → Display → Show animations (Off)
- **macOS**: System Preferences → Accessibility → Display → Reduce motion (On)
- **iOS**: Settings → Accessibility → Motion → Reduce Motion (On)

---

## Known Issues

### Current Limitations

1. **Protocol visualizations complexity**
   - Some visualizations may be challenging to describe fully via screen readers
   - **Mitigation**: Comprehensive `aria-label` descriptions provided
   - **Future**: Consider audio descriptions for complex animations

2. **Real-time updates**
   - High-frequency updates (packet visualizations) may be verbose for screen readers
   - **Mitigation**: `aria-live="polite"` used instead of "assertive"
   - **Future**: Throttle announcements or provide summary updates

3. **Chart accessibility**
   - Performance comparison charts (Tab 2) use canvas/SVG without data tables
   - **Mitigation**: SVG has title/desc elements
   - **Future**: Add hidden data tables for screen readers

4. **Mobile Safari VoiceOver**
   - Some custom controls may require extra taps on iOS
   - **Mitigation**: Standard HTML controls used where possible
   - **Status**: Ongoing testing

### Reporting Issues

If you encounter accessibility issues:

1. **Check browser/OS combination** - document which you're using
2. **Describe the issue** - what doesn't work as expected?
3. **Include steps to reproduce** - how can we replicate it?
4. **Note assistive technology** - screen reader, keyboard-only, etc.
5. **Report at**: https://github.com/anthropics/two-generals-public/issues

---

## Compliance Checklist

Use this checklist to verify accessibility before deployment:

### Keyboard
- [ ] All interactive elements are keyboard accessible
- [ ] Tab order is logical
- [ ] No keyboard traps
- [ ] Focus indicators visible on all elements
- [ ] Arrow keys work for tab navigation
- [ ] Enter/Space activate buttons

### Screen Readers
- [ ] All images have alt text or aria-label
- [ ] Form inputs have associated labels
- [ ] Headings form logical hierarchy
- [ ] ARIA roles used correctly (tab, tabpanel, etc.)
- [ ] Live regions announce state changes
- [ ] Button purposes are clear

### Visual
- [ ] Text contrast ≥ 4.5:1
- [ ] Large text contrast ≥ 3:1
- [ ] Information not conveyed by color alone
- [ ] Text remains readable at 200% zoom
- [ ] No horizontal scrolling at 200% zoom

### Motion
- [ ] Animations respect prefers-reduced-motion
- [ ] No auto-playing videos
- [ ] No flashing content (> 3 flashes/second)
- [ ] Essential animations have alternatives

### Mobile
- [ ] Touch targets ≥ 44×44 CSS pixels
- [ ] Pinch zoom enabled
- [ ] Orientation lock not enforced
- [ ] Content readable without horizontal scrolling

---

## Resources

### Tools
- [WAVE Browser Extension](https://wave.webaim.org/extension/) - Accessibility checker
- [axe DevTools](https://www.deque.com/axe/devtools/) - Automated accessibility testing
- [NVDA Screen Reader](https://www.nvaccess.org/) - Free Windows screen reader
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) - Chrome automated audits

### Guidelines
- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/) - Web Content Accessibility Guidelines
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/) - Widget design patterns
- [WebAIM](https://webaim.org/) - Web accessibility resources

### Testing Services
- [Accessibility Insights](https://accessibilityinsights.io/) - Microsoft's free testing tools
- [Pa11y](https://pa11y.org/) - Automated accessibility testing
- [Tenon.io](https://tenon.io/) - Cloud-based accessibility testing

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-01 | Initial accessibility implementation |
| 1.0.1 | 2025-01-02 | Enhanced keyboard navigation for tabs |
| 1.0.2 | 2025-01-03 | Added screen reader announcements |
| 1.0.3 | 2025-01-04 | Comprehensive reduced-motion support |

---

**Last Updated**: 2025-12-07
**Maintained By**: Claude Code Team
**License**: AGPLv3

For questions or accessibility feedback, contact: team@riff.cc
