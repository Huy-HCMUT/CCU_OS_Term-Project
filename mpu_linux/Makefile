CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -std=gnu11 -pthread
LDFLAGS ?= -pthread -lm

SRC_DIR = workload
BUILD_DIR = build
TARGET = $(BUILD_DIR)/dual_thread_bench

SRCS = $(SRC_DIR)/dual_thread_bench.c $(SRC_DIR)/fft_math.c
OBJS = $(BUILD_DIR)/dual_thread_bench.o $(BUILD_DIR)/fft_math.o

.PHONY: all clean run_config_a run_config_b

all: $(TARGET)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)
	mkdir -p ../results/raw

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(TARGET): $(OBJS)
	$(CC) $(OBJS) $(LDFLAGS) -o $@
	@echo "Build successful: $(TARGET)"

run_config_a: $(TARGET)
	@mkdir -p ../results/raw
	./$(TARGET) --config A --stress 0 --cycles 10000 --out ../results/raw/config_A_stress_0.csv

run_config_b: $(TARGET)
	@mkdir -p ../results/raw
	sudo ./$(TARGET) --config B --stress 0 --cycles 10000 --out ../results/raw/config_B_stress_0.csv

clean:
	rm -rf $(BUILD_DIR)
