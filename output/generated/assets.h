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



extern const mono_asset_t *const mono_assets[];
extern const size_t mono_assets_count;

const mono_asset_t *mono_asset_find(const char *name);

#ifdef __cplusplus
}
#endif
