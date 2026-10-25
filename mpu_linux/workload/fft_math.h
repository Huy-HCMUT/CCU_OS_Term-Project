#ifndef FFT_MATH_H
#define FFT_MATH_H

#include <stddef.h>
#include <math.h>

#define FFT_SIZE 1024

typedef struct {
    float real;
    float imag;
} complex_float_t;

/**
 * Initialize precomputed Twiddle factors and Hanning window for 1024-point FFT.
 */
void fft_init(void);

/**
 * Apply Hanning window to 1024 real input samples.
 */
void fft_apply_hanning(const float *input, float *output);

/**
 * Perform 1024-point in-place Cooley-Tukey Radix-2 Decimation-In-Time FFT.
 * 'data' array must have length FFT_SIZE.
 */
void fft_compute_1024(complex_float_t *data);

/**
 * Extract magnitude spectrum (length FFT_SIZE / 2 = 512) and dominant peak.
 * Returns the peak frequency bin index (0 to 511).
 */
int fft_extract_spectrum_and_peak(const complex_float_t *fft_data,
                                  float *magnitudes,
                                  float *peak_magnitude,
                                  float *total_energy);

#endif /* FFT_MATH_H */
