import { expect, test } from '@playwright/test';

import { createNetworkDiagnostics } from '../support/network-diagnostics';
import { createPerformanceProbe } from '../support/performance-probe';

test.skip(
  process.env.OPENEMR_PERFORMANCE_SITE !== '1',
  'Requires the isolated 50,000-patient performance site',
);

test.describe('OpenEMR patient name-search latency attribution', () => {
  test('attributes the common-surname finder lifecycle', async ({
    page,
  }) => {
    /*
     * This is an integration-style browser workflow running
     * against a local containerized OpenEMR instance.
     *
     * Individual application transitions remain bounded by
     * shorter explicit timeouts below. The larger test-level
     * budget allows those legitimate transitions to occur
     * sequentially without the overall test timeout becoming
     * the limiting factor.
     */
    test.setTimeout(240_000);

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

    /*
     * Lightweight performance instrumentation is disabled by
     * default.
     *
     * Set PLAYWRIGHT_PERF=1 to collect client-observed timing
     * boundaries and derived segments for this workflow.
     *
     * These measurements describe elapsed time as observed by
     * the Playwright client. They must not be interpreted as
     * server-processing, network-only, browser-rendering, or
     * database execution time without additional correlated
     * evidence from those layers.
     */
    const perf = createPerformanceProbe(
      'openemr.name-search-latency-attribution',
    );

    const network = createNetworkDiagnostics(
      page,
      'openemr.name-search-latency-attribution',
    );
    /*
     * Install observation code in every document created after
     * this point, including the patient finder iframe.
     *
     * Navigation Timing supplies browser-owned lifecycle
     * boundaries. Long Task Timing reveals main-thread tasks
     * exceeding 50 ms. Neither API measures PHP or database
     * execution directly.
     */
    await page.addInitScript(() => {
      const latencyWindow = window as typeof window & {
        __openemrLatencyLongTasks?: Array<{
          startTime: number;
          duration: number;
        }>;
      };

      latencyWindow.__openemrLatencyLongTasks = [];

      if (!('PerformanceObserver' in window)) {
        return;
      }

      try {
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            latencyWindow.__openemrLatencyLongTasks?.push({
              startTime: entry.startTime,
              duration: entry.duration,
            });
          }
        });

        observer.observe({
          type: 'longtask',
          buffered: true,
        });
      } catch {
        /*
         * Long Task Timing may be unavailable. Navigation
         * timing remains valid and absence is reported rather
         * than failing the workflow.
         */
      }
    });

    /*
     * Controlled diagnostic condition: intercept only the
     * browser-triggered background-service request so its
     * relationship to foreground patient-chart latency can
     * be measured without changing OpenEMR configuration.
     */
    const suppressBackgroundRun =
      process.env.PLAYWRIGHT_SUPPRESS_BACKGROUND_RUN === '1';

    let suppressedBackgroundRunCount = 0;

    if (suppressBackgroundRun) {
      await page.route(
        '**/api/background_service/$run',
        async (route) => {
          suppressedBackgroundRunCount += 1;

          console.log('[BACKGROUND_RUN_INTERCEPTED]');

          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              diagnostic: 'background_run_suppressed',
            }),
          });
        },
      );
    }

    perf.mark('workflow.start');

    // ---------------------------------------------------------
    // Authenticate
    // ---------------------------------------------------------

    perf.mark('login_navigation.start');

    await page.goto(
      '/interface/login/login.php?site=performance',
      {
        waitUntil: 'domcontentloaded',
        timeout: 90_000,
      },
    );

    perf.mark('login_navigation.domcontentloaded');

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
        {
          timeout: 90_000,
        },
      );

    perf.mark('authentication.submit');

    await page
      .getByRole('button', { name: 'Login' })
      .click({
        noWaitAfter: true,
      });

    const authenticationResponse =
      await authenticatedNavigation;

    expect(authenticationResponse.status()).toBe(200);

    perf.mark('authentication.response');
    network.checkpoint('authentication.response');

    await expect(page).toHaveURL(
      /\/interface\/main\/tabs\/main\.php\?token_main=/,
      {
        timeout: 90_000,
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
      timeout: 90_000,
    });

    perf.mark('authenticated_shell.ready');
    network.checkpoint('authenticated_shell.ready');

    /*
     * A newly installed OpenEMR environment may display its
     * optional product-registration modal asynchronously.
     * Resolve it before opening the Patient menu because its
     * appearance can close an already-open submenu.
     */
    const registrationModal = page.locator(
      '.product-registration-modal',
    );

    const registrationAppeared = await registrationModal
      .waitFor({
        state: 'visible',
        timeout: 5_000,
      })
      .then(() => true)
      .catch(() => false);

    if (registrationAppeared) {
      await registrationModal.locator('.nothanks').click();

      await expect(registrationModal).toBeHidden({
        timeout: 10_000,
      });
    }

    // ---------------------------------------------------------
    // Open Patient -> New/Search
    // ---------------------------------------------------------

    perf.mark('patient_search_initialization.start');

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
      timeout: 90_000,
    });

    await expect(firstNameField).toBeVisible();
    await expect(lastNameField).toBeVisible();

    perf.mark('patient_search_initialization.ready');

    /*
     * The optional registration modal may appear after the
     * patient-search frame has loaded. Dismiss this late arrival
     * before interacting with the underlying search fields.
     */
    if (await registrationModal.isVisible()) {
      await registrationModal.locator('.nothanks').click();

      await expect(registrationModal).toBeHidden({
        timeout: 10_000,
      });
    }

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
    await lastNameField.click();
    await lastNameField.fill('Smith');

    await expect(lastNameField).toHaveValue('Smith');
    // ---------------------------------------------------------
    // Execute the real OpenEMR patient search
    // ---------------------------------------------------------

    const clientLifecycle: Record<string, number | null> = {
      search_submit_epoch_ms: null,
      request_observed_epoch_ms: null,
      response_headers_epoch_ms: null,
      iframe_attached_epoch_ms: null,
      first_row_visible_epoch_ms: null,
      hundred_rows_present_epoch_ms: null,
      validation_complete_epoch_ms: null,
    };

    /*
     * Register both observers before clicking Search so a fast
     * document request cannot occur before Playwright begins
     * listening. Restrict the match to the patient finder
     * document rather than its scripts, styles, or images.
     */
    const finderRequestPromise = page
      .waitForRequest(
        (request) =>
          request.resourceType() === 'document' &&
          request.url().includes('patient_select.php'),
        {
          timeout: 90_000,
        },
      )
      .then((request) => {
        clientLifecycle.request_observed_epoch_ms =
          Date.now();

        return request;
      });

    const finderResponsePromise = page
      .waitForResponse(
        (response) =>
          response.request().resourceType() ===
          'document' &&
          response.url().includes(
            'patient_select.php',
          ),
        {
          timeout: 90_000,
        },
      )
      .then((response) => {
        clientLifecycle.response_headers_epoch_ms =
          Date.now();

        return response;
      });

    clientLifecycle.search_submit_epoch_ms =
      Date.now();
    perf.mark('finder_search.submit');

    await searchButton.click();

    /*
     * OpenEMR dlgopen() renders the patient finder in a
     * dialog iframe rather than navigating the main page.
     *
     * Attachment proves that the dialog iframe exists, but it
     * does not prove that OpenEMR has finished populating the
     * search-results table inside that iframe.
     */
    const finderIframe = page.locator(
      'iframe[src*="patient_select.php"]',
    );

    await expect(
      finderIframe,
      'OpenEMR did not open the patient finder dialog',
    ).toBeAttached({
      timeout: 90_000,
    });

    clientLifecycle.iframe_attached_epoch_ms =
      Date.now();
    perf.mark('finder_iframe.attached');

    const finderFrame = page.frameLocator(
      'iframe[src*="patient_select.php"]',
    );

    // ---------------------------------------------------------
    // Qualify the common-surname first page
    // ---------------------------------------------------------

    const resultRows = finderFrame.locator('tr.oneresult');

    await expect(
      resultRows.first(),
      'OpenEMR did not render the first Smith search result',
    ).toBeVisible({
      timeout: 90_000,
    });
    clientLifecycle.first_row_visible_epoch_ms =
      Date.now();
    perf.mark('finder_first_row.visible');

    await expect(
      resultRows,
      'Smith prefix search did not render the expected 100-row first page',
    ).toHaveCount(100, {
      timeout: 90_000,
    });
    clientLifecycle.hundred_rows_present_epoch_ms =
      Date.now();
    perf.mark('finder_hundred_rows.present');

    const displayedNames = await resultRows
      .locator('td.srName')
      .allTextContents();

    expect(displayedNames).toHaveLength(100);

    for (const displayedName of displayedNames) {
      expect(displayedName.trim()).toMatch(/^Smith,/);
    }

    clientLifecycle.validation_complete_epoch_ms =
      Date.now();
    perf.mark('finder_result.ready');
    network.checkpoint('finder_result.ready');

    /*
     * Resolve the request and response captured by observers
     * registered before the Search click. Navigation Timing
     * below supplies the browser-owned responseEnd and DOM
     * lifecycle boundaries.
     */
    const finderRequest = await finderRequestPromise;
    const finderResponse = await finderResponsePromise;

    /*
     * Evaluate inside the finder iframe. Using the existing
     * FrameLocator avoids converting the iframe Locator through
     * ElementHandle APIs and keeps the successful locator model
     * unchanged.
     */
    const browserTiming = await finderFrame
      .locator('html')
      .evaluate(() => {
        const navigation = performance.getEntriesByType(
          'navigation',
        )[0] as PerformanceNavigationTiming | undefined;

        const paints = Object.fromEntries(
          performance
            .getEntriesByType('paint')
            .map((entry) => [
              entry.name,
              Math.round(entry.startTime * 1000) /
              1000,
            ]),
        );

        const latencyWindow = window as typeof window & {
          __openemrLatencyLongTasks?: Array<{
            startTime: number;
            duration: number;
          }>;
        };

        const longTasks =
          latencyWindow.__openemrLatencyLongTasks ?? [];

        const roundedLongTasks = longTasks.map(
          (task) => ({
            start_time_ms:
              Math.round(task.startTime * 1000) /
              1000,
            duration_ms:
              Math.round(task.duration * 1000) /
              1000,
          }),
        );

        const totalLongTaskDuration =
          roundedLongTasks.reduce(
            (total, task) =>
              total + task.duration_ms,
            0,
          );

        return {
          time_origin_epoch_ms:
            performance.timeOrigin,
          navigation: navigation
            ? {
              fetch_start_ms:
                navigation.fetchStart,
              request_start_ms:
                navigation.requestStart,
              response_start_ms:
                navigation.responseStart,
              response_end_ms:
                navigation.responseEnd,
              dom_interactive_ms:
                navigation.domInteractive,
              dom_content_loaded_start_ms:
                navigation.domContentLoadedEventStart,
              dom_content_loaded_end_ms:
                navigation.domContentLoadedEventEnd,
              load_event_start_ms:
                navigation.loadEventStart,
              load_event_end_ms:
                navigation.loadEventEnd,
              duration_ms:
                navigation.duration,
              transfer_size_bytes:
                navigation.transferSize,
              encoded_body_size_bytes:
                navigation.encodedBodySize,
              decoded_body_size_bytes:
                navigation.decodedBodySize,
              redirect_count:
                navigation.redirectCount,
            }
            : null,
          paints,
          long_tasks: {
            performance_observer_present:
              'PerformanceObserver' in window,
            collection_initialized:
              Array.isArray(
                latencyWindow
                  .__openemrLatencyLongTasks,
              ),
            count: roundedLongTasks.length,
            total_duration_ms:
              Math.round(
                totalLongTaskDuration * 1000,
              ) / 1000,
            maximum_duration_ms:
              roundedLongTasks.length > 0
                ? Math.max(
                  ...roundedLongTasks.map(
                    (task) => task.duration_ms,
                  ),
                )
                : 0,
            entries: roundedLongTasks,
          },
        };
      });

    const requestTiming = finderRequest.timing();

    const elapsed = (
      start: number | null,
      end: number | null,
    ): number | null => {
      if (start === null || end === null) {
        return null;
      }

      return end - start;
    };

    const clientIntervals = {
      submit_to_request_observed_ms: elapsed(
        clientLifecycle.search_submit_epoch_ms,
        clientLifecycle.request_observed_epoch_ms,
      ),

      request_observed_to_response_headers_ms: elapsed(
        clientLifecycle.request_observed_epoch_ms,
        clientLifecycle.response_headers_epoch_ms,
      ),

      request_observed_to_iframe_attached_ms: elapsed(
        clientLifecycle.request_observed_epoch_ms,
        clientLifecycle.iframe_attached_epoch_ms,
      ),

      response_headers_to_iframe_attached_ms:
        clientLifecycle.response_headers_epoch_ms !== null &&
          clientLifecycle.iframe_attached_epoch_ms !== null &&
          clientLifecycle.response_headers_epoch_ms <=
          clientLifecycle.iframe_attached_epoch_ms
          ? elapsed(
            clientLifecycle.response_headers_epoch_ms,
            clientLifecycle.iframe_attached_epoch_ms,
          )
          : null,

      iframe_attached_to_response_headers_ms:
        clientLifecycle.response_headers_epoch_ms !== null &&
          clientLifecycle.iframe_attached_epoch_ms !== null &&
          clientLifecycle.iframe_attached_epoch_ms <
          clientLifecycle.response_headers_epoch_ms
          ? elapsed(
            clientLifecycle.iframe_attached_epoch_ms,
            clientLifecycle.response_headers_epoch_ms,
          )
          : null,

      iframe_attached_to_first_row_ms: elapsed(
        clientLifecycle.iframe_attached_epoch_ms,
        clientLifecycle.first_row_visible_epoch_ms,
      ),

      first_row_to_hundred_rows_ms: elapsed(
        clientLifecycle.first_row_visible_epoch_ms,
        clientLifecycle.hundred_rows_present_epoch_ms,
      ),

      hundred_rows_to_validation_complete_ms: elapsed(
        clientLifecycle.hundred_rows_present_epoch_ms,
        clientLifecycle.validation_complete_epoch_ms,
      ),

      submit_to_validation_complete_ms: elapsed(
        clientLifecycle.search_submit_epoch_ms,
        clientLifecycle.validation_complete_epoch_ms,
      ),
    };

    const navigationIntervals =
      browserTiming.navigation
        ? {
          request_to_first_byte_ms:
            browserTiming.navigation
              .response_start_ms -
            browserTiming.navigation
              .request_start_ms,
          response_transfer_ms:
            browserTiming.navigation
              .response_end_ms -
            browserTiming.navigation
              .response_start_ms,
          response_end_to_dom_interactive_ms:
            browserTiming.navigation
              .dom_interactive_ms -
            browserTiming.navigation
              .response_end_ms,
          response_end_to_dom_content_loaded_ms:
            browserTiming.navigation
              .dom_content_loaded_end_ms -
            browserTiming.navigation
              .response_end_ms,
          dom_content_loaded_to_load_end_ms:
            browserTiming.navigation
              .load_event_end_ms -
            browserTiming.navigation
              .dom_content_loaded_end_ms,
        }
        : null;

    const attribution = {
      schema:
        'playwright.openemr-name-search-attribution.v1',
      workflow:
        'openemr.name-search-latency-attribution',
      measurement_layers: [
        'playwright_client',
        'browser_navigation_timing',
        'browser_long_task_timing',
      ],
      finder: {
        method: finderRequest.method(),
        status: finderResponse.status(),
        status_text: finderResponse.statusText(),
        resource_type:
          finderRequest.resourceType(),
        url_path:
          new URL(finderRequest.url()).pathname,
      },
      client_lifecycle: clientLifecycle,
      client_intervals: clientIntervals,
      playwright_request_timing: requestTiming,
      browser_timing: browserTiming,
      browser_navigation_intervals:
        navigationIntervals,
      interpretation_boundaries: {
        request_observed:
          'Playwright observed the outgoing finder document request.',
        response_headers:
          'Playwright observed response headers; this approximates first-byte availability but is not PHP-only time.',
        response_end:
          'Chromium completed response transfer; DOM construction may continue afterward.',
        dom_content_loaded:
          'The finder document completed its DOMContentLoaded event.',
        load_event:
          'The finder document completed its load event.',
        first_row:
          'Playwright first observed a visible finder result row.',
        hundred_rows:
          'Playwright first observed the complete 100-row result page.',
        validation_complete:
          'Playwright completed all result-count and name-prefix assertions.',
        long_tasks:
          'Main-thread tasks longer than 50 ms observed through the Long Tasks API; zero entries do not prove zero browser work.',
      },
    };

    console.log(
      `[NAME_SEARCH_ATTRIBUTION] ${JSON.stringify(
        attribution,
      )}`,
    );

    perf.segment(
      'login_navigation',
      'login_navigation.start',
      'login_navigation.domcontentloaded',
    );

    perf.segment(
      'authentication_response',
      'authentication.submit',
      'authentication.response',
    );

    perf.segment(
      'authentication_to_usable_shell',
      'authentication.submit',
      'authenticated_shell.ready',
    );

    perf.segment(
      'patient_search_initialization',
      'patient_search_initialization.start',
      'patient_search_initialization.ready',
    );

    perf.segment(
      'finder_iframe_attachment',
      'finder_search.submit',
      'finder_iframe.attached',
    );

    perf.segment(
      'finder_result_post_attachment',
      'finder_iframe.attached',
      'finder_result.ready',
    );

    perf.segment(
      'finder_total',
      'finder_search.submit',
      'finder_result.ready',
    );

    perf.segment(
      'workflow_to_finder_result',
      'workflow.start',
      'finder_result.ready',
    );

    console.log(
      `[NAME_SEARCH_PILOT] ${JSON.stringify({
        site: 'performance',
        lastNamePrefix: 'Smith',
        expectedDatabaseRows: 50000,
        expectedPrefixMatches: 473,
        renderedFirstPageRows: displayedNames.length,
        allRenderedNamesMatchPrefix: displayedNames.every(
          (name) => /^Smith,/.test(name.trim()),
        ),
      })}`,
    );

    console.log(
      `[BACKGROUND_RUN_CONTROL] ${JSON.stringify({
        suppressed: suppressBackgroundRun,
        intercepted: suppressedBackgroundRunCount,
      })}`,
    );

    network.finish();
    perf.finish();
  });
});
