# PulseCart 商品体验洞察平台

PulseCart 面向商品运营、品类负责人、数据分析师和客服负责人，把商品评论从“文本存档”转成可验证、可回查、可行动的体验信号：数据导入时先做质量校验，再执行版本化分析，最后在看板上按 SKU、类目、渠道和时间窗口定位问题，并回查原始评论证据。

这个仓库由原有评论情感分析项目重构而来。`sentiment-plus` 与 `product-sentiment-plus` 是同一项目的两个演进版本，不再作为两个独立项目继续开发；后者保留作历史参考。重构目标、业务角色、数据边界、架构和验收路线见 [重构蓝图](docs/重构蓝图.md)。

## 正式项目文档

- [业务背景与项目目标](docs/01-业务背景与项目目标.md)
- [需求分析说明书](docs/02-需求分析说明书.md)
- [详细使用手册](docs/03-详细使用手册.md)
- [详细设计说明书](docs/04-详细设计说明书.md)

## 当前交付

当前首先完成数据闭环，而不是继续堆叠静态图表或未验证的模型指标：

- CSV 导入支持标准字段、常见别名和显式字段映射。
- 导入前校验必填字段、空文本、重复 `review_id`、日期、评分、文本长度、语言标记和额外列。
- 输出稳定的 `dataset_version`、文件 SHA-256、有效/拒绝行数、拒绝原因统计和拒绝行报告。
- 规范化记录、报告和拒绝行按版本保存；相同文件和映射可幂等复用。
- 提供可复现的合成演示数据：1,200 条扫地机器人评论、300 条人工审核任务、独立参考标签和 SHA-256 清单，不包含真实用户身份信息。
- 提供只使用已审核标签的三分类 TF-IDF + Logistic Regression 训练基线；训练产物包含数据指纹、随机种子、混淆矩阵和评测指标。
- JeecgBoot Vue 3 工作台已接入数据集导入、演示数据初始化、人工审核、分析运行和商品体验问题卡状态流转；旧的单条分析、关键词和模型页面保留为实验对比入口。

核心实现位于 [`sentiment-ai/app/services/dataset_import.py`](sentiment-ai/app/services/dataset_import.py)，命令行入口位于 [`sentiment-ai/scripts/import_reviews.py`](sentiment-ai/scripts/import_reviews.py)。导入模块只依赖 Python 标准库，便于被 API、异步 worker 和离线任务复用。

## 快速演示

建议使用 Python 3.12.x。当前导入闭环不要求启动 MySQL、Redis 或模型服务：

```powershell
cd sentiment-ai
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/generate_demo_reviews.py
python scripts/import_reviews.py data/demo/sweep_robot/reviews.csv
```

报告中的 `dataset_version` 可以作为后续分析运行的固定输入。重复执行同一命令时，报告会标记 `reused: true`，不会重复产生另一份规范化数据。

## 目标业务闭环

```text
合规 CSV
   -> 字段映射与质量校验
   -> dataset_version / checksum
   -> 批量情感、属性、主题分析
   -> 按 SKU / 类目 / 渠道 / 时间聚合
   -> 证据评论回查
   -> 关注项、告警与人工反馈
```

## 目录职责

| 目录 | 职责 | 当前策略 |
| --- | --- | --- |
| `jeecg-fastapi/` | 认证、业务 API、任务编排和领域数据访问 | 保留 FastAPI 与现有登录能力，逐步把静态 Mock 替换为领域服务 |
| `jeecgboot-vue3/` | 运营工作台和图表展示 | 复用 Vue 3 与图表基础，已接入数据集、审核、分析运行和问题卡工作流 |
| `sentiment-ai/` | 数据导入、模型训练、推理和评测 | 已落地导入质量、审核任务种子、可复跑 TF-IDF 基线与独立模型服务 |
| `sentiment-ai-2.0/` | 实验性多标签能力 | 暂不独立部署，等有数据和评测结果后再接入 |
| `product-sentiment-plus/` | 历史参考版本 | 冻结，不作为第三个产品继续扩展 |

## 环境基线

- Python 3.12.x
- Node.js 22 LTS + pnpm
- MySQL 8：业务数据、数据集元数据和分析运行记录
- Redis 7：异步导入/分析任务与短状态
- MinIO 或 S3：上传文件和模型产物
- Docker Compose：本地依赖和 staging 环境

第一阶段的导入器使用本地版本目录，方便离线验证；接入管理端后，文件内容和导入任务会迁移到 MinIO/MySQL，数据库记录保存任务状态、版本、统计和审计信息。

## 分阶段路线

1. P1 数据闭环：导入、校验、版本化、拒绝行解释和导入历史。
2. P2 分析闭环：可复跑 TF-IDF + Logistic Regression 或 Linear SVC，保存数据集、模型版本、随机种子和指标。
3. P3 运营闭环：趋势、属性问题排行、证据评论、导出、关注项和阈值告警。
4. P4 工程交付：异步任务、数据库迁移、Docker Compose、API 集成测试和固定 Demo 端到端演示。

## 真实性边界

Mock 只用于明确标注的演示环境；没有训练产物、评测集和运行记录时，不声称 BERT 线上可用、准确率达到某个数值、实时处理海量数据或已经生产上线。简历中的指标只填写仓库内可复现的实测结果。
