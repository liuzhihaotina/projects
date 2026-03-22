import torch

frames_len = 100
frames = list()
d1 = [2, 3, 5, 6, 8, 7, 3, 1, 10, 9, 5, 3, 6, 7, 8]
for i in range(frames_len):
    big_tensor = list()
    for j in range(15):
        x = torch.randn(12, d1[j], 576, 224)
        big_tensor.append(x)
    frames.append(big_tensor)
torch.save(frames, 'data/frames.pt')