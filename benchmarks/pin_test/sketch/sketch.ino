// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l.
// SPDX-License-Identifier: MPL-2.0

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define MAX_SAMPLES 10240

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

  Bridge.begin();
  Bridge.provide("set_pin_by_name", set_pin_by_name);
  Bridge.provide("start_zephyr_pulses", start_zephyr_pulses);
  Bridge.provide("get_sent_count", get_sent_count);
  Bridge.provide("check_dwt_status", check_dwt_status);
  Bridge.provide("get_dwt_chunk", get_dwt_chunk);
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
