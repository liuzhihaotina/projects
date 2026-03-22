import torch
import random

from zarr_read import Frame15ZarrDataset
from zarr_write import save_frames_to_zarr

# 构造示例数据
frames = []
for i in range(100):
    frame = []

    # field 0: 固定 shape
    frame.append(torch.randn(3, 224, 224, dtype=torch.float32))

    # field 1: 变长
    n = random.randint(10, 50)
    frame.append(torch.randint(0, 1000, (n, 4), dtype=torch.int32))

    # field 2: 固定 shape
    frame.append(torch.randn(128, dtype=torch.float64))

    # field 3: 变长 1D
    m = random.randint(20, 60)
    frame.append(torch.randint(0, 2, (m,), dtype=torch.uint8))

    # field 4~14: 随便补几个固定/变长
    for k in range(4, 15):
        if k % 2 == 0:
            frame.append(torch.randn(16, 16, dtype=torch.float32))
        else:
            s = random.randint(5, 15)
            frame.append(torch.randn(s, 8, dtype=torch.float32))

    frames.append(frame)

save_frames_to_zarr(frames, "data/zarr/demo_cache.zarr")

ds = Frame15ZarrDataset("data/zarr/demo_cache.zarr")
x = ds[3]

for i, t in enumerate(x):
    print(i, t.shape, t.dtype)