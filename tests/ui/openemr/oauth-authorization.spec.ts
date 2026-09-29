import {
    expect,
    request as playwrightRequest,
    test,
} from '@playwright/test';

import { randomBytes } from 'node:crypto';

import {
    existsSync,
    mkdirSync,
    readFileSync,
    writeFileSync,
} from 'node:fs';

import { tmpdir } from 'node:os';

import {
    dirname,
    join,
} from 'node:path';

test.use({
    ignoreHTTPSErrors: true,
});

test.describe(
    'OpenEMR SMART OAuth authorization',
    () => {
        test(
            'acquires a ServiceRequest write-scoped token',
            async ({ page }) => {
                test.setTimeout(90_000);

                const baseUrl = (
                    process.env.OPENEMR_BASE_URL ??
                    'https://localhost:9340'
                ).replace(/\/+$/, '');

                const registrationPath =
                    process.env.OPENEMR_FHIR_REGISTRATION_FILE ??
                    join(
                        tmpdir(),
                        'openemr-fhir-write-registration.json',
                    );

                const outputTokenPath =
                    process.env.OPENEMR_OAUTH_TOKEN_PATH ??
                    join(
                        tmpdir(),
                        'openemr-fhir-write-token.json',
                    );

                const openEmrUser =
                    process.env.OPENEMR_ADMIN_USER ?? '';

                const openEmrPassword =
                    process.env.OPENEMR_ADMIN_PASSWORD ?? '';

                expect(
                    openEmrUser,
                    'OPENEMR_ADMIN_USER must be defined',
                ).toBeTruthy();

                expect(
                    openEmrPassword,
                    'OPENEMR_ADMIN_PASSWORD must be defined',
                ).toBeTruthy();

                expect(
                    existsSync(registrationPath),
                    `OAuth registration file not found: ${registrationPath}`,
                ).toBe(true);

                const registrationText =
                    readFileSync(
                        registrationPath,
                        'utf8',
                    ).replace(/^\uFEFF/, '');

                const registration =
                    JSON.parse(registrationText);

                expect(
                    registration.client_id,
                    'OAuth client_id is missing',
                ).toBeTruthy();

                expect(
                    registration.client_secret,
                    'OAuth client_secret is missing',
                ).toBeTruthy();

                expect(
                    registration.redirect_uris?.[0],
                    'OAuth redirect URI is missing',
                ).toBeTruthy();

                const redirectUri =
                    registration.redirect_uris[0];

                const requestedScope = [
                    'openid',
                    'fhirUser',
                    'api:fhir',
                    'user/Patient.rs',
                    'user/ServiceRequest.cud',
                ].join(' ');

                const fhirBaseUrl =
                    `${baseUrl}/apis/default/fhir`;

                const authorizationEndpoint =
                    `${baseUrl}/oauth2/default/authorize`;

                const tokenEndpoint =
                    `${baseUrl}/oauth2/default/token`;

                const state =
                    randomBytes(16).toString('hex');

                const authorizeUrl =
                    `${authorizationEndpoint}?` +
                    new URLSearchParams({
                        response_type: 'code',
                        client_id: registration.client_id,
                        redirect_uri: redirectUri,
                        scope: requestedScope,
                        state,
                        aud: fhirBaseUrl,
                    }).toString();

                await page.goto(
                    authorizeUrl,
                    {
                        waitUntil: 'domcontentloaded',
                        timeout: 30_000,
                    },
                );

                await expect(
                    page.getByRole(
                        'textbox',
                        {
                            name: 'Username',
                        },
                    ),
                ).toBeVisible();

                await page
                    .getByRole(
                        'textbox',
                        {
                            name: 'Username',
                        },
                    )
                    .fill(openEmrUser);

                const passwordInput =
                    page.locator(
                        'input[type="password"]',
                    ).first();

                await expect(
                    passwordInput,
                ).toBeVisible();

                await passwordInput.fill(
                    openEmrPassword,
                );

                const scopeConfirmationResponsePromise =
                    page.waitForResponse(
                        (response) =>
                            response.request().method() ===
                            'POST' &&
                            response.url().includes(
                                '/oauth2/default/scope-authorize-confirm',
                            ) &&
                            response.status() === 200,
                        {
                            timeout: 30_000,
                        },
                    );

                await page
                    .getByRole(
                        'button',
                        {
                            name: /OpenEMR Login/i,
                        },
                    )
                    .click({
                        noWaitAfter: true,
                    });

                const scopeResponse =
                    await scopeConfirmationResponsePromise;

                expect(
                    scopeResponse.status(),
                ).toBe(200);

                await expect(page).toHaveURL(
                    /\/oauth2\/default\/scope-authorize-confirm/,
                );

                const serviceRequestMaster =
                    page.locator(
                        '.resource-master-checkbox[data-resource="user-ServiceRequest"]',
                    );

                await expect(
                    serviceRequestMaster,
                ).toBeVisible();

                await serviceRequestMaster.check();

                await expect(
                    serviceRequestMaster,
                ).toBeChecked();

                const serviceRequestControls =
                    await page
                        .locator(
                            '[data-resource="user-ServiceRequest"]',
                        )
                        .evaluateAll((elements) =>
                            elements.map((element) => ({
                                tag: element.tagName,
                                type: element.getAttribute('type'),
                                className: element.getAttribute('class'),
                                action: element.getAttribute('data-action'),
                                checked: (
                                    element as HTMLInputElement
                                ).checked,
                                disabled: (
                                    element as HTMLInputElement
                                ).disabled,
                            })),
                        );

                await test.info().attach(
                    'oauth-consent-controls',
                    {
                        body: JSON.stringify(
                            {
                                resource: 'ServiceRequest',
                                controls: serviceRequestControls,
                            },
                            null,
                            2,
                        ),
                        contentType: 'application/json',
                    },
                );

                const authorizeButton =
                    page.getByRole(
                        'button',
                        {
                            name: /authorize|allow|approve|continue|confirm/i,
                        },
                    ).last();

                let consentControl =
                    authorizeButton;

                if (
                    await authorizeButton.count() === 0
                ) {
                    consentControl =
                        page.locator(
                            'button[type="submit"], input[type="submit"]',
                        ).last();
                }

                await expect(
                    consentControl,
                ).toBeVisible();

                let submittedScopes: string[] = [];

                page.on(
                    'request',
                    (request) => {
                        if (
                            request.method() !== 'POST' ||
                            !request.url().includes(
                                '/oauth2/default/device/code',
                            )
                        ) {
                            return;
                        }

                        const postData =
                            request.postData() ?? '';

                        submittedScopes =
                            Array.from(
                                new URLSearchParams(
                                    postData,
                                ).entries(),
                            )
                                .filter(([key]) =>
                                    key.startsWith('scope['),
                                )
                                .map(([, value]) => value);
                    },
                );

                const deviceCodeResponsePromise =
                    page.waitForResponse(
                        (response) =>
                            response.request().method() ===
                            'POST' &&
                            response.url().includes(
                                '/oauth2/default/device/code',
                            ) &&
                            [
                                301,
                                302,
                                303,
                                307,
                                308,
                            ].includes(response.status()),
                        {
                            timeout: 30_000,
                        },
                    );

                await consentControl.click({
                    noWaitAfter: true,
                });

                const deviceCodeResponse =
                    await deviceCodeResponsePromise;

                await test.info().attach(
                    'oauth-submitted-scopes',
                    {
                        body: JSON.stringify(
                            {
                                scopes: submittedScopes,
                            },
                            null,
                            2,
                        ),
                        contentType: 'application/json',
                    },
                );

                const redirectLocation =
                    deviceCodeResponse.headers().location;

                expect(
                    redirectLocation,
                    'OAuth device-code response did not contain a redirect location',
                ).toBeTruthy();

                const callback =
                    new URL(
                        redirectLocation!,
                        baseUrl,
                    );

                expect(
                    `${callback.origin}${callback.pathname}`,
                ).toBe(redirectUri);

                expect(
                    callback.searchParams.get('state'),
                ).toBe(state);

                const authorizationCode =
                    callback.searchParams.get('code');

                expect(
                    authorizationCode,
                    'OAuth redirect did not contain an authorization code',
                ).toBeTruthy();

                const tokenClient =
                    await playwrightRequest.newContext({
                        ignoreHTTPSErrors: true,
                    });

                let tokenStatus = 0;

                let token: Record<
                    string,
                    any
                > = {};

                try {
                    const tokenResponse =
                        await tokenClient.post(
                            tokenEndpoint,
                            {
                                form: {
                                    grant_type:
                                        'authorization_code',
                                    client_id:
                                        registration.client_id,
                                    client_secret:
                                        registration.client_secret,
                                    redirect_uri:
                                        redirectUri,
                                    code:
                                        authorizationCode,
                                },
                                timeout: 30_000,
                            },
                        );

                    tokenStatus =
                        tokenResponse.status();

                    token =
                        await tokenResponse.json();
                } finally {
                    await tokenClient.dispose();
                }

                expect(
                    tokenStatus,
                ).toBe(200);

                expect(
                    token.access_token,
                    'Token response did not contain access_token',
                ).toBeTruthy();

                const grantedScopes =
                    String(
                        token.scope ?? '',
                    )
                        .split(/\s+/)
                        .filter(Boolean);

                const serviceRequestActions =
                    new Set<string>();

                for (const scope of grantedScopes) {
                    const match =
                        /^user\/ServiceRequest\.([cruds]+)(?:\?.*)?$/
                            .exec(scope);

                    if (!match) {
                        continue;
                    }

                    for (const action of match[1]) {
                        serviceRequestActions.add(action);
                    }
                }

                for (const requiredAction of [
                    'c',
                    'u',
                    'd',
                ]) {
                    expect(
                        serviceRequestActions.has(
                            requiredAction,
                        ),
                        `Granted scopes did not include ServiceRequest action ${requiredAction}: ${grantedScopes.join(' ')}`,
                    ).toBe(true);
                }

                const acquiredAtUtc =
                    new Date().toISOString();

                const expiresInSeconds =
                    Number(
                        token.expires_in ?? 0,
                    );

                const expiresAtUtc =
                    new Date(
                        Date.now() +
                        expiresInSeconds * 1000,
                    ).toISOString();

                mkdirSync(
                    dirname(outputTokenPath),
                    {
                        recursive: true,
                    },
                );

                writeFileSync(
                    outputTokenPath,
                    JSON.stringify(
                        {
                            ...token,
                            acquired_at_utc:
                                acquiredAtUtc,
                            expires_at_utc:
                                expiresAtUtc,
                        },
                        null,
                        2,
                    ),
                    {
                        encoding: 'utf8',
                    },
                );

                console.log(
                    'OAuth token acquisition passed.',
                );

                console.log(
                    `Granted scope count: ${grantedScopes.length}`,
                );

                console.log(
                    `Token written outside repository: ${outputTokenPath}`,
                );
            },
        );
    },
);