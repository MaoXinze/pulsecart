# PulseCart P1 接口契约

## 边界

PulseCart 分为两个进程：运营后端负责认证、数据版本、人工审核、问题卡与任务编排；NLP 服务只负责可审计模型的训练、注册和批量推理。两者不共用 ORM，也不允许模型服务绕过运营后端直接读取 MySQL 评论表。

| 服务 | 本地地址 | 责任 |
| --- | --- | --- |
| 运营后端 | `http://127.0.0.1:8006/jeecg-boot` | JWT、数据集、审核、问题卡、分析运行 |
| NLP 服务 | `http://127.0.0.1:8100` | 训练任务、模型注册、批量三分类预测 |

运营后端所有接口使用已有 JWT 鉴权。NLP 服务在 P1 仅面向受信任的内网 Worker，demo 环境不暴露到公网；生产接入时应在网关增加服务身份认证和请求审计。

## 运营后端

基础路径为 `/jeecg-boot/api/v1`。

| 方法与路径 | 用途 | 关键约束 |
| --- | --- | --- |
| `POST /datasets/imports` | 上传 CSV 并创建不可变数据集版本 | 只支持 CSV；同内容/映射幂等；保留拒绝行原因和 SHA-256 |
| `GET /datasets` | 查看已导入数据集 | 返回行数、版本和质量报告摘要 |
| `POST /demo/bootstrap` | 导入仓库内 1,200 条合成演示评论并播种 300 审核任务 | 仅演示，不能把参考标签用于训练 |
| `GET /review-tasks` | 获取审核任务和评论证据 | 评论按 `(dataset_version, review_id)` 复合键关联，防止跨导入批次串数据 |
| `PATCH /review-tasks/{task_id}` | 记录人工确认、修正或无效理由 | `approved` / `verified` 必须填情感；`rejected` 必须填原因 |
| `POST /analysis-runs` | 创建正式训练/评测运行 | 至少 15 条已审核样本；状态先为 `queued` |
| `GET /analysis-runs` | 查询运行状态与指标 | 指标只来自实际任务回写 |
| `POST /issues` | 人工创建正式问题卡 | 来源评论必须属于同一数据集版本 |
| `GET /issues` | 筛选问题卡 | 支持按数据集和状态查询 |
| `PATCH /issues/{issue_id}` | 更新处理状态 | 只允许 `open -> in_progress -> pending_validation -> closed`；关闭必须记录验证说明 |

`POST /datasets/imports` 的 `field_mapping` 是可选 JSON 表单字段，格式为“标准字段 -> 原始列名”。标准字段至少需要 `review_id`、`product_id`、`review_text`、`reviewed_at`。

## NLP 服务

### 可用性与模型

| 方法与路径 | 用途 | 响应语义 |
| --- | --- | --- |
| `GET /healthz` | 健康与模型就绪状态 | 没有已发布模型时返回 `status: not_ready`，服务仍然正常 |
| `GET /api/v1/models` | 模型注册清单 | 无效产物会保留并显示原因，不能被推理选择 |
| `POST /api/v1/predictions:batch` | 最多 200 条评论三分类 | `model_version` 可选；模型不可用时返回 HTTP 409 和 `model_not_ready` |

请求示例：

```json
{
  "model_version": "baseline-ds-20260828-v1",
  "texts": ["更新后经常撞桌腿，地图也丢了", "清扫干净，回充稳定"]
}
```

成功响应包含 `model_version`、`dataset_version`、各标签概率和置信度。P1 基线不具备属性抽取能力，响应会显式标记 `aspect_extraction.status: not_available`，禁止把空数组包装成模型抽取结果。

### 训练任务

| 方法与路径 | 用途 |
| --- | --- |
| `POST /api/v1/training-runs` | 以已审核记录创建持久化训练任务，返回 HTTP 202 |
| `GET /api/v1/training-runs` | 查询任务列表 |
| `GET /api/v1/training-runs/{job_id}` | 查询单个任务状态、指标和错误信息 |

训练请求必须包含 `dataset_version`、不可覆盖的 `model_version`、随机种子和至少 15 条记录。每条记录只能使用 `approved` / `verified` 状态和 `positive` / `neutral` / `negative` 标签。Worker 完成后，模型产物必须同时具有 `model.joblib` 和 `metadata.json`；服务会再次核验 SHA-256 才允许推理。

## 状态机与关联

```text
CSV 导入 -> 数据集版本 -> 人工审核任务 -> approved / verified
                                        -> 分析运行 queued -> NLP 训练任务 queued
                                        -> Worker running -> succeeded / failed
                                        -> 注册模型 -> 批量预测 -> 人工确认问题卡
```

模型永远不自动关闭、自动指派或自动批准问题卡。问题卡的关闭结论由品质/客服负责人验证并记录；模型版本、数据集版本、人工审核与来源评论需要能完整回查。
