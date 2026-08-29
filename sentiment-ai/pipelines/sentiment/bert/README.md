# 历史 BERT 二分类微调原型

> 本目录保留原项目的二分类 BERT 训练、评估和推理代码，供后续兼容和 Transformer 对比实验使用。当前仓库不含原训练数据、预训练模型或微调权重，也没有可复现实测指标；它不是 PulseCart 的默认模型或已部署服务。

## 目录职责

- 训练 / 划分 / 评估：本目录
- 推理 HTTP：`sentiment-ai/app/`
- 数据：`data/raw/train.csv`（中文主训），划分结果 → `data/processed/`
- 权重：`artifacts/bert/best/`（不入库）
- 预训练：`artifacts/pretrained/bert-base-chinese/`（本地拷贝，不联网下载）

## 重要：Git 不会带上的东西

以下文件被 `.gitignore` 忽略，**推送代码后队友拿不到**，需你单独发给他们（网盘 / U 盘 / 共享盘）：

| 内容 | 放到队友机器上的路径 |
|------|----------------------|
| 中文数据 `train.csv` | `sentiment-ai/data/raw/train.csv` |
| 预训练模型目录 `bert-base-chinese/`（含 `pytorch_model.bin` 等） | `sentiment-ai/artifacts/pretrained/bert-base-chinese/` |

英文 `data.csv` 本任务不混训，可不发。

## 环境（有 GPU 的队友）

```powershell
# 在仓库根目录安装统一依赖
cd ..   # → sentiment-plus/
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# 若有 NVIDIA GPU，建议再装对应 CUDA 版 torch，例如：
# pip install torch --index-url https://download.pytorch.org/whl/cu121
cd sentiment-ai
```

确认 GPU：

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

应打印 `True`。

## 配置检查（正式全量训练前）

打开 `configs/bert_sentiment.yaml`，确认：

- `max_train_samples: null`
- `max_val_samples: null`
- `epochs: 2`（或 3～4）
- `model_name: artifacts/pretrained/bert-base-chinese`

## 训练流程（在 sentiment-ai 根目录）

```powershell
python -m pipelines.sentiment.bert.split_data
python -m pipelines.sentiment.bert.train
python -m pipelines.sentiment.bert.evaluate
python -m pipelines.sentiment.bert.infer --text "味道很好" "物流太慢"
```

训练结束后把 `artifacts/bert/best/` 整包发回给你（用于推理 / 交 1 号）。

## 启动推理服务

```powershell
uvicorn app.main:app --reload --port 8100
```

## 超参

本地 `bert-base-chinese`，`max_length=128`，`lr=2e-5`，`batch_size=16`，`epochs=2~4`，AdamW

## 历史验收目标，不是当前结果

旧项目中曾写有“测试集 Acc ≥ 92%，F1 ≥ 0.90，优于 CNN/BiLSTM”的目标，但没有对应的可复现数据、权重、运行记录或评测报告。本项目不得将其用于 README、简历、演示或接口说明。重新启用 Transformer 后，必须以已审核数据集重新训练，并报告三分类评测、模型版本、压缩前后延迟与 F1。
