#include "tennis_core.h"
#include <stdint.h>

#define TFT_CORE_VERSION 1

int tft_core_version(void) {
    return TFT_CORE_VERSION;
}

double tft_deterministic_shot_error(int frame, int side, int score1, int score2, int power) {
    if (power <= 100) {
        return 0.0;
    }

    const double error_range = (double)(power - 100) * 0.125;
    uint64_t seed =
        (uint64_t)(uint32_t)frame * 1103515245ULL +
        (uint64_t)(uint32_t)side * 12345ULL +
        (uint64_t)(uint32_t)score1 * 97ULL +
        (uint64_t)(uint32_t)score2 * 193ULL;

    seed &= 0x7fffffffULL;
    const double normalized = ((double)(seed % 2001ULL) / 1000.0) - 1.0;
    return normalized * error_range;
}

unsigned int tft_pack_input(int left, int right, int angle_up, int angle_down,
                            int hit, int power_down, int power_up) {
    return ((left ? 1u : 0u) |
            ((right ? 1u : 0u) << 1) |
            ((angle_up ? 1u : 0u) << 2) |
            ((angle_down ? 1u : 0u) << 3) |
            ((hit ? 1u : 0u) << 4) |
            ((power_down ? 1u : 0u) << 5) |
            ((power_up ? 1u : 0u) << 6));
}
