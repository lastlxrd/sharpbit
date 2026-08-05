#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    const uint8_t *data;
    size_t data_size;
} mono_asset_t;

typedef struct {
    const uint8_t *data;
    size_t data_size;
    uint16_t duration_ms;
} mono_animation_frame_t;

typedef struct {
    const char *name;
    uint16_t width;
    uint16_t height;
    uint16_t stride;
    uint16_t frame_count;
    const mono_animation_frame_t *frames;
} mono_animation_t;

extern const mono_asset_t mono_asset_photo_2026_08_05_18_41_52;
extern const mono_asset_t mono_asset_photo_2026_08_05_18_41_57;
extern const mono_asset_t mono_asset_photo_2026_08_05_18_41_55;

extern const mono_animation_t mono_animation_video;

extern const mono_asset_t *const mono_assets[];
extern const size_t mono_assets_count;

extern const mono_animation_t *const mono_animations[];
extern const size_t mono_animations_count;

const mono_asset_t *mono_asset_find(const char *name);
const mono_animation_t *mono_animation_find(const char *name);

#ifdef __cplusplus
}
#endif
