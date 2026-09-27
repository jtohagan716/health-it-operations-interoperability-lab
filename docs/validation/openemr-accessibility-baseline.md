# OpenEMR Accessibility Baseline

## Objective

This validation establishes a repeatable accessibility smoke baseline for selected OpenEMR workflows using Playwright and axe-core.

The test evaluates WCAG 2.0 A/AA and Section 508-oriented rules.

This is an independent QA validation exercise. It is not a formal Section 508 conformance determination, VPAT, or accessibility certification.

## Test Environment

- Application: OpenEMR running locally in Docker
- Base URL: http://localhost:8300
- Browser: Chromium
- Playwright: 1.63.0
- axe-core: 4.13.0
- Test data: Local synthetic/non-production environment
- axe rule tags: wcag2a, wcag2aa, section508

## Execution

Command:

```powershell
npm run test:ui:a11y
```

Result:

```text
1 passed
```

The test is currently configured as an advisory baseline. Accessibility findings are reported and attached to the Playwright report, but they do not yet cause the test to fail.

## Workflow States Tested

The test evaluates three application states:

1. OpenEMR login page
2. Authenticated OpenEMR application shell
3. Patient-search container and embedded patient form

The successful run produced 11 state-level violation categories across 6 unique axe rule IDs.

## Login Page Findings

### Color contrast

Affected element:

```html
<button id="login-button" class="btn btn-primary flex-fill">
  Login
</button>
```

Observed contrast:

```text
Foreground: #ffffff
Background: #007bff
Measured ratio: 3.97:1
Expected ratio: 4.5:1
```

This was reported as a serious WCAG AA color-contrast finding.

### Missing accessible name

Affected element:

```html
<select class="form-control" name="languageChoice" size="1">
```

The selector did not have an associated label, aria-label, aria-labelledby attribute, or title.

This was reported under the axe `select-name` rule.

## Authenticated Shell Findings

### Missing iframe title

Affected element:

```html
<iframe src="/interface/main/main_info.php" name="cal">
</iframe>
```

The iframe did not provide an accessible title or equivalent accessible name.

### Missing document language

The embedded document contained:

```html
<html>
```

without a `lang` attribute.

### Unnamed menu link

Affected element:

```html
<a id="menu-toggle" href="#" class="btn btn-outline-dark">
  <i class="fas fa-bars"></i>
</a>
```

The icon-only link did not provide a discernible accessible name.

### Unnamed select controls

Affected elements:

```html
<select name="pc_facility" id="pc_facility" class="view1 form-control">
```

and:

```html
<select multiple size="5" name="pc_username[]" id="pc_username" class="view2 form-control">
```

Neither control had an associated accessible name.

### Color contrast

The authenticated shell included several contrast findings involving calendar and provider controls.

Examples included:

- Hidden tab text with a measured ratio of 2.53:1
- Day, week, and month buttons with a measured ratio of 3.97:1
- Current-date calendar styling with a measured ratio of 2.27:1
- Provider header styling with a measured ratio of 3.97:1

The WCAG AA target for normal-sized text is 4.5:1.

## Patient-Search Container Findings

### Invalid ARIA control references

Example:

```html
<button
  data-target="#div_5"
  aria-controls="5">
  Stats
</button>
```

The `aria-controls` value does not match the controlled element ID referenced by `data-target`.

Similar findings were reported for several patient-form sections, including:

- Stats
- Misc
- Related
- Insurance

This was reported under the axe `aria-valid-attr-value` rule.

### Missing iframe title

Affected element:

```html
<iframe src="/interface/new/new.php" name="pat">
</iframe>
```

The patient-form iframe did not provide an accessible title or equivalent accessible name.

### Missing document language

The embedded patient form contained an HTML document without a `lang` attribute.

### Color contrast

The patient form contained controls with insufficient contrast, including:

- Add button
- Create New Patient button

Both measured approximately 3.97:1 against the expected 4.5:1 threshold.

## Interpretation

The automated run identified repeatable accessibility concerns across the login page, authenticated shell, and embedded patient-management views.

Several findings cluster within shared OpenEMR iframe-based components. This suggests that some issues may originate from common templates or UI conventions rather than isolated controls.

The findings should be manually reviewed before being classified as confirmed product defects. Automated axe testing does not replace keyboard navigation, focus-order, screen-reader, color-contrast, or assistive-technology testing.

The `critical` and `serious` labels are axe impact classifications. They indicate accessibility priority and user impact; they do not indicate security vulnerabilities.

## Evidence

The full results are available in the Playwright HTML report:

```powershell
npx playwright show-report artifacts\playwright-report
```

The automated test is located at:

```text
tests/ui/openemr/accessibility-smoke.spec.ts
```

## Limitations

- Testing was performed against a local OpenEMR instance only.
- No production or customer data was used.
- This work does not claim formal Section 508 compliance.
- The initial baseline is advisory and does not fail the build on accessibility findings.
- Findings were not remediated in the OpenEMR application during this exercise.
- Manual assistive-technology testing was not performed.

## Outcome

This work demonstrates a repeatable accessibility-focused QA process:

1. Authenticate to a healthcare application.
2. Exercise multiple functional workflow states.
3. Run automated WCAG-oriented checks.
4. Capture reproducible DOM evidence.
5. Group findings by shared component or frame.
6. Document limitations and distinguish automated findings from confirmed defects.

The baseline provides a foundation for future accessibility regression testing and targeted defect triage.