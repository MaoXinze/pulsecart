# PulseCart 分析包

`sentiment-ai/` 是 PulseCart 的可复跑数据和模型能力目录。它不直接承担运营工作台的鉴权与业务编排；这些职责属于 `../jeecg-fastapi/`。当前最先落地的是数据集导入与质量校验，为后续训练、批量分析和洞察聚合提供固定输入。

## 当前可验证能力

- `app/services/dataset_import.py`：UTF-8 CSV 导入、字段别名和显式映射、质量校验、数据集版本、SHA-256、规范化记录和拒绝行报告。
- `app/services/demo_data.py`：固定随机种子的扫地机器人合成演示集、审核任务、参考标签和完整性清单生成器。
- `app/services/baseline_sentiment.py`：仅基于人工审核任务训练的三分类 TF-IDF + Logistic Regression 基线，保存模型、数据指纹、划分、混淆矩阵和指标。
- `app/services/model_registry.py`：独立模型服务的只读注册表，只允许元数据完整、模型文件 SHA-256 匹配的三分类产物进入推理。
- `app/services/training_jobs.py`：本地开发/演示可用的持久化训练任务队列；任务保存审核记录、随机种子与最终指标，后续可替换为 Redis Worker。
- `scripts/import_reviews.py`：离线导入 CLI，可在不启动 MySQL、Redis、FastAPI 或模型服务时演示。
- `scripts/run_training_worker.py`：执行已入队的模型训练任务；不会用合成参考标签训练，也不会覆盖已有模型版本。
- `data/demo/sweep_robot/`：1,200 条无个人信息的合成评论、300 条审核任务和数据清单；使用边界见该目录 README。
- `tests/`：覆盖导入契约、审核任务抽样、演示数据可复现和传统基线训练。

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/generate_demo_reviews.py
python scripts/import_reviews.py data/demo/sweep_robot/reviews.csv
```

导入完成后，`data/imports/<dataset_version>/` 会生成 `report.json`、`records.jsonl` 和 `rejected.json`。该目录默认不提交 Git；只有 `data/demo/` 中的合成样本可以用于演示。

## 独立模型服务

从该目录启动服务：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

- `GET /healthz`：服务和已注册模型状态。没有经过人工审核训练并发布的模型时，会返回 `not_ready`，这是预期保护，不是成功预测。
- `GET /api/v1/models`：展示每个模型的版本、数据集版本、评测指标、产物哈希和无效原因。
- `POST /api/v1/predictions:batch`：批量三分类推理；可指定 `model_version`，未指定时只选择一个校验通过的模型。
- `POST /api/v1/training-runs` 与 `GET /api/v1/training-runs/{job_id}`：创建和查询可复现的训练任务。服务接口不会返回任务中包含的评论正文。

训练任务只接收 `approved` 或 `verified` 的人工审核记录。创建任务后，由本地 Worker 执行：

```powershell
python scripts/run_training_worker.py --limit 1
```

产物默认放在 `artifacts/models/<model_version>/`，任务文件默认放在 `runtime/training-jobs/`。可以通过 `PULSECART_MODEL_ROOT` 与 `PULSECART_TRAINING_JOB_ROOT` 调整到 D 盘的持久化位置。当前文件队列是 `dev + demo` 的实现，不把它描述成 Redis 生产 Worker；Redis 接入将复用相同的任务状态与模型版本契约。

## 旧推理原型

目录中保留了一套早期的 FastAPI 二分类推理原型和 BERT 加载代码，接口为 `/api/sentiment/predict`，仅用于后续迁移与历史兼容。它依赖 `artifacts/bert/best` 下的训练产物；当前仓库没有该权重、对应授权训练数据或可复现实测指标，因此它不会被 P1 模型注册表自动发现，也不能作为“BERT 已部署”或“准确率达到某值”的证据。

在导入数据、建立评测集之前，默认模型路线是可解释的 TF-IDF + Logistic Regression 或 Linear SVC。当前的 `scripts/train_baseline.py` 只读取审核状态为 `approved` 或 `verified` 的 `reviewer_sentiment`，主动拒绝合成参考标签；训练运行会保存数据集版本、划分、随机种子、特征参数、指标、混淆矩阵和产物校验值。人工审核集尚未完成前，不会在仓库提交伪造的模型权重或 F1。

## 后续职责

1. 读取 `dataset_version` 对应的规范化评论和人工审核任务，训练并评估情感基线。
2. 记录模型版本和预测结果，使每条洞察可回查数据集、模型与原始文本。
3. 由 `jeecg-fastapi` 的 Redis Worker 将正式分析运行提交给 `/api/v1/training-runs` 与 `/api/v1/predictions:batch`，并回写模型版本、任务状态与洞察证据。

完整业务边界、环境和验收路线见 [上级项目蓝图](../docs/重构蓝图.md)。
