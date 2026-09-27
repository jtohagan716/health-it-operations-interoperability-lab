import { expect, test, type Page, type TestInfo } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const axeTags = ['wcag2a', 'wcag2aa', 'section508'];

async function scanState(
    page: Page,
    testInfo: TestInfo,
    state: string,
): Promise<void> {
    const results = await new AxeBuilder({ page })
        .withTags(axeTags)
        .analyze();

    await testInfo.attach(`${state}-axe-results.json`, {
        body: JSON.stringify(results, null, 2),
        contentType: 'application/json',
    });

    const summary = results.violations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        helpUrl: violation.helpUrl,
        nodes: violation.nodes.map((node) => node.target),
    }));

    console.log(`[axe] ${state}: ${summary.length} violation type(s)`);

    if (summary.length > 0) {
        console.table(summary);
    }

    if (process.env.ACCESSIBILITY_FAIL_ON_VIOLATIONS === '1') {
        expect(summary, `${state} accessibility violations`).toEqual([]);
    }
}

test.describe('OpenEMR accessibility baseline', () => {
    test('authenticated shell and patient search container', async ({ page }, testInfo) => {
        test.setTimeout(120_000);

        const username = process.env.OPENEMR_ADMIN_USER;
        const password = process.env.OPENEMR_ADMIN_PASSWORD;

        expect(username, 'OPENEMR_ADMIN_USER must be set').toBeTruthy();
        expect(password, 'OPENEMR_ADMIN_PASSWORD must be set').toBeTruthy();

        await page.goto('/interface/login/login.php?site=default', {
            waitUntil: 'domcontentloaded',
            timeout: 30_000,
        });

        await scanState(page, testInfo, 'login-page');

        await page.getByRole('textbox', { name: 'Username' }).fill(username!);
        await page.getByRole('textbox', { name: 'Password' }).fill(password!);

        const authenticatedNavigation = page.waitForResponse(
            (response) =>
                response.request().isNavigationRequest() &&
                response.request().method() === 'GET' &&
                response.url().includes('/interface/main/tabs/main.php') &&
                response.status() === 200,
            {
                timeout: 30_000,
            },
        );

        await page.getByRole('button', { name: 'Login' }).click({
            noWaitAfter: true,
        });

        const authenticationResponse = await authenticatedNavigation;

        expect(authenticationResponse.status()).toBe(200);

        await expect(page).toHaveURL(
            /\/interface\/main\/tabs\/main\.php\?token_main=/,
            {
                timeout: 30_000,
            },
        );

        await expect(page).toHaveTitle(/OpenEMR/i);

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

        await scanState(page, testInfo, 'authenticated-shell');

        await patientMenu.click();
        await page.getByText('New/Search', { exact: true }).click();

        const patientSearchFrame = page.frameLocator('iframe[name="pat"]');

        await expect(patientSearchFrame.locator('#search')).toBeVisible({
            timeout: 30_000,
        });

        await scanState(page, testInfo, 'patient-search-container');
    });
});