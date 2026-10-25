#include "fft_math.h"
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static float s_hanning_window[FFT_SIZE];
static complex_float_t s_twiddle[FFT_SIZE / 2];
static unsigned int s_bit_rev[FFT_SIZE];
static int s_initialized = 0;

static unsigned int reverse_bits_10(unsigned int x) {
    unsigned int n = 0;
    for (int i = 0; i < 10; ++i) {
        n <<= 1;
        n |= (x & 1);
        x >>= 1;
    }
    return n;
}

void fft_init(void) {
    if (s_initialized) return;

    /* Precompute Hanning window coefficients */
    for (int i = 0; i < FFT_SIZE; ++i) {
        s_hanning_window[i] = 0.5f * (1.0f - cosf((float)(2.0 * M_PI * i / (FFT_SIZE - 1))));
    }

    /* Precompute Twiddle factors W_N^k = e^(-2*pi*i*k / N) */
    for (int k = 0; k < FFT_SIZE / 2; ++k) {
        float angle = (float)(-2.0 * M_PI * k / FFT_SIZE);
        s_twiddle[k].real = cosf(angle);
        s_twiddle[k].imag = sinf(angle);
    }

    /* Precompute 10-bit bit-reversal table */
    for (unsigned int i = 0; i < FFT_SIZE; ++i) {
        s_bit_rev[i] = reverse_bits_10(i);
    }

    s_initialized = 1;
}

void fft_apply_hanning(const float *input, float *output) {
    if (!s_initialized) fft_init();
    for (int i = 0; i < FFT_SIZE; ++i) {
        output[i] = input[i] * s_hanning_window[i];
    }
}

void fft_compute_1024(complex_float_t *data) {
    if (!s_initialized) fft_init();

    /* 1. Bit-reversal permutation */
    for (unsigned int i = 0; i < FFT_SIZE; ++i) {
        unsigned int j = s_bit_rev[i];
        if (i < j) {
            complex_float_t temp = data[i];
            data[i] = data[j];
            data[j] = temp;
        }
    }

    /* 2. Cooley-Tukey Radix-2 DIT butterfly computation */
    for (int len = 2; len <= FFT_SIZE; len <<= 1) {
        int half_len = len >> 1;
        int step = FFT_SIZE / len;

        for (int i = 0; i < FFT_SIZE; i += len) {
            for (int j = 0; j < half_len; ++j) {
                complex_float_t u = data[i + j];
                complex_float_t w = s_twiddle[j * step];

                /* v = w * data[i + j + half_len] */
                complex_float_t in_val = data[i + j + half_len];
                complex_float_t v;
                v.real = w.real * in_val.real - w.imag * in_val.imag;
                v.imag = w.real * in_val.imag + w.imag * in_val.real;

                data[i + j].real = u.real + v.real;
                data[i + j].imag = u.imag + v.imag;
                data[i + j + half_len].real = u.real - v.real;
                data[i + j + half_len].imag = u.imag - v.imag;
            }
        }
    }
}

int fft_extract_spectrum_and_peak(const complex_float_t *fft_data,
                                  float *magnitudes,
                                  float *peak_magnitude,
                                  float *total_energy) {
    int peak_bin = 0;
    float max_mag = 0.0f;
    float energy_sum = 0.0f;

    /* Single-sided spectrum: bins 0 to 511 (Nyquist) */
    for (int i = 0; i < FFT_SIZE / 2; ++i) {
        float re = fft_data[i].real;
        float im = fft_data[i].imag;
        float mag = sqrtf(re * re + im * im) / (float)FFT_SIZE;
        if (i > 0) mag *= 2.0f; /* Double magnitude for single-sided representation (except DC) */

        if (magnitudes) {
            magnitudes[i] = mag;
        }

        energy_sum += mag * mag;

        /* Skip DC bin 0 when determining peak fault frequency */
        if (i > 0 && mag > max_mag) {
            max_mag = mag;
            peak_bin = i;
        }
    }

    if (peak_magnitude) *peak_magnitude = max_mag;
    if (total_energy) *total_energy = energy_sum;

    return peak_bin;
}
