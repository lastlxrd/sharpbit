#include "assets.h"

#include <string.h>

const mono_asset_t *const mono_assets[] = {
};

const size_t mono_assets_count =
    sizeof(mono_assets) / sizeof(mono_assets[0]);

const mono_asset_t *mono_asset_find(const char *name)
{
    if (name == NULL) {
        return NULL;
    }

    for (size_t i = 0; i < mono_assets_count; ++i) {
        if (strcmp(mono_assets[i]->name, name) == 0) {
            return mono_assets[i];
        }
    }

    return NULL;
}
