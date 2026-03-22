import random
import torch
import time

from frame_cache import (
    build_stream_cache,
    StreamFrameCacheDataset,
    verify_lossless,
)


NUM_FRAMES = 10#200
NUM_FIELDS = 15

def get_frame(i):
    frames_len = 10
    frames = list()
    d1 = [2, 3, 5, 6, 8, 7, 3, 1, 10, 9, 5, 3, 6, 7, 8]
    big_tensor = list()
    for j in range(NUM_FIELDS):
        x = torch.randn(12, d1[j], 576, 224)
        big_tensor.append(x)
    return big_tensor

def get_frame1(i):
    """
    模拟你实际业务中的“每次遍历拿到一帧”。
    要求：
    - 同一 field 在所有帧中 dtype 固定
    - ndim 固定
    - shape 可以固定，也可以变
    """
    rng = random.Random(i)

    frame = []

    # field 0: 固定 shape float32
    g = torch.Generator().manual_seed(i * 1000 + 0)
    frame.append(torch.randn(3, 64, 64, dtype=torch.float32, generator=g))

    # field 1: 变长 int32
    n = rng.randint(5, 20)
    frame.append(torch.randint(0, 100, (n, 4), dtype=torch.int32))

    # field 2: 固定 shape float64
    g = torch.Generator().manual_seed(i * 1000 + 2)
    frame.append(torch.randn(16, dtype=torch.float64, generator=g))

    # field 3: 变长 bool
    m = rng.randint(10, 30)
    frame.append(torch.randint(0, 2, (m,), dtype=torch.uint8).bool())

    # field 4: 固定 shape bfloat16
    g = torch.Generator().manual_seed(i * 1000 + 4)
    frame.append(torch.randn(8, 8, dtype=torch.float32, generator=g).to(torch.bfloat16))

    # field 5: 变长 float16
    s = rng.randint(3, 12)
    g = torch.Generator().manual_seed(i * 1000 + 5)
    frame.append(torch.randn(s, 6, dtype=torch.float16, generator=g))

    # field 6: 固定 shape int64
    frame.append(torch.arange(20, dtype=torch.int64))

    # field 7: 变长 uint8
    s = rng.randint(15, 40)
    frame.append(torch.randint(0, 255, (s,), dtype=torch.uint8))

    # field 8: 固定 shape complex64
    g = torch.Generator().manual_seed(i * 1000 + 8)
    real = torch.randn(4, 4, generator=g)
    imag = torch.randn(4, 4, generator=g)
    frame.append(torch.complex(real, imag).to(torch.complex64))

    # field 9~14: 混合固定/变长
    for k in range(9, 15):
        if k % 2 == 0:
            g = torch.Generator().manual_seed(i * 1000 + k)
            frame.append(torch.randn(5, 5, dtype=torch.float32, generator=g))
        else:
            s = rng.randint(2, 10)
            g = torch.Generator().manual_seed(i * 1000 + k)
            frame.append(torch.randn(s, 3, dtype=torch.float32, generator=g))

    assert len(frame) == NUM_FIELDS
    return frame


def main():
    out_dir = "data/demo_stream_cache"

    print("=== build cache ===")
    s = time.time()
    build_stream_cache(
        get_frame=get_frame,
        num_frames=NUM_FRAMES,
        out_dir=out_dir,
        num_fields=NUM_FIELDS,
        compressor_name="zstd",
        clevel=3,
        shuffle="bitshuffle",
        chunk_frames_fixed=32,
        verbose_every=50,
    )
    print('----------build用时：', time.time() - s)

    print("\n=== read cache ===")
    s = time.time()
    ds = StreamFrameCacheDataset(out_dir)

    print("len(ds) =", len(ds))
    for j in range(len(ds)):
        sample = ds[j]
        for i, t in enumerate(sample):
            pass
            # print(i, t.shape, t.dtype)
    print('----------read cache用时：', time.time() - s)

    # print("\n=== verify lossless ===")
    # verify_lossless(
    #     get_frame=get_frame,
    #     cache_dir=out_dir,
    #     num_frames=NUM_FRAMES,
    #     num_fields=NUM_FIELDS,
    #     check_all=True,
    # )

    # print("\nDone.")


if __name__ == "__main__":
    main()