import { performance } from 'node:perf_hooks';

type PerformanceMark = {
    name: string;
    elapsed_ms: number;
};

type PerformanceSegment = {
    measurement: string;
    start_boundary: string;
    end_boundary: string;
    duration_ms: number;
    measurement_layer: 'playwright_client';
};

type PerformanceSummary = {
    schema: 'playwright.performance-probe.v1';
    workflow: string;
    run_started_at: string;
    measurement_layer: 'playwright_client';
    enabled: true;
    total_elapsed_ms: number;
    marks: PerformanceMark[];
    segments: PerformanceSegment[];
};

type PerformanceProbe = {
    enabled: boolean;
    mark: (name: string) => void;
    segment: (
        measurement: string,
        startBoundary: string,
        endBoundary: string,
    ) => void;
    finish: () => void;
};

export function createPerformanceProbe(
    workflow: string,
): PerformanceProbe {
    const enabled = process.env.PLAYWRIGHT_PERF === '1';

    if (!enabled) {
        return {
            enabled: false,
            mark: () => { },
            segment: () => { },
            finish: () => { },
        };
    }

    const runStartedAt = new Date().toISOString();
    const workflowStart = performance.now();

    const markTimes = new Map<string, number>();

    const marks: PerformanceMark[] = [];
    const segments: PerformanceSegment[] = [];

    const mark = (name: string): void => {
        if (markTimes.has(name)) {
            throw new Error(
                `Performance boundary "${name}" was recorded more than once`,
            );
        }

        const now = performance.now();

        markTimes.set(name, now);

        marks.push({
            name,
            elapsed_ms: Math.round(now - workflowStart),
        });
    };

    const segment = (
        measurement: string,
        startBoundary: string,
        endBoundary: string,
    ): void => {
        const start = markTimes.get(startBoundary);
        const end = markTimes.get(endBoundary);

        if (start === undefined) {
            throw new Error(
                `Performance segment "${measurement}" references missing start boundary "${startBoundary}"`,
            );
        }

        if (end === undefined) {
            throw new Error(
                `Performance segment "${measurement}" references missing end boundary "${endBoundary}"`,
            );
        }

        if (end < start) {
            throw new Error(
                `Performance segment "${measurement}" ends before it starts`,
            );
        }

        segments.push({
            measurement,
            start_boundary: startBoundary,
            end_boundary: endBoundary,
            duration_ms: Math.round(end - start),
            measurement_layer: 'playwright_client',
        });
    };

    const finish = (): void => {
        const workflowEnd = performance.now();

        const summary: PerformanceSummary = {
            schema: 'playwright.performance-probe.v1',
            workflow,
            run_started_at: runStartedAt,
            measurement_layer: 'playwright_client',
            enabled: true,
            total_elapsed_ms: Math.round(
                workflowEnd - workflowStart,
            ),
            marks,
            segments,
        };

        console.log(
            `[PERF_SUMMARY] ${JSON.stringify(summary)}`,
        );
    };

    return {
        enabled,
        mark,
        segment,
        finish,
    };
}