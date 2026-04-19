import random
import numpy as np
import torch
import time

from nested_cache import (
    build_nested_stream_cache,
    NestedStreamCacheDataset,
    verify_nested_stream_cache,
)


NUM_SAMPLES = 100


def get_sample(i: int):
    rng = random.Random(i)

    g1 = torch.Generator().manual_seed(i * 1000 + 1)
    g2 = torch.Generator().manual_seed(i * 1000 + 2)
    g3 = torch.Generator().manual_seed(i * 1000 + 3)

    n = rng.randint(30, 80)
    m = rng.randint(50, 102)

    sample = {
        "id": f"sample_{i}",
        "tokens": [f"tok_{i}_{j}" for j in range(rng.randint(2, 6))],
        "image": torch.randn(30, 302, 320, dtype=torch.float32, generator=g1),  # fixed tensor
        "meta": {
            "score": float(i) * 0.1,
            "valid": (i % 2 == 0),
            "boxes": torch.randint(0, 100, (n, 4), dtype=torch.int32),  # variable tensor
            "caption": f"caption for sample {i}",
            "aliases": [f"a{i}", f"b{i}", f"c{i}"],
            "embedding": torch.randn(16, dtype=torch.float64, generator=g2),  # fixed tensor
            "mask": torch.randint(0, 2, (m,), dtype=torch.uint8).bool(),       # variable tensor
        },
        "misc": [
            torch.randn(rng.randint(4, 10), 3, 11,  dtype=torch.float16, generator=g3),  # variable tensor
            "note_" + str(i),
            ["x", "y", f"z{i}"],
            None,
            np.arange(6, dtype=np.int64).reshape(2, 3),  # fixed ndarray
        ],
        "pair": (
            torch.randn(5, 5, dtype=torch.float32, generator=g1),  # fixed tensor
            f"tuple_str_{i}",
        ),
    }
    return sample


def main():
    out_dir = "data/demo_nested_cache"
    s = time.time()
    print("=== build nested cache ===")
    build_nested_stream_cache(
        get_sample=get_sample,
        num_samples=NUM_SAMPLES,
        out_dir=out_dir,
        compressor_name="zstd",
        clevel=3,
        shuffle="bitshuffle",
        chunk_samples_fixed=32,
        verbose_every=20,
    )
    print('----build用时：', time.time() - s)

    s = time.time()
    print("\n=== read dataset ===")
    ds = NestedStreamCacheDataset(out_dir)

    print("len(ds) =", len(ds))
    for i in range(len(ds)):
        x = ds[i]
    print('----读取用时：', time.time() - s)

    # s = ds[3]
    # print("sample[3] type =", type(s))
    # print("keys =", s.keys())
    # print("id =", s["id"])
    # print("tokens =", s["tokens"])
    # print("image shape =", s["image"].shape, s["image"].dtype)
    # print("meta.boxes shape =", s["meta"]["boxes"].shape, s["meta"]["boxes"].dtype)
    # print("misc[0] shape =", s["misc"][0].shape, s["misc"][0].dtype)
    # print("pair[0] shape =", s["pair"][0].shape, s["pair"][0].dtype)
    # print("pair[1] =", s["pair"][1])

    # print("\n=== verify ===")
    # verify_nested_stream_cache(
    #     get_sample=get_sample,
    #     cache_dir=out_dir,
    #     num_samples=NUM_SAMPLES,
    #     check_all=True,
    # )

    print("\nDone.")


if __name__ == "__main__":
    main()