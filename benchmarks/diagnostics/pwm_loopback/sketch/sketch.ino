// PWM loopback diagnostic (Phase 6b, test 1). Runs on board 3 only.
// Wiring: ONE jumper on the same board, D3 -> D8. Nothing else connected.
//   D3 = PWM output (TIM3_CH3, 500 Hz fixed by the core's devicetree; duty via analogWrite)
//   D8 = input (PB4, EXTI4), timestamps both edges with the DWT cycle counter (160 MHz)
// Questions answered:
//   1. Period and duty of the PWM at 80 % and 48 % (steady captures).
//   2. Missed edges over a long capture (level repeats, period outliers).
//   3. Delay from analogWrite() to the first PWM period carrying the new duty (switch test).
//   4. Duration of one analogWrite() call (DWT around the call).
// Not for measurements of the DUT; core version on board 3 may differ from the DUT.

#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define PIN_OUT D3
#define PIN_IN  D8
#define RAW_MAX 2000
#define SW_MAX  512
#define NOMINAL_PERIOD_CYC 320000u  // 2 ms at 160 MHz
#define PERIOD_TOL_CYC     3200u    // +-1 %
#define RAW_CHUNK 30
#define SW_CHUNK  8

enum { MODE_IDLE = 0, MODE_CAPTURE = 1, MODE_SWITCH = 2 };
enum { CMD_NONE = 0, CMD_CAPTURE = 1, CMD_SWITCH = 2 };

// ---- edge capture state (written by the ISR) ----
volatile uint32_t g_mode = MODE_IDLE;
volatile uint32_t g_raw_t[RAW_MAX];
volatile uint8_t  g_raw_lvl[RAW_MAX];
volatile uint32_t g_raw_n = 0;
volatile uint32_t g_edges = 0;
volatile uint32_t g_level_errors = 0;
volatile uint32_t g_have_lvl = 0;
volatile uint32_t g_last_lvl = 0;
volatile uint32_t g_have_rise = 0;
volatile uint32_t g_last_rise = 0;
volatile uint32_t g_last_period = 0;
volatile uint32_t g_np = 0, g_pmin = 0xFFFFFFFFu, g_pmax = 0, g_pout = 0;
volatile uint64_t g_psum = 0;
volatile uint32_t g_nh = 0, g_hmin = 0xFFFFFFFFu, g_hmax = 0;
volatile uint64_t g_hsum = 0;

// ---- switch test state ----
volatile uint32_t g_sw_pending = 0;
volatile uint32_t g_sw_target_hi = 0;
volatile uint32_t g_sw_i = 0;
volatile uint32_t g_sw_target[SW_MAX];
volatile uint32_t g_sw_call[SW_MAX];
volatile uint32_t g_sw_cost[SW_MAX];
volatile uint32_t g_sw_rise[SW_MAX];
volatile uint32_t g_sw_fall[SW_MAX];
volatile uint32_t g_sw_high[SW_MAX];
volatile uint32_t g_sw_done = 0;
volatile uint32_t g_sw_timeouts = 0;

// ---- command handoff (RPC -> loop) ----
volatile uint32_t g_cmd = CMD_NONE;
volatile uint32_t g_busy = 0;
volatile uint32_t g_arg_permille = 800;
volatile uint32_t g_arg_seconds = 10;
volatile uint32_t g_arg_n = 200;
volatile uint32_t g_cur_permille = 800;

void init_dwt_cm33() {
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
#if defined(DWT_LAR_KEY)
  DWT->LAR = 0xC5ACCE55;
#elif defined(DWT)
  *((volatile uint32_t*)0xE0001FB0) = 0xC5ACCE55; // Cortex-M33 Lock Access Register
#endif
  DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static inline int duty_value(uint32_t permille) {
  // analogWriteResolution(16): 0..65535 maps to 0..period
  return (int)((permille * 65535u + 500u) / 1000u);
}

void reset_stats() {
  g_raw_n = 0; g_edges = 0; g_level_errors = 0;
  g_have_lvl = 0; g_have_rise = 0; g_last_period = 0;
  g_np = 0; g_pmin = 0xFFFFFFFFu; g_pmax = 0; g_pout = 0; g_psum = 0;
  g_nh = 0; g_hmin = 0xFFFFFFFFu; g_hmax = 0; g_hsum = 0;
}

void on_edge() {
  uint32_t now = DWT->CYCCNT;            // timestamp first
  uint32_t lvl = digitalRead(PIN_IN) ? 1u : 0u;
  if (g_mode == MODE_IDLE) return;
  g_edges++;
  if (g_have_lvl && lvl == g_last_lvl) g_level_errors++;  // two edges of the same kind = one missed
  g_last_lvl = lvl; g_have_lvl = 1;
  if (g_raw_n < RAW_MAX) { g_raw_t[g_raw_n] = now; g_raw_lvl[g_raw_n] = (uint8_t)lvl; g_raw_n++; }

  if (lvl) {  // rising edge: a period ends, a new one starts
    if (g_have_rise) {
      uint32_t p = now - g_last_rise;
      g_np++; g_psum += p;
      if (p < g_pmin) g_pmin = p;
      if (p > g_pmax) g_pmax = p;
      if (p + PERIOD_TOL_CYC < NOMINAL_PERIOD_CYC || p > NOMINAL_PERIOD_CYC + PERIOD_TOL_CYC) g_pout++;
      g_last_period = p;
    }
    g_last_rise = now; g_have_rise = 1;
  } else if (g_have_rise) {  // falling edge: high time of the current period is known
    uint32_t h = now - g_last_rise;
    g_nh++; g_hsum += h;
    if (h < g_hmin) g_hmin = h;
    if (h > g_hmax) g_hmax = h;
    if (g_mode == MODE_SWITCH && g_sw_pending && g_last_period) {
      // classify against 64 % of the last period (midpoint of 48 % and 80 %)
      uint32_t thr = (uint32_t)(((uint64_t)g_last_period * 640u) / 1000u);
      uint32_t is_hi = (h > thr) ? 1u : 0u;
      if (is_hi == g_sw_target_hi) {
        uint32_t i = g_sw_i;
        g_sw_rise[i] = g_last_rise;
        g_sw_fall[i] = now;
        g_sw_high[i] = h;
        g_sw_pending = 0;
      }
    }
  }
}

// ---------------- RPCs ----------------
int check_dwt_status(int dummy) {
  (void)dummy;
  uint32_t c1 = DWT->CYCCNT;
  delayMicroseconds(50);
  uint32_t c2 = DWT->CYCCNT;
  return (c2 > c1) ? (int)(c2 - c1) : -1;
}

int start_capture(int permille, int seconds) {
  if (g_busy || g_cmd != CMD_NONE) return -1;
  if (permille < 50 || permille > 950 || seconds < 1 || seconds > 600) return -2;
  g_arg_permille = (uint32_t)permille;
  g_arg_seconds = (uint32_t)seconds;
  g_cmd = CMD_CAPTURE;
  return 1;
}

int start_switch(int n) {
  if (g_busy || g_cmd != CMD_NONE) return -1;
  if (n < 1 || n > SW_MAX) return -2;
  g_arg_n = (uint32_t)n;
  g_cmd = CMD_SWITCH;
  return 1;
}

int get_state(int dummy) {
  (void)dummy;
  return (g_busy || g_cmd != CMD_NONE) ? 1 : 0;
}

// edges,level_errors,np,pmin,pmax,psum_hi,psum_lo,pout,nh,hmin,hmax,hsum_hi,hsum_lo,raw_n
String get_capture_summary(int dummy) {
  (void)dummy;
  uint64_t ps = g_psum, hs = g_hsum;
  String s = String(g_edges) + "," + String(g_level_errors) + "," + String(g_np) + "," +
             String(g_pmin) + "," + String(g_pmax) + "," +
             String((uint32_t)(ps >> 32)) + "," + String((uint32_t)(ps & 0xFFFFFFFFu)) + "," +
             String(g_pout) + "," + String(g_nh) + "," + String(g_hmin) + "," + String(g_hmax) + "," +
             String((uint32_t)(hs >> 32)) + "," + String((uint32_t)(hs & 0xFFFFFFFFu)) + "," +
             String(g_raw_n);
  return s;
}

// "t,l;t,l;..." for up to RAW_CHUNK edges starting at start_idx
String get_raw_chunk(int start_idx) {
  if (start_idx < 0 || start_idx >= (int)g_raw_n) return "";
  int end_idx = start_idx + RAW_CHUNK;
  if (end_idx > (int)g_raw_n) end_idx = (int)g_raw_n;
  String s = "";
  for (int i = start_idx; i < end_idx; i++) {
    if (i > start_idx) s += ";";
    s += String(g_raw_t[i]) + "," + String((uint32_t)g_raw_lvl[i]);
  }
  return s;
}

// n_done,timeouts
String get_switch_info(int dummy) {
  (void)dummy;
  return String(g_sw_done) + "," + String(g_sw_timeouts);
}

// "target,call,cost,rise,fall,high;..." for up to SW_CHUNK switches starting at start_idx
String get_switch_chunk(int start_idx) {
  if (start_idx < 0 || start_idx >= (int)g_sw_done) return "";
  int end_idx = start_idx + SW_CHUNK;
  if (end_idx > (int)g_sw_done) end_idx = (int)g_sw_done;
  String s = "";
  for (int i = start_idx; i < end_idx; i++) {
    if (i > start_idx) s += ";";
    s += String(g_sw_target[i]) + "," + String(g_sw_call[i]) + "," + String(g_sw_cost[i]) + "," +
         String(g_sw_rise[i]) + "," + String(g_sw_fall[i]) + "," + String(g_sw_high[i]);
  }
  return s;
}

// ---------------- tests (run in loop) ----------------
void run_capture() {
  uint32_t permille = g_arg_permille;
  analogWrite(PIN_OUT, duty_value(permille));
  g_cur_permille = permille;
  delay(50);                       // let the new duty settle
  reset_stats();
  g_mode = MODE_CAPTURE;
  delay(g_arg_seconds * 1000u);
  g_mode = MODE_IDLE;
}

void run_switch() {
  uint32_t n = g_arg_n;
  analogWrite(PIN_OUT, duty_value(800));   // start from a steady 80 %
  g_cur_permille = 800;
  delay(100);
  reset_stats();
  g_sw_done = 0; g_sw_timeouts = 0; g_sw_pending = 0;
  g_mode = MODE_SWITCH;
  uint32_t lcg = 12345u;
  for (uint32_t i = 0; i < n; i++) {
    lcg = lcg * 1664525u + 1013904223u;
    delay(20u + ((lcg >> 16) % 21u));               // 20-40 ms: >= 10 PWM periods settle
    lcg = lcg * 1664525u + 1013904223u;
    delayMicroseconds((lcg >> 16) % 2000u);          // random phase within one PWM period
    uint32_t target = (i % 2u == 0u) ? 480u : 800u;  // alternate 80 % -> 48 % -> 80 % ...
    g_sw_target[i] = target;
    g_sw_rise[i] = 0; g_sw_fall[i] = 0; g_sw_high[i] = 0;
    g_sw_i = i;
    g_sw_target_hi = (target == 800u) ? 1u : 0u;
    g_sw_pending = 1;
    uint32_t t0 = DWT->CYCCNT;
    analogWrite(PIN_OUT, duty_value(target));
    uint32_t t1 = DWT->CYCCNT;
    g_sw_call[i] = t0;
    g_sw_cost[i] = t1 - t0;
    g_cur_permille = target;
    uint32_t w0 = millis();
    while (g_sw_pending && (millis() - w0) < 20u) {
      delayMicroseconds(100);
    }
    if (g_sw_pending) { g_sw_pending = 0; g_sw_timeouts++; }
    g_sw_done = i + 1u;
  }
  g_mode = MODE_IDLE;
}

void setup() {
  init_dwt_cm33();
  analogWriteResolution(16);
  pinMode(PIN_IN, INPUT_PULLDOWN);   // D3 is configured by analogWrite (pinctrl); no pinMode on D3
  attachInterrupt(digitalPinToInterrupt(PIN_IN), on_edge, CHANGE);
  NVIC_SetPriority(EXTI4_IRQn, 0);   // PB4 -> EXTI line 4; highest priority, as the referee does for D2
  analogWrite(PIN_OUT, duty_value(800));

  Bridge.begin();
  Bridge.provide("check_dwt_status", check_dwt_status);
  Bridge.provide("start_capture", start_capture);
  Bridge.provide("start_switch", start_switch);
  Bridge.provide("get_state", get_state);
  Bridge.provide("get_capture_summary", get_capture_summary);
  Bridge.provide("get_raw_chunk", get_raw_chunk);
  Bridge.provide("get_switch_info", get_switch_info);
  Bridge.provide("get_switch_chunk", get_switch_chunk);
}

void loop() {
  uint32_t cmd = g_cmd;
  if (cmd == CMD_CAPTURE) {
    g_busy = 1; run_capture(); g_cmd = CMD_NONE; g_busy = 0;
  } else if (cmd == CMD_SWITCH) {
    g_busy = 1; run_switch(); g_cmd = CMD_NONE; g_busy = 0;
  } else {
    Bridge.update();   // only while idle, as in the referee (no serial work during a test)
  }
}
