#ifndef TFT_TENNIS_CORE_H
#define TFT_TENNIS_CORE_H

#ifdef _WIN32
#define TFT_EXPORT __declspec(dllexport)
#else
#define TFT_EXPORT __attribute__((visibility("default")))
#endif

TFT_EXPORT int tft_core_version(void);
TFT_EXPORT double tft_deterministic_shot_error(int frame, int side, int score1, int score2, int power);
TFT_EXPORT unsigned int tft_pack_input(int left, int right, int angle_up, int angle_down,
                                       int hit, int power_down, int power_up);

#endif
