import { expect, test } from '@playwright/test';

test.describe('OpenEMR patient chart smoke', () => {
  test('finds and opens a deterministic synthetic patient chart', async ({
    page,
  }) => {
    test.setTimeout(90_000);

    const username = process.env.OPENEMR_ADMIN_USER;
    const password = process.env.OPENEMR_ADMIN_PASSWORD;

    const patientFirstName = 'Synthetic001';
    const patientMiddleName = 'Test';
    const patientLastName = 'Patient001';
    const patientMrn = 'SYNTHMRN000001';
    const patientDisplayName = 'Patient001, Synthetic001';

    expect(
      username,
      'OPENEMR_ADMIN_USER must be defined in .env',
    ).toBeTruthy();

    expect(
      password,
      'OPENEMR_ADMIN_PASSWORD must be defined in .env',
    ).toBeTruthy();

    // ---------------------------------------------------------
    // Authenticate
    // ---------------------------------------------------------

    await page.goto(
      '/interface/login/login.php?site=default',
      {
        waitUntil: 'domcontentloaded',
        timeout: 30_000,
      },
    );

    await page
      .getByRole('textbox', { name: 'Username' })
      .fill(username!);

    await page
      .getByRole('textbox', { name: 'Password' })
      .fill(password!);

    /*
     * OpenEMR authentication posts through main_screen.php and
     * then navigates to the authenticated tabs shell.
     *
     * Synchronize against that successful navigation response
     * rather than allowing Playwright's click action to wait
     * generically for navigation completion.
     */
    const authenticatedNavigation =
      page.waitForResponse(
        (response) =>
          response.request().isNavigationRequest() &&
          response.request().method() === 'GET' &&
          response.url().includes(
            '/interface/main/tabs/main.php',
          ) &&
          response.status() === 200,
      );

    await page
      .getByRole('button', { name: 'Login' })
      .click({
        noWaitAfter: true,
      });

    const authenticationResponse =
      await authenticatedNavigation;

    expect(authenticationResponse.status()).toBe(200);

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
      {
        timeout: 30_000,
      },
    );

    await expect(page).toHaveTitle(/OpenEMR/i);

    // ---------------------------------------------------------
    // Wait for authenticated OpenEMR shell
    // ---------------------------------------------------------

    const patientMenu = page.getByRole('button', {
      name: 'Patient',
      exact: true,
    });

    await expect(
      patientMenu,
      'OpenEMR authenticated shell did not expose the Patient menu',
    ).toBeVisible({
      timeout: 30_000,
    });

    // ---------------------------------------------------------
    // Open Patient -> New/Search
    // ---------------------------------------------------------

    await patientMenu.click();

    const newSearch = page.getByText('New/Search', {
      exact: true,
    });

    await expect(
      newSearch,
      'OpenEMR Patient menu did not expose New/Search',
    ).toBeVisible({
      timeout: 10_000,
    });

    await newSearch.click();

    // ---------------------------------------------------------
    // Locate the OpenEMR patient-search view
    // ---------------------------------------------------------

    const patientFrame = page.frameLocator(
      'iframe[name="pat"]',
    );

    const firstNameField = patientFrame.locator(
      '#form_fname',
    );

    const lastNameField = patientFrame.locator(
      '#form_lname',
    );

    const searchButton = patientFrame.locator(
      '#search',
    );

    /*
     * Waiting for #search is intentional.
     *
     * OpenEMR's large patient form can expose individual
     * demographic fields before the complete search UI has
     * finished parsing and initializing.
     */
    await expect(
      searchButton,
      'OpenEMR patient-search UI did not finish loading',
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(firstNameField).toBeVisible();
    await expect(lastNameField).toBeVisible();

    // ---------------------------------------------------------
    // Activate and populate deterministic search criteria
    // ---------------------------------------------------------

    /*
     * OpenEMR uses a click handler (toggleSearch) to mark
     * demographic fields as active patient-search criteria.
     *
     * Therefore these clicks are part of the application
     * workflow and must occur before filling the fields.
     */
    await firstNameField.click();
    await firstNameField.fill(patientFirstName);

    await lastNameField.click();
    await lastNameField.fill(patientLastName);

    await expect(firstNameField).toHaveValue(
      patientFirstName,
    );

    await expect(lastNameField).toHaveValue(
      patientLastName,
    );

    // ---------------------------------------------------------
    // Execute the real OpenEMR patient search
    // ---------------------------------------------------------

    await searchButton.click();

    /*
     * OpenEMR dlgopen() renders the patient finder in a
     * dialog iframe rather than navigating the main page.
     */
    const finderIframe = page.locator(
      'iframe[src*="patient_select.php"]',
    );

    await expect(
      finderIframe,
      'OpenEMR did not open the patient finder dialog',
    ).toBeAttached({
      timeout: 30_000,
    });

    const finderFrame = page.frameLocator(
      'iframe[src*="patient_select.php"]',
    );

    // ---------------------------------------------------------
    // Validate deterministic finder result
    // ---------------------------------------------------------

    const patientResult = finderFrame.getByText(
      patientDisplayName,
      {
        exact: true,
      },
    );

    await expect(
      patientResult,
      'Deterministic synthetic patient was not returned by OpenEMR search',
    ).toBeVisible({
      timeout: 30_000,
    });

    await expect(
      finderFrame.getByText(patientMrn, {
        exact: true,
      }),
      'Returned patient did not contain the expected synthetic MRN',
    ).toBeVisible();

    // ---------------------------------------------------------
    // Select deterministic patient
    // ---------------------------------------------------------

    /*
     * Register the dialog handler before selecting the
     * patient because OpenEMR may optionally display a
     * JavaScript dialog during chart selection.
     */
    page.once('dialog', async (dialog) => {
      console.log(
        `[OPENEMR DIALOG] ${dialog.message()}`,
      );

      await dialog.accept();
    });

    /*
     * OpenEMR reuses the patient workspace iframe when the
     * finder result is selected. The iframe's DOM src
     * attribute is therefore not a reliable indication that
     * the Medical Record Dashboard has loaded.
     *
     * Synchronize instead against the actual frame navigation
     * to the patient-summary route observed at runtime.
     */
    const patientDashboardNavigation =
      page.waitForResponse(
        (response) =>
          response.request().isNavigationRequest() &&
          response.request().method() === 'GET' &&
          response.url().includes(
            '/interface/patient_file/summary/demographics.php',
          ) &&
          response.status() === 200,
        {
          timeout: 30_000,
        },
      );

    await patientResult.click();

    const dashboardResponse =
      await patientDashboardNavigation;

    expect(dashboardResponse.status()).toBe(200);

    // ---------------------------------------------------------
    // Validate selected patient chart
    // ---------------------------------------------------------

    /*
     * Find the frame by its current document URL rather than
     * by the iframe element's original src attribute.
     */
    await expect
      .poll(
        () =>
          page
            .frames()
            .some((frame) =>
              frame
                .url()
                .includes(
                  '/interface/patient_file/summary/demographics.php',
                ),
            ),
        {
          message:
            'OpenEMR patient-summary frame did not become active',
          timeout: 30_000,
        },
      )
      .toBe(true);

    const patientDashboard = page
      .frames()
      .find((frame) =>
        frame
          .url()
          .includes(
            '/interface/patient_file/summary/demographics.php',
          ),
      );

    expect(
      patientDashboard,
      'OpenEMR patient-summary frame was not available after navigation',
    ).toBeDefined();

    const dashboardTitle =
      `Medical Record Dashboard - ` +
      `${patientFirstName} ${patientMiddleName} ${patientLastName}`;

    /*
     * The dashboard heading proves that OpenEMR opened the
     * intended deterministic patient's Medical Record
     * Dashboard rather than merely retaining finder/search
     * content containing the same demographic values.
     */
    await expect(
      patientDashboard!.getByText(
        dashboardTitle,
        {
          exact: true,
        },
      ),
      'Selected synthetic patient Medical Record Dashboard did not expose the expected patient identity',
    ).toBeVisible({
      timeout: 30_000,
    });

    /*
     * The dashboard demographics expose the deterministic
     * synthetic MRN as OpenEMR's External ID. This provides
     * an independent identity assertion inside the active
     * patient chart.
     */
    await expect(
      patientDashboard!.getByText(
        patientMrn,
        {
          exact: true,
        },
      ),
      'Active patient dashboard did not expose the expected synthetic MRN',
    ).toBeVisible({
      timeout: 30_000,
    });
  });
});
