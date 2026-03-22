from typing import List

import numpy as np
import torch
import zarr


class Frame15ZarrDataset:
    def __init__(self, zarr_path: str, device: str = "cpu"):
        self.root = zarr.open_group(zarr_path, mode="r")
        self.num_frames = int(self.root.attrs["num_frames"])
        self.num_fields = int(self.root.attrs["num_fields"])
        self.fields_group = self.root["fields"]
        self.device = device

    def __len__(self):
        return self.num_frames

    def _load_field(self, field_idx: int, frame_idx: int) -> torch.Tensor:
        fg = self.fields_group[f"field_{field_idx}"]
        fixed_shape = bool(fg.attrs["fixed_shape"])

        if fixed_shape:
            arr = fg["data"][frame_idx]
            t = torch.from_numpy(np.asarray(arr))
            if self.device != "cpu":
                t = t.to(self.device, non_blocking=True)
            return t

        offsets = fg["offsets"]
        shapes = fg["shapes"]
        data = fg["data"]

        start = int(offsets[frame_idx])
        end = int(offsets[frame_idx + 1])
        shape = tuple(int(x) for x in shapes[frame_idx])

        flat = np.asarray(data[start:end])
        arr = flat.reshape(shape)
        t = torch.from_numpy(arr)
        if self.device != "cpu":
            t = t.to(self.device, non_blocking=True)
        return t

    def __getitem__(self, idx: int) -> List[torch.Tensor]:
        if idx < 0:
            idx += self.num_frames
        if idx < 0 or idx >= self.num_frames:
            raise IndexError(idx)

        return [self._load_field(k, idx) for k in range(self.num_fields)]