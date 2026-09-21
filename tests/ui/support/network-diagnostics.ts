import type {
    Page,
    Request,
    Response,
} from '@playwright/test';
import { performance } from 'node:perf_hooks';


type RequestEndEvent = 'finished' | 'failed';


type NetworkEvent = {
    sequence: number;
    method: string;
    resource_type: string;
    path: string;
    request_started_ms: number;
    response_received_ms: number | null;
    request_ended_ms: number | null;
    duration_to_response_ms: number | null;
    duration_to_end_ms: number | null;
    status: number | null;
    end_event: RequestEndEvent | null;
    failed: boolean;
    failure_text: string | null;
};


type NetworkCheckpoint = {
    name: string;
    elapsed_ms: number;
};


type NetworkDiagnosticSummary = {
    schema: 'playwright.network-diagnostics.v2';
    workflow: string;
    enabled: true;
    measurement_layer: 'playwright_network_observer';
    run_started_at: string;
    observation_elapsed_ms: number;
    request_count: number;
    ended_count: number;
    finished_count: number;
    failed_count: number;
    outstanding_count: number;
    checkpoints: NetworkCheckpoint[];
    events: NetworkEvent[];
};


type NetworkDiagnostics = {
    enabled: boolean;
    checkpoint: (name: string) => void;
    finish: () => void;
};


type InternalRequestRecord = {
    sequence: number;
    method: string;
    resourceType: string;
    path: string;
    startedAt: number;
    responseReceivedAt: number | null;
    endedAt: number | null;
    status: number | null;
    endEvent: RequestEndEvent | null;
    failureText: string | null;
};


function sanitizeRequestPath(rawUrl: string): string {
    try {
        const parsed = new URL(rawUrl);

        /*
         * Deliberately retain only the pathname.
         *
         * Query-string values can contain session identifiers, CSRF tokens,
         * patient-search values, record identifiers, or other sensitive
         * runtime data. Network diagnostics are intended to identify the
         * endpoint and timing boundary, not capture request parameters.
         */
        return parsed.pathname;
    } catch {
        /*
         * Playwright normally supplies absolute HTTP(S) URLs here. If an
         * unusual URL cannot be parsed, do not fall back to the raw value
         * because doing so could reintroduce sensitive query data.
         */
        return '[unparseable-url]';
    }
}


export function createNetworkDiagnostics(
    page: Page,
    workflow: string,
): NetworkDiagnostics {
    const enabled =
        process.env.PLAYWRIGHT_NETWORK_DIAGNOSTICS === '1';

    if (!enabled) {
        return {
            enabled: false,
            checkpoint: () => { },
            finish: () => { },
        };
    }

    const observationStart = performance.now();
    const runStartedAt = new Date().toISOString();

    const records = new Map<Request, InternalRequestRecord>();
    const checkpoints: NetworkCheckpoint[] = [];

    let sequence = 0;

    const elapsed = (): number =>
        Math.round(performance.now() - observationStart);

    const onRequest = (request: Request): void => {
        sequence += 1;

        records.set(request, {
            sequence,
            method: request.method(),
            resourceType: request.resourceType(),
            path: sanitizeRequestPath(request.url()),
            startedAt: performance.now(),
            responseReceivedAt: null,
            endedAt: null,
            status: null,
            endEvent: null,
            failureText: null,
        });
    };

    const onResponse = (response: Response): void => {
        const request = response.request();
        const record = records.get(request);

        if (!record) {
            return;
        }

        record.responseReceivedAt = performance.now();
        record.status = response.status();
    };

    const onRequestFinished = (request: Request): void => {
        const record = records.get(request);

        if (!record) {
            return;
        }

        record.endedAt = performance.now();
        record.endEvent = 'finished';
    };

    const onRequestFailed = (request: Request): void => {
        const record = records.get(request);

        if (!record) {
            return;
        }

        record.endedAt = performance.now();
        record.endEvent = 'failed';
        record.failureText =
            request.failure()?.errorText ?? 'unknown failure';
    };

    page.on('request', onRequest);
    page.on('response', onResponse);
    page.on('requestfinished', onRequestFinished);
    page.on('requestfailed', onRequestFailed);

    const checkpoint = (name: string): void => {
        checkpoints.push({
            name,
            elapsed_ms: elapsed(),
        });
    };

    const finish = (): void => {
        const observationEnd = performance.now();

        page.off('request', onRequest);
        page.off('response', onResponse);
        page.off('requestfinished', onRequestFinished);
        page.off('requestfailed', onRequestFailed);

        const events: NetworkEvent[] = Array.from(
            records.values(),
        )
            .sort((left, right) => left.sequence - right.sequence)
            .map((record) => ({
                sequence: record.sequence,
                method: record.method,
                resource_type: record.resourceType,
                path: record.path,

                request_started_ms: Math.round(
                    record.startedAt - observationStart,
                ),

                response_received_ms:
                    record.responseReceivedAt === null
                        ? null
                        : Math.round(
                            record.responseReceivedAt -
                            observationStart,
                        ),

                request_ended_ms:
                    record.endedAt === null
                        ? null
                        : Math.round(
                            record.endedAt - observationStart,
                        ),

                duration_to_response_ms:
                    record.responseReceivedAt === null
                        ? null
                        : Math.round(
                            record.responseReceivedAt -
                            record.startedAt,
                        ),

                duration_to_end_ms:
                    record.endedAt === null
                        ? null
                        : Math.round(
                            record.endedAt - record.startedAt,
                        ),

                status: record.status,
                end_event: record.endEvent,
                failed: record.endEvent === 'failed',
                failure_text: record.failureText,
            }));

        const endedCount = events.filter(
            (event) => event.end_event !== null,
        ).length;

        const finishedCount = events.filter(
            (event) => event.end_event === 'finished',
        ).length;

        const failedCount = events.filter(
            (event) => event.end_event === 'failed',
        ).length;

        const outstandingCount = events.filter(
            (event) => event.end_event === null,
        ).length;

        const summary: NetworkDiagnosticSummary = {
            schema: 'playwright.network-diagnostics.v2',
            workflow,
            enabled: true,
            measurement_layer:
                'playwright_network_observer',
            run_started_at: runStartedAt,
            observation_elapsed_ms: Math.round(
                observationEnd - observationStart,
            ),
            request_count: events.length,
            ended_count: endedCount,
            finished_count: finishedCount,
            failed_count: failedCount,
            outstanding_count: outstandingCount,
            checkpoints,
            events,
        };

        console.log(
            `[NETWORK_DIAGNOSTICS] ${JSON.stringify(summary)}`,
        );
    };

    return {
        enabled,
        checkpoint,
        finish,
    };
}