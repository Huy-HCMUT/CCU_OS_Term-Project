// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l.
// SPDX-License-Identifier: MPL-2.0

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

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

String test_clock_ratio_busy(int ms) {
  if (ms <= 0) ms = 100;
  uint32_t target_us = (uint32_t)ms * 1000;
  uint32_t d1 = DWT->CYCCNT;
  uint32_t k1 = k_cycle_get_32();
  uint32_t u1 = micros();
  while ((micros() - u1) < target_us) {
    // busy wait
  }
  uint32_t d2 = DWT->CYCCNT;
  uint32_t k2 = k_cycle_get_32();
  uint32_t u2 = micros();
  return String(d2 - d1) + "," + String(k2 - k1) + "," + String(u2 - u1);
}

String test_clock_ratio_sleep(int ms) {
  if (ms <= 0) ms = 100;
  uint32_t d1 = DWT->CYCCNT;
  uint32_t k1 = k_cycle_get_32();
  uint32_t u1 = micros();
  delay(ms);
  uint32_t d2 = DWT->CYCCNT;
  uint32_t k2 = k_cycle_get_32();
  uint32_t u2 = micros();
  return String(d2 - d1) + "," + String(k2 - k1) + "," + String(u2 - u1);
}

// Test 50 cycles of 10,000 µs loop with and without sleep
String test_loop_sleep_vs_spin(int with_sleep) {
  uint32_t next_us = micros();
  uint32_t d_start = DWT->CYCCNT;
  uint32_t k_start = k_cycle_get_32();
  uint32_t u_start = micros();

  for (int i = 0; i < 50; i++) {
    next_us += 10000;

    if (with_sleep) {
      int32_t rem_us = (int32_t)(next_us - micros());
      if (rem_us > 3000) {
        delay(6);
      }
    }

    while ((int32_t)(next_us - micros()) > 0) {
      // spin
    }
  }

  uint32_t d_end = DWT->CYCCNT;
  uint32_t k_end = k_cycle_get_32();
  uint32_t u_end = micros();

  return String(d_end - d_start) + "," + String(k_end - k_start) + "," + String(u_end - u_start);
}

void setup() {
  init_dwt_cm33();

  Bridge.begin();
  Bridge.provide("check_dwt_status", check_dwt_status);
  Bridge.provide("test_clock_ratio_busy", test_clock_ratio_busy);
  Bridge.provide("test_clock_ratio_sleep", test_clock_ratio_sleep);
  Bridge.provide("test_loop_sleep_vs_spin", test_loop_sleep_vs_spin);
}

void loop() {
  Bridge.update();
}
