#!/bin/sh
# RNNoise (xiph 新代 v0.2, mumble d983458 快照) macOS 构建配方 —— 产物放仓库根供服务加载
# Windows: 同源码 + config.h + rnnoise_data*.c，用 DLL 目标编 rnnoise.dll 进 vendor（见 win_pack.md）
cd "$(dirname "$0")"
cc -O3 -shared -fPIC -DHAVE_CONFIG_H -I. -Iinclude -Isrc -DNDEBUG \
  src/rnnoise_data.c src/rnnoise_tables.c src/rnn.c src/pitch.c src/nnet.c \
  src/nnet_default.c src/parse_lpcnet_weights.c src/kiss_fft.c src/denoise.c src/celt_lpc.c \
  -o ../../librnnoise.dylib
