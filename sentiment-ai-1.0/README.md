# sentiment-ai-1.0（历史归档）

> 这是早期二分类实验实现的保留副本，不是 `sentiment-ai/` 的链接，也不作为独立服务或独立简历项目继续开发。当前产品能力以 [`../sentiment-ai/`](../sentiment-ai/) 的数据导入、可复跑训练和版本化分析为准。
>
> 本目录不包含可验证的线上权重、授权训练数据或实测指标。保留它仅用于迁移旧 pipeline 和接口兼容，不能据此声称 BERT 已部署或具备某个效果指标。

## 历史内容

## 1.0 做什么

| 能力 | 说明 |
|------|------|
| 整句情感 | `label`：**0=差评，1=好评** |
| 关键词 / 优缺点 / 属性 | 仍挂在本服务（或同仓库 pipelines） |
| 数据主集 | `train2.csv`（中文 0/1） |

**不是**开心/伤心等多情绪分类；那是 2.0 规划方向之一。

## 启动

```powershell
cd sentiment-ai   # 或 sentiment-ai-1.0
# 依赖在仓库根目录：pip install -r ../requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

业务后端默认：`SENTIMENT_AI_BASE_URL=http://127.0.0.1:8100`

## 核心接口（1.0）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/sentiment/predict` | 二分类推理 |

默认请求体示例：`{"texts": ["物流很快"]}` → 每条含 `label` / `label_name` / `confidence`。

## 与 2.0 关系

```
1.0（本目录）  稳定：好评/差评 + 现有 pipelines
2.0（sentiment-ai-2.0）  新开：固定多标签 → 再做「拼多多式」按商品动态标签
```

郑平高当前联调 **只接 1.0（8100）**；2.0 就绪后再加配置项切换。
