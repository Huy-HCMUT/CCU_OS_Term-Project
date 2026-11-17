// Phase 6b drive emulator (board 3). Inputs only (D2 tick + D8 PWM).
// Measures tick intervals and detects duty changes on D8 using DWT->CYCCNT (160 MHz).

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define NOMINAL_PERIOD_CYC 320000u  // 2 ms at 160 MHz
#define PERIOD_TOL_CYC     3200u    // +-1 %
#define CHANGE_CYC         3200u    // +-1 % of 2 ms period = 20 us high-time delta threshold
#define EV_MAX             1024

volatile bool     g_recording = false;
volatile uint32_t g_ticks = 0;
volatile uint32_t g_last_tick = 0;
volatile uint32_t g_tick_min = 0xFFFFFFFFu;
volatile uint32_t g_tick_max = 0;
volatile uint32_t g_last_tick_ms = 0;

volatile uint32_t g_have_lvl = 0;
volatile uint32_t g_last_lvl = 0;
volatile uint32_t g_have_rise = 0;
volatile uint32_t g_last_rise = 0;
volatile uint32_t g_last_period = 0;
volatile uint32_t g_have_prev_high = 0;
volatile uint32_t g_prev_high = 0;

volatile uint32_t g_np = 0;
volatile uint32_t g_pout = 0;
volatile uint32_t g_level_errors = 0;
volatile uint32_t g_initial_high = 0;

volatile int32_t  g_ev_tick_idx[EV_MAX];
volatile uint32_t g_ev_tick_cyc[EV_MAX];
volatile uint32_t g_ev_rise[EV_MAX];
volatile uint32_t g_ev_fall[EV_MAX];
volatile uint32_t g_ev_high[EV_MAX];
volatile uint32_t g_ev_period[EV_MAX];
volatile uint32_t g_ev_n = 0;
volatile uint32_t g_ev_dropped = 0;

void init_dwt_cm33() {
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
#if defined(DWT_LAR_KEY)
  DWT->LAR = 0xC5ACCE55;
#elif defined(DWT)
  *((volatile uint32_t*)0xE0001FB0) = 0xC5ACCE55; // Cortex-M33 Lock Access Register
#endif
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

void on_tick() {
  uint32_t now = DWT->CYCCNT;
  if (!g_recording) return;
  if (g_ticks > 0) {
    uint32_t dt = now - g_last_tick;
    if (dt < g_tick_min) g_tick_min = dt;
    if (dt > g_tick_max) g_tick_max = dt;
  }
  g_last_tick = now;
  g_ticks++;
  g_last_tick_ms = millis();
}

void on_pwm_edge() {
  uint32_t now = DWT->CYCCNT;
  uint32_t lvl = digitalRead(D8) ? 1u : 0u;
  if (g_have_lvl && lvl == g_last_lvl) {
    if (g_recording) g_level_errors++;
  }
  g_last_lvl = lvl;
  g_have_lvl = 1;

  if (lvl) {
    if (g_have_rise) {
      uint32_t p = now - g_last_rise;
      if (g_recording) {
        g_np++;
        if (p + PERIOD_TOL_CYC < NOMINAL_PERIOD_CYC || p > NOMINAL_PERIOD_CYC + PERIOD_TOL_CYC) {
          g_pout++;
        }
      }
      g_last_period = p;
    }
    g_last_rise = now;
    g_have_rise = 1;
  } else if (g_have_rise) {
    uint32_t h = now - g_last_rise;
    if (g_have_prev_high) {
      uint32_t dh = (h > g_prev_high) ? (h - g_prev_high) : (g_prev_high - h);
      if (g_recording && dh > CHANGE_CYC && g_last_period > 0u) {
        if (g_ev_n < EV_MAX) {
          uint32_t idx = g_ev_n;
          g_ev_tick_idx[idx] = (int32_t)g_ticks - 1;
          g_ev_tick_cyc[idx] = g_last_tick;
          g_ev_rise[idx]     = g_last_rise;
          g_ev_fall[idx]     = now;
          g_ev_high[idx]     = h;
          g_ev_period[idx]   = g_last_period;
          g_ev_n = idx + 1u;
        } else {
          g_ev_dropped++;
        }
      }
    }
    g_prev_high = h;
    g_have_prev_high = 1;
  }
}

int start_capture(int dummy) {
  (void)dummy;
  g_recording = false;
  g_ticks = 0;
  g_last_tick = 0;
  g_tick_min = 0xFFFFFFFFu;
  g_tick_max = 0;
  g_np = 0;
  g_pout = 0;
  g_level_errors = 0;
  g_ev_n = 0;
  g_ev_dropped = 0;
  g_initial_high = g_prev_high;
  g_last_tick_ms = millis();
  g_recording = true;
  return 1;
}

int stop_capture(int dummy) {
  (void)dummy;
  g_recording = false;
  return (int)g_ev_n;
}

String get_info(int dummy) {
  (void)dummy;
  return String(g_ticks) + "," + String(g_tick_min) + "," + String(g_tick_max) + "," +
         String(g_np) + "," + String(g_pout) + "," + String(g_level_errors) + "," +
         String(g_initial_high) + "," + String(g_ev_n) + "," + String(g_ev_dropped);
}

String get_events_chunk(int start_value) {
  int total = (int)g_ev_n * 6;
  if (start_value < 0 || start_value >= total || (start_value % 6) != 0) return "";
  int end_value = start_value + 48;
  if (end_value > total) end_value = total;
  String s = "";
  for (int v = start_value; v < end_value; v++) {
    int i = v / 6;
    int f = v % 6;
    if (v > start_value) s += ",";
    if (f == 0) {
      s += String((int32_t)g_ev_tick_idx[i]);
    } else {
      uint32_t x = (f == 1) ? g_ev_tick_cyc[i]
                 : (f == 2) ? g_ev_rise[i]
                 : (f == 3) ? g_ev_fall[i]
                 : (f == 4) ? g_ev_high[i]
                            : g_ev_period[i];
      s += String(x);
    }
  }
  return s;
}

void setup() {
  init_dwt_cm33();
  pinMode(D2, INPUT_PULLDOWN);
  pinMode(D8, INPUT_PULLDOWN);
  attachInterrupt(digitalPinToInterrupt(D2), on_tick, RISING);
  attachInterrupt(digitalPinToInterrupt(D8), on_pwm_edge, CHANGE);
  NVIC_SetPriority(EXTI3_IRQn, 0);
  NVIC_SetPriority(EXTI4_IRQn, 0);

  Bridge.begin();
  Bridge.provide("start_capture", start_capture);
  Bridge.provide("stop_capture", stop_capture);
  Bridge.provide("get_info", get_info);
  Bridge.provide("get_events_chunk", get_events_chunk);
}

void loop() {
  if (g_recording && g_ticks > 0) {
    uint32_t last = g_last_tick_ms;
    uint32_t now = millis();
    if (now > last && (now - last) > 2000u) {
      g_recording = false;
    }
  }
  if (!g_recording) {
    Bridge.update();
  }
}

