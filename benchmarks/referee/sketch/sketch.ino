#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define MAX_RECORDS 10000

volatile uint32_t g_pulse_count = 0;
volatile uint32_t g_last_pulse_cyc = 0;
volatile uint32_t g_deltas_us[MAX_RECORDS];
volatile uint32_t g_expected_count = 10000;
volatile bool g_recording = false;

void on_pulse_d2() {
    // Read 160 MHz hardware cycle counter directly to eliminate 26.84s micros() rollover artifact
    uint32_t now_cyc = k_cycle_get_32();
    if (!g_recording) {
        g_last_pulse_cyc = now_cyc;
        return;
    }
    
    // Unsigned 32-bit subtraction natively handles 2^32 cycle rollover
    uint32_t delta_cyc = now_cyc - g_last_pulse_cyc;
    g_last_pulse_cyc = now_cyc;
    
    // Convert 160 MHz cycles to microseconds
    uint32_t delta_us = delta_cyc / 160;
    
    if (g_pulse_count < MAX_RECORDS) {
        g_deltas_us[g_pulse_count++] = delta_us;
        if (g_pulse_count >= g_expected_count) {
            // Auto-stop immediately to re-enable Bridge.update() safely
            g_recording = false;
        }
    }
}

int rpc_start_capture(int expected_count) {
    g_expected_count = (expected_count > 0) ? (uint32_t)expected_count : 10000;
    g_pulse_count = 0;
    g_last_pulse_cyc = k_cycle_get_32();
    g_recording = true;
    return 1;
}

int rpc_stop_capture(int dummy) {
    (void)dummy;
    g_recording = false;
    return (int)g_pulse_count;
}

int rpc_get_count(int dummy) {
    (void)dummy;
    return (int)g_pulse_count;
}

int rpc_get_delta_at(int idx) {
    if (idx < 0 || idx >= (int)g_pulse_count) return -1;
    return (int)g_deltas_us[idx];
}

String rpc_get_deltas_chunk(int start_idx) {
    if (start_idx < 0 || start_idx >= (int)g_pulse_count) return "";
    int end_idx = start_idx + 50;
    if (end_idx > (int)g_pulse_count) end_idx = (int)g_pulse_count;
    
    String chunk = "";
    for (int i = start_idx; i < end_idx; i++) {
        if (i > start_idx) chunk += ",";
        chunk += String(g_deltas_us[i]);
    }
    return chunk;
}

void setup() {
    pinMode(D2, INPUT_PULLDOWN);
    attachInterrupt(digitalPinToInterrupt(D2), on_pulse_d2, RISING);
    NVIC_SetPriority(EXTI3_IRQn, 0); // Highest NVIC priority for zero ISR entry jitter
    
    Bridge.begin();
    Bridge.provide("start_capture", rpc_start_capture);
    Bridge.provide("stop_capture", rpc_stop_capture);
    Bridge.provide("get_count", rpc_get_count);
    Bridge.provide("get_delta_at", rpc_get_delta_at);
    Bridge.provide("get_deltas_chunk", rpc_get_deltas_chunk);
}

void loop() {
    // Suppress Bridge.update() during active pulse capture to eliminate serial irq_lock() noise!
    // Resume only after capture finishes or if pulse train has been idle for > 500 ms (timeout recovery)
    if (!g_recording) {
        Bridge.update();
    }
}
