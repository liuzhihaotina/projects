# Stream Frame Cache

一个用于流式缓存“每帧15个tensor”的项目。

## 特性

- 流式写入：每次只需要一帧
- 无损
- 支持变长 shape
- 支持 bfloat16 无损
- 读取时 `dataset[i]` 返回 `List[Tensor]`，结构与原始帧一致

## 安装

```bash
pip install -r requirements.txt