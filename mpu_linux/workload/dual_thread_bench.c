/**
 * dual_thread_bench.c - Workload-Normalized Dual-Threaded Linux Benchmark
 * Course: CCU Operating Systems (Fall 2026) - Term Project
 * Author: Quang-Huy Nguyen (Lead) & Akash / An-Rui Peng
 *
 * Implements Option 2 (Dual-Threaded Asymmetric Decoupling):
 *   Thread 1 (Control Reflex):
 *     - Rigid 10.00 ms (100 Hz) periodic loop via clock_nanosleep(TIMER_ABSTIME).
 *     - Samples shared atomic setpoint, calculates absolute lateness L_k = t_k - R_k.
 *     - Buffered entirely in RAM (10,000 records). Zero in-loop file/UART I/O.
 *   Thread 2 (Cognitive Analytics):
 *     - Asynchronous ~85.33 ms cadence (1024 samples @ 12 kHz CWRU vibration signal).
 *     - Computes 1024-point FFT, evaluates spectrum LUT, updates shared setpoint.
 *
 * Supports Config A (Linux CFS) and Config B (Linux SCHED_FIFO priority 90).
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <sched.h>
#include <unistd.h>
#include <sys/resource.h>
#include <sys/mman.h>
#include <stdatomic.h>
#include <math.h>
#include "fft_math.h"

#define DEFAULT_CYCLES 10000

#define CONTROL_PERIOD_NS 10000000ULL       /* 10.00 ms in nanoseconds */
#define ANALYTICS_PERIOD_NS 85333333ULL     /* 85.33 ms in nanoseconds */
#define DEADLINE_TOLERANCE_MS 1.0           /* L_k > 1.0 ms is a Deadline Miss */
#define SEVERE_STARVATION_MS 40.0          /* L_k > 40.0 ms is Severe Starvation */
#define MAX_REPLAY_FRAMES 100

typedef struct {
    uint32_t cycle;
    uint64_t scheduled_ns;
    uint64_t actual_wake_ns;
    double lateness_ms;
    int is_miss;
    int is_starvation;
    int setpoint;
    long nivcsw;
    long minflt;
} cycle_record_t;

/* Global shared state */
static atomic_int g_current_setpoint = ATOMIC_VAR_INIT(100);
static atomic_bool g_benchmark_running = ATOMIC_VAR_INIT(true);
static cycle_record_t *g_records = NULL;
static uint32_t g_total_cycles = DEFAULT_CYCLES;

/* Replay test frames */
static float g_replay_frames[MAX_REPLAY_FRAMES][FFT_SIZE];
static int g_num_replay_frames = 0;

static uint64_t timespec_to_ns(const struct timespec *ts) {
    return (uint64_t)ts->tv_sec * 1000000000ULL + (uint64_t)ts->tv_nsec;
}

static struct timespec ns_to_timespec(uint64_t ns) {
    struct timespec ts;
    ts.tv_sec = (time_t)(ns / 1000000000ULL);
    ts.tv_nsec = (long)(ns % 1000000000ULL);
    return ts;
}

/**
 * Load pre-sliced binary vibration test frames from data/processed/cwru_test_frames.bin
 * Fallback to synthetic vibration signal if file is missing.
 */
static void load_or_generate_vibration_data(const char *bin_path) {
    FILE *f = fopen(bin_path, "rb");
    if (f) {
        size_t read_floats = fread(g_replay_frames, sizeof(float), MAX_REPLAY_FRAMES * FFT_SIZE, f);
        g_num_replay_frames = (int)(read_floats / FFT_SIZE);
        fclose(f);
        printf("[Data] Loaded %d real CWRU vibration frames (1024 floats each) from %s\n",
               g_num_replay_frames, bin_path);
        return;
    }

    printf("[Data] %s not found. Generating synthetic multi-harmonic vibration frames...\n", bin_path);
    g_num_replay_frames = 40;
    for (int frame = 0; frame < g_num_replay_frames; ++frame) {
        float f_fault = (frame % 4 == 0) ? 0.0f : (frame % 4 == 1) ? 135.0f : (frame % 4 == 2) ? 95.0f : 175.0f;
        for (int i = 0; i < FFT_SIZE; ++i) {
            float t = (float)i / 12000.0f;
            float sig = 0.05f * sinf(2.0f * (float)M_PI * 30.0f * t); /* 30 Hz shaft */
            if (f_fault > 0.0f) {
                sig += 0.35f * sinf(2.0f * (float)M_PI * f_fault * t); /* Injected fault tone */
            }
            g_replay_frames[frame][i] = sig;
        }
    }
}

/**
 * Thread 2: Cognitive Analytics Thread (~85.33 ms Cadence)
 * Runs decoupled on Linux, computes FFT, updates the atomic setpoint.
 */
static void *analytics_thread_func(void *arg) {
    (void)arg;
    struct timespec next_release;
    clock_gettime(CLOCK_MONOTONIC, &next_release);

    float windowed_input[FFT_SIZE];
    complex_float_t fft_buffer[FFT_SIZE];
    float spectrum[FFT_SIZE / 2];
    int frame_idx = 0;

    while (atomic_load(&g_benchmark_running)) {
        /* Advance next scheduled release by ~85.33 ms */
        uint64_t target_ns = timespec_to_ns(&next_release) + ANALYTICS_PERIOD_NS;
        next_release = ns_to_timespec(target_ns);

        /* 1. Fetch current 1024-sample vibration frame */
        const float *raw_frame = g_replay_frames[frame_idx % g_num_replay_frames];
        frame_idx++;

        /* 2. Apply Hanning window & compute 1024-point FFT */
        fft_apply_hanning(raw_frame, windowed_input);
        for (int i = 0; i < FFT_SIZE; ++i) {
            fft_buffer[i].real = windowed_input[i];
            fft_buffer[i].imag = 0.0f;
        }
        fft_compute_1024(fft_buffer);

        /* 3. Extract spectral peak */
        float peak_mag = 0.0f;
        float total_energy = 0.0f;
        int peak_bin = fft_extract_spectrum_and_peak(fft_buffer, spectrum, &peak_mag, &total_energy);

        /* 4. Deterministic PsM Rule Lookup Table (LUT) */
        int prescribed_setpoint = 100;
        if (peak_mag > 0.15f) {
            if (peak_bin >= 150) {
                prescribed_setpoint = 60; /* Outer race fault -> derate to 60% */
            } else if (peak_bin >= 115) {
                prescribed_setpoint = 70; /* Inner race fault -> derate to 70% */
            } else if (peak_bin >= 75) {
                prescribed_setpoint = 85; /* Ball fault -> derate to 85% */
            }
        }

        /* 5. Non-blocking latest-value-wins atomic update */
        atomic_store(&g_current_setpoint, prescribed_setpoint);

        /* Sleep until next frame schedule */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next_release, NULL);
    }

    return NULL;
}

/**
 * Thread 1: Control Reflex Loop (10.00 ms Strict Cadence)
 * Measures absolute wake-up lateness against scheduled release time.
 */
static void run_control_benchmark(void) {
    struct timespec start_ts;
    clock_gettime(CLOCK_MONOTONIC, &start_ts);
    uint64_t base_ns = timespec_to_ns(&start_ts);

    struct rusage usage_snap;
    getrusage(RUSAGE_SELF, &usage_snap);

    for (uint32_t k = 0; k < g_total_cycles; ++k) {
        /* Scheduled release time: R_k = t_0 + k * 10 ms */
        uint64_t scheduled_ns = base_ns + (uint64_t)k * CONTROL_PERIOD_NS;
        struct timespec sched_ts = ns_to_timespec(scheduled_ns);

        /* Rigid absolute timer sleep */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &sched_ts, NULL);

        /* Immediate wake-up timestamp */
        struct timespec wake_ts;
        clock_gettime(CLOCK_MONOTONIC, &wake_ts);
        uint64_t actual_wake_ns = timespec_to_ns(&wake_ts);

        /* Minimal work: read local atomic variable */
        int sp = atomic_load(&g_current_setpoint);

        /* Absolute wake-up lateness L_k = t_k - R_k */
        int64_t lateness_ns = (int64_t)actual_wake_ns - (int64_t)scheduled_ns;
        double lateness_ms = (double)lateness_ns / 1000000.0;

        /* Check deadline and starvation flags */
        int is_miss = (lateness_ms > DEADLINE_TOLERANCE_MS) ? 1 : 0;
        int is_starvation = (lateness_ms > SEVERE_STARVATION_MS) ? 1 : 0;

        /* Periodic telemetry snapshot (every 500 cycles to avoid getrusage overhead) */
        if (k % 500 == 0) {
            getrusage(RUSAGE_SELF, &usage_snap);
        }

        /* Buffer directly into RAM */
        g_records[k].cycle = k;
        g_records[k].scheduled_ns = scheduled_ns;
        g_records[k].actual_wake_ns = actual_wake_ns;
        g_records[k].lateness_ms = lateness_ms;
        g_records[k].is_miss = is_miss;
        g_records[k].is_starvation = is_starvation;
        g_records[k].setpoint = sp;
        g_records[k].nivcsw = usage_snap.ru_nivcsw;
        g_records[k].minflt = usage_snap.ru_minflt;
    }

    /* Signal analytics thread to terminate */
    atomic_store(&g_benchmark_running, false);
}

static int compare_doubles(const void *a, const void *b) {
    double da = *(const double *)a;
    double db = *(const double *)b;
    if (da < db) return -1;
    if (da > db) return 1;
    return 0;
}

static void print_summary_and_save_csv(const char *config_str,
                                       const char *policy_name,
                                       int stress_level,
                                       const char *csv_output_path,
                                       const struct rusage *ru_start,
                                       const struct rusage *ru_end) {
    uint32_t total_misses = 0;
    uint32_t total_starvations = 0;
    double sum_lateness = 0.0;
    double max_lateness = -1e9;
    double min_lateness = 1e9;

    double *sorted_lateness = malloc(g_total_cycles * sizeof(double));

    for (uint32_t i = 0; i < g_total_cycles; ++i) {
        double l = g_records[i].lateness_ms;
        sorted_lateness[i] = l;
        sum_lateness += l;
        if (l > max_lateness) max_lateness = l;
        if (l < min_lateness) min_lateness = l;
        if (g_records[i].is_miss) total_misses++;
        if (g_records[i].is_starvation) total_starvations++;
    }

    double avg_lateness = sum_lateness / (double)g_total_cycles;

    /* Jitter standard deviation */
    double var_sum = 0.0;
    for (uint32_t i = 0; i < g_total_cycles; ++i) {
        double diff = g_records[i].lateness_ms - avg_lateness;
        var_sum += diff * diff;
    }
    double jitter_std_dev = sqrt(var_sum / (double)g_total_cycles);

    /* 99.9th percentile lateness */
    qsort(sorted_lateness, g_total_cycles, sizeof(double), compare_doubles);
    uint32_t idx_999 = (uint32_t)((double)g_total_cycles * 0.999);
    if (idx_999 >= g_total_cycles) idx_999 = g_total_cycles - 1;
    double p999_lateness = sorted_lateness[idx_999];
    free(sorted_lateness);

    double dmr_percent = ((double)total_misses / (double)g_total_cycles) * 100.0;

    long d_nivcsw = ru_end->ru_nivcsw - ru_start->ru_nivcsw;
    long d_nvcsw  = ru_end->ru_nvcsw  - ru_start->ru_nvcsw;
    long d_minflt = ru_end->ru_minflt - ru_start->ru_minflt;
    long d_majflt = ru_end->ru_majflt - ru_start->ru_majflt;

    printf("\n======================================================================\n");
    printf(" BENCHMARK REPORT: Config %s (%s) | Stress: %d%% | %u Cycles\n",
           config_str, policy_name, stress_level, g_total_cycles);
    printf("======================================================================\n");
    printf("  Nominal Cycle Period (T_nom):     10.00 ms (100 Hz)\n");
    printf("  Deadline Miss Tolerance:          L_k > %.2f ms\n", DEADLINE_TOLERANCE_MS);
    printf("----------------------------------------------------------------------\n");
    printf("  Average Lateness (L_avg):          %.4f ms\n", avg_lateness);
    printf("  Minimum Lateness (L_min):          %.4f ms\n", min_lateness);
    printf("  Worst-Case Lateness (WCL max):     %.4f ms\n", max_lateness);
    printf("  Tail Lateness (P99.9):             %.4f ms\n", p999_lateness);
    printf("  Timing Jitter (Std Dev sigma_L):   %.4f ms\n", jitter_std_dev);
    printf("  Deadline Miss Count:               %u / %u\n", total_misses, g_total_cycles);
    printf("  Deadline Miss Ratio (DMR):         %.3f %%\n", dmr_percent);
    printf("  Severe Starvations (L_k > 40ms):   %u\n", total_starvations);
    printf("----------------------------------------------------------------------\n");
    printf("  Kernel Telemetry Summary:\n");
    printf("    Involuntary Context Switches:    %ld (ru_nivcsw)\n", d_nivcsw);
    printf("    Voluntary Context Switches:      %ld (ru_nvcsw)\n", d_nvcsw);
    printf("    Minor Page Faults:               %ld (ru_minflt)\n", d_minflt);
    printf("    Major Page Faults:               %ld (ru_majflt)\n", d_majflt);
    printf("======================================================================\n");

    /* Export full records to CSV */
    FILE *f = fopen(csv_output_path, "w");
    if (!f) {
        fprintf(stderr, "Error opening CSV output file %s for writing\n", csv_output_path);
        return;
    }

    fprintf(f, "cycle,scheduled_ns,actual_wake_ns,lateness_ms,is_miss,is_starvation,setpoint,nivcsw,minflt\n");
    for (uint32_t i = 0; i < g_total_cycles; ++i) {
        fprintf(f, "%u,%llu,%llu,%.4f,%d,%d,%d,%ld,%ld\n",
                g_records[i].cycle,
                (unsigned long long)g_records[i].scheduled_ns,
                (unsigned long long)g_records[i].actual_wake_ns,
                g_records[i].lateness_ms,
                g_records[i].is_miss,
                g_records[i].is_starvation,
                g_records[i].setpoint,
                g_records[i].nivcsw,
                g_records[i].minflt);
    }
    fclose(f);
    printf("[Output] Full cycle telemetry saved to: %s\n\n", csv_output_path);
}

int main(int argc, char **argv) {
    const char *config_str = "A";  /* "A" (CFS) or "B" (SCHED_FIFO) */
    const char *policy_str = NULL; /* "FIFO", "RR", "OTHER" */
    int rt_priority = 90;
    bool enable_mlock = false;
    int affinity_core = -1;        /* -1 means floating */
    int stress_level = 0;          /* 0, 50, or 100 */
    char csv_path[512] = {0};
    const char *data_bin_path = "data/processed/cwru_test_frames.bin";

    /* Parse command-line flags */
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            config_str = argv[++i];
        } else if (strcmp(argv[i], "--policy") == 0 && i + 1 < argc) {
            policy_str = argv[++i];
        } else if (strcmp(argv[i], "--priority") == 0 && i + 1 < argc) {
            rt_priority = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--mlock") == 0) {
            enable_mlock = true;
        } else if (strcmp(argv[i], "--affinity") == 0 && i + 1 < argc) {
            affinity_core = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--cycles") == 0 && i + 1 < argc) {
            g_total_cycles = (uint32_t)atoi(argv[++i]);
        } else if (strcmp(argv[i], "--stress") == 0 && i + 1 < argc) {
            stress_level = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            strncpy(csv_path, argv[++i], sizeof(csv_path) - 1);
        } else if (strcmp(argv[i], "--data") == 0 && i + 1 < argc) {
            data_bin_path = argv[++i];
        } else if (strcmp(argv[i], "--help") == 0) {
            printf("Usage: %s [OPTIONS]\n", argv[0]);
            printf("  --config A|B         Baseline config: A (CFS) or B (SCHED_FIFO)\n");
            printf("  --policy FIFO|RR     Explicit RT scheduling policy override\n");
            printf("  --priority 1-99      Real-time priority (default: 90)\n");
            printf("  --mlock              Lock all virtual pages into physical RAM (mlockall)\n");
            printf("  --affinity 0-3       Pin process to a specific CPU core\n");
            printf("  --cycles N           Number of 10 ms cycles (default: 10000)\n");
            printf("  --stress 0|50|100    Metadata label for stress condition\n");
            printf("  --out file.csv       Output CSV path\n");
            printf("  --data file.bin      Input binary vibration frames\n");
            return 0;
        }
    }

    /* Resolve effective scheduling policy */
    int target_policy = SCHED_OTHER;
    int target_prio = 0;
    const char *policy_name = "CFS (SCHED_OTHER)";

    if (policy_str != NULL) {
        if (strcasecmp(policy_str, "FIFO") == 0) {
            target_policy = SCHED_FIFO;
            target_prio = rt_priority;
            policy_name = "SCHED_FIFO";
        } else if (strcasecmp(policy_str, "RR") == 0) {
            target_policy = SCHED_RR;
            target_prio = rt_priority;
            policy_name = "SCHED_RR";
        } else {
            target_policy = SCHED_OTHER;
            target_prio = 0;
            policy_name = "CFS (SCHED_OTHER)";
        }
    } else {
        if (strcasecmp(config_str, "B") == 0) {
            target_policy = SCHED_FIFO;
            target_prio = rt_priority;
            policy_name = "SCHED_FIFO";
        } else {
            target_policy = SCHED_OTHER;
            target_prio = 0;
            policy_name = "CFS (SCHED_OTHER)";
        }
    }

    if (strlen(csv_path) == 0) {
        snprintf(csv_path, sizeof(csv_path), "results/raw/config_%s_stress_%d.csv", config_str, stress_level);
    }

    printf("======================================================================\n");
    printf(" Initializing Dual-Threaded Linux PsM Benchmark\n");
    printf(" Target: Config %s (%s, Prio %d) | Stress: %d%% | Total Cycles: %u (%.1f s)\n",
           config_str, policy_name, target_prio, stress_level, g_total_cycles, (double)g_total_cycles * 0.01);
    printf(" Memory Lock (mlockall): %s | CPU Affinity: %s\n",
           enable_mlock ? "ENABLED" : "DISABLED",
           (affinity_core >= 0) ? "Core Pinning" : "Floating");
    printf("======================================================================\n");

    /* Apply CPU Affinity if requested */
    if (affinity_core >= 0) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        CPU_SET(affinity_core, &cpuset);
        if (sched_setaffinity(0, sizeof(cpu_set_t), &cpuset) != 0) {
            perror("[Warning] sched_setaffinity failed");
        } else {
            printf("[Affinity] Process pinned strictly to CPU core %d\n", affinity_core);
        }
    } else {
        printf("[Affinity] Floating dynamically across all CPU cores\n");
    }

    /* Apply Virtual Memory Locking if requested */
    if (enable_mlock) {
        if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
            perror("[Warning] mlockall(MCL_CURRENT | MCL_FUTURE) failed. Run with sudo!");
        } else {
            printf("[Memory] Address space locked into physical RAM (zero page faults)\n");
        }
    }

    /* Allocate in-memory RAM buffer */
    g_records = malloc(g_total_cycles * sizeof(cycle_record_t));
    if (!g_records) {
        fprintf(stderr, "Fatal: Failed to allocate RAM buffer for %u records\n", g_total_cycles);
        return 1;
    }

    /* Prefault buffer memory if mlock was requested */
    if (enable_mlock) {
        memset(g_records, 0, g_total_cycles * sizeof(cycle_record_t));
    }

    fft_init();
    load_or_generate_vibration_data(data_bin_path);

    /* Elevate Thread 1 scheduler if RT policy selected */
    if (target_policy != SCHED_OTHER) {
        struct sched_param param;
        param.sched_priority = target_prio;
        if (sched_setscheduler(0, target_policy, &param) != 0) {
            perror("[Warning] sched_setscheduler failed. Please run with 'sudo'");
        } else {
            printf("[Scheduler] Successfully elevated process to %s (Priority %d)\n", policy_name, target_prio);
        }
    } else {
        printf("[Scheduler] Running under standard Linux CFS (SCHED_OTHER)\n");
    }

    /* Start Thread 2 (Analytics loop) */
    pthread_t analytics_tid;
    pthread_attr_t attr;
    pthread_attr_init(&attr);

    /* Explicitly prevent Thread 2 from inheriting RT priority: force CFS */
    pthread_attr_setinheritsched(&attr, PTHREAD_EXPLICIT_SCHED);
    struct sched_param analytics_param;
    analytics_param.sched_priority = 0;
    pthread_attr_setschedpolicy(&attr, SCHED_OTHER);
    pthread_attr_setschedparam(&attr, &analytics_param);

    if (pthread_create(&analytics_tid, &attr, analytics_thread_func, NULL) != 0) {
        perror("Failed to create analytics thread");
        free(g_records);
        return 1;
    }
    pthread_attr_destroy(&attr);

    /* Measure initial kernel telemetry */
    struct rusage ru_start, ru_end;
    getrusage(RUSAGE_SELF, &ru_start);

    printf("[Benchmark] Starting 10 ms real-time timing loop on Main Thread...\n");
    run_control_benchmark();

    /* Wait for analytics thread to finish clean-up */
    pthread_join(analytics_tid, NULL);
    getrusage(RUSAGE_SELF, &ru_end);

    /* Compute and print results, flush CSV */
    print_summary_and_save_csv(config_str, policy_name, stress_level, csv_path, &ru_start, &ru_end);

    free(g_records);
    return 0;
}
