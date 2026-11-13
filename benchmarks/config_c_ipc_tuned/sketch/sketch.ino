// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l.
// SPDX-License-Identifier: MPL-2.0

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define MAX_SAMPLES 10240
// Phase 5b tuned variant (DECISIONS.md D7): run setup()/loop() above the
// RouterBridge "bridge" thread (priority 5). Lower number = higher priority.
#define LOOP_PRIO_TUNED 4

struct PinEntry { const char* name; uint8_t pin; };

static const PinEntry kPins[] = {
  {"D21", D21}, {"D20", D20}, {"D13", D13}, {"D12", D12},
  {"D11", D11}, {"D10", D10}, {"D9",  D9 }, {"D8",  D8 },
  {"D7",  D7 }, {"D6",  D6 }, {"D5",  D5 }, {"D4",  D4 },
  {"D3",  D3 }, {"D2",  D2 }, {"D1",  D1 }, {"D0",  D0 },
  {"A0",  A0 }, {"A1",  A1 }, {"A2",  A2 }, {"A3",  A3 },
  {"A4",  A4 }, {"A5",  A5 },
  {"LED3_R", LED_BUILTIN}, {"LED3_G", LED_BUILTIN + 1}, {"LED3_B", LED_BUILTIN + 2},
  {"LED4_R", LED_BUILTIN + 3}, {"LED4_G", LED_BUILTIN + 4}, {"LED4_B", LED_BUILTIN + 5},
};

static inline int findIndex(const char* n) {
  for (size_t i = 0; i < sizeof(kPins)/sizeof(kPins[0]); ++i) {
    if (strcmp(kPins[i].name, n) == 0) return (int)i;
  }
  return -1;
}

void set_pin_by_name(String name, bool s) {
  int idx = findIndex(name.c_str());
  if (idx < 0) return;
  digitalWrite(kPins[idx].pin, s ? HIGH : LOW);
}

// Config C: Dual-Perspective DWT + Pin Actuation
volatile uint32_t g_dwt_timestamps[MAX_SAMPLES];
volatile bool g_sending = false;
volatile int g_pulses_to_send = 0;
volatile int g_pulses_sent = 0;
volatile uint32_t g_dwt_start = 0;
// Phase 5 IPC: latest-value-wins setpoint word = (seq << 8) | setpoint_pct.
// Written only by the bridge thread, read once per cycle by the loop.
// A single aligned 32-bit access is atomic on Cortex-M33, so no lock.
volatile uint32_t g_sp_word = 100u;          // seq 0, setpoint 100 %
volatile uint32_t g_applied[MAX_SAMPLES];    // g_sp_word as read in cycle k
volatile uint32_t g_actuator_setpoint = 100u;
volatile uint32_t g_rx_count = 0;
volatile int g_main_prio = -99;
volatile int g_bridge_prio = -99;

void init_dwt_cm33() {
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
#if defined(DWT_LAR_KEY)
  DWT->LAR = 0xC5ACCE55;
#elif defined(DWT)
  *((volatile uint32_t*)0xE0001FB0) = 0xC5ACCE55; // Cortex-M33 Lock Access Register
#endif
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

int check_dwt_status(int dummy) {
  (void)dummy;
  uint32_t c1 = DWT->CYCCNT;
  delayMicroseconds(50);
  uint32_t c2 = DWT->CYCCNT;
  if (c2 > c1) {
    return (int)(c2 - c1); // Returns cycles elapsed during 50 µs (~8,000 at 160 MHz)
  }
  return -1; // DWT failed or locked
}

int start_zephyr_pulses(int count) {
  if (count <= 0) count = 20;
  if (count > MAX_SAMPLES) count = MAX_SAMPLES;
  g_pulses_to_send = count;
  g_pulses_sent = 0;
  g_sending = true;
  return 1;
}

int get_sent_count(int dummy) {
  (void)dummy;
  return g_pulses_sent;
}

// Batch chunk retrieval: returns comma-separated DWT deltas from start (in microseconds or cycles)
String get_dwt_chunk(int start_idx) {
  if (start_idx < 0 || start_idx >= g_pulses_sent) return "";
  int end_idx = start_idx + 50;
  if (end_idx > g_pulses_sent) end_idx = g_pulses_sent;

  String chunk = "";
  for (int i = start_idx; i < end_idx; i++) {
    if (i > start_idx) chunk += ",";
    chunk += String(g_dwt_timestamps[i]);
  }
  return chunk;
}

int set_setpoint(int seq, int sp) {
  g_sp_word = (((uint32_t)seq & 0xFFFFFFu) << 8) | ((uint32_t)sp & 0xFFu);
  g_rx_count++;
  // k_sched_current_thread_query(), not k_current_get(): on this core k_current_get()
  // reads a thread-local variable whose C++ helper symbol the sketch loader cannot resolve.
  if (g_bridge_prio == -99) g_bridge_prio = k_thread_priority_get(k_sched_current_thread_query());
  return seq;
}

int reset_ipc(int dummy) {
  (void)dummy;
  g_sp_word = 100u;
  g_rx_count = 0;
  return 1;
}

int get_rx_count(int dummy) {
  (void)dummy;
  return (int)g_rx_count;
}

String get_thread_prios(int dummy) {
  (void)dummy;
  return String("main=") + String(g_main_prio) + ",bridge=" + String(g_bridge_prio);
}

String get_seq_chunk(int start_idx) {
  if (start_idx < 0 || start_idx >= g_pulses_sent) return "";
  int end_idx = start_idx + 50;
  if (end_idx > g_pulses_sent) end_idx = g_pulses_sent;

  String chunk = "";
  for (int i = start_idx; i < end_idx; i++) {
    if (i > start_idx) chunk += ",";
    chunk += String(g_applied[i]);
  }
  return chunk;
}

void setup()
{
  for (auto &e : kPins) pinMode(e.pin, OUTPUT);
  digitalWrite(D2, LOW);

  digitalWrite(LED_BUILTIN, HIGH);
  digitalWrite(LED_BUILTIN + 1, HIGH);
  digitalWrite(LED_BUILTIN + 2, HIGH);
  digitalWrite(LED_BUILTIN + 3, HIGH);
  digitalWrite(LED_BUILTIN + 4, HIGH);
  digitalWrite(LED_BUILTIN + 5, HIGH);

  init_dwt_cm33();
  g_main_prio = k_thread_priority_get(k_sched_current_thread_query());

  Bridge.begin();
  Bridge.provide("set_pin_by_name", set_pin_by_name);
  Bridge.provide("start_zephyr_pulses", start_zephyr_pulses);
  Bridge.provide("get_sent_count", get_sent_count);
  Bridge.provide("check_dwt_status", check_dwt_status);
  Bridge.provide("get_dwt_chunk", get_dwt_chunk);
  Bridge.provide("set_setpoint", set_setpoint);
  Bridge.provide("reset_ipc", reset_ipc);
  Bridge.provide("get_rx_count", get_rx_count);
  Bridge.provide("get_thread_prios", get_thread_prios);
  Bridge.provide("get_seq_chunk", get_seq_chunk);
  // Set last, so Bridge.begin()/provide() run exactly as in the stock sketch.
  k_thread_priority_set(k_sched_current_thread_query(), LOOP_PRIO_TUNED);
  g_main_prio = k_thread_priority_get(k_sched_current_thread_query());
}

void loop()
{
  Bridge.update();

  if (g_sending) {
    g_dwt_start = DWT->CYCCNT;
    uint32_t next_us = micros();

    while (g_sending && g_pulses_sent < g_pulses_to_send) {
      next_us += 10000; // Exact 10.00 ms (10,000 µs) period

      // 1. Capture instant DWT cycle timestamp
      uint32_t t_now_cyc = DWT->CYCCNT;
      g_dwt_timestamps[g_pulses_sent] = t_now_cyc;

      // 1b. IPC: latest-value-wins read of the setpoint (one 32-bit load)
      uint32_t sp_word = g_sp_word;
      g_applied[g_pulses_sent] = sp_word;
      g_actuator_setpoint = sp_word & 0xFFu;

      // 2. Physical pin actuation (500 µs active HIGH pulse)
      digitalWrite(D2, HIGH);
      delayMicroseconds(500);
      digitalWrite(D2, LOW);
      g_pulses_sent++;

      // 3. RTOS Yield / Sleep: if > 3 ms remaining, sleep 6 ms to yield to Zephyr
      int32_t rem_us = (int32_t)(next_us - micros());
      if (rem_us > 3000) {
        delay(6); // Calls k_sleep(6) -> CPU sleeps in WFI, yields to Zephyr scheduler
      }

      // 4. Final microsecond alignment spin
      while ((int32_t)(next_us - micros()) > 50) {
        delayMicroseconds(30);
      }
      while ((int32_t)(next_us - micros()) > 0) {
        // tight precision wait
      }
    }
    g_sending = false;
  }
}

