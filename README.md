# IS 507 Project: Alibaba GPU Cluster Trace

This repository contains a reproducible preprocessing and analysis workflow for
the Alibaba Cluster Trace GPU v2026 dataset. The study scope is the first 30
relative days (`day = 0` through `day = 29`) of pod-hourly observations and the
complete job-execution summary.

## Canonical analysis files

All downstream Python, R, and DuckDB analyses use exactly two processed files:

```text
data/processed/
  asi_opensource_pod_hourly_processed.parquet
  asi_opensource_job_execution_summary_processed.parquet
```

The processed files contain the original fields plus documented cleaning and
indicator fields. Raw files remain immutable inputs and are not the downstream
analysis interface.

## Reproduce the data

1. Place the two raw single-file Parquet datasets under `data/`:

   ```text
   data/asi_opensource_pod_hourly_day0_29.parquet
   data/asi_opensource_job_execution_summary.parquet
   ```

2. Open `data_pre_process.ipynb` and run it from the first cell.
3. Review the in-notebook integrity, profile, relationship, and PCA tables.
4. Confirm the preprocessing settings, set `WRITE_PROCESSED_FILES = True`,
   and rerun the materialization and validation sections.
5. Create the distribution archive:

   ```powershell
   python scripts/package_team_data.py
   ```

The result is `data/IS507_processed_data.zip`. It contains only the two files
under `data/processed/` and can be extracted directly into the repository root.
Parquet already uses ZSTD compression, so the ZIP intentionally uses store
mode to avoid slow and ineffective recompression.

## Analysis entry points

- `data_pre_process.ipynb`: integrity checks, missingness, field profiles,
  distributions, relationships, PCA, preprocessing, and final materialization.
- `r_start.R`: simple Arrow/dplyr access to the two canonical files.
- `docs/PREPROCESSING.md`: canonical rules and configuration decisions.
- `docs/DATA_README.md`: data layout, grain, fields, and usage notes.
- `docs/DATA_PROFILE.md`: profile scope and interpretation guidance.
- `scripts/`: raw-data acquisition, merge, and processed-data packaging tools.

## Python setup

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## R setup

```r
install.packages(c("arrow", "dplyr"))
source("r_start.R")
```

After sourcing the file, `pod` and `summary` are lazy Arrow datasets. No
preprocessing policy needs to be repeated in R.

Official references:

- [Dataset download](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/data_download.md)
- [Dataset schema](https://github.com/alibaba/clusterdata/blob/master/cluster-trace-gpu-v2026/docs/schema.md)

## Important limitations

- `day` is relative to the trace start, not a calendar date.
- Missing `workload_id` values are common, especially in the execution summary.
- Negative delay values are retained in raw fields and converted to missing only
  in explicitly named `*_clean` fields.
- Literal `Unknown` and `unknown` are source categories, not null values.
- Aggregate each table to a declared grain before joining; joining both tables
  at raw row level can create a many-to-many expansion.



## 資料探索(暫時)
1. 資料完整度
完整檔案檢查通過：
Dataset	Rows	Size	Columns
Pod hourly	842,390,418	33.476 GiB	25
Execution summary	40,522,321	1.107 GiB	14


Pod hourly 涵蓋：
- Day 0–29，共 30 天
- Hour 0–23
- 完整 720 個 day/hour 組合
所以下載與合併結果完整，沒有遺漏日期或小時。
2. 缺值與例外值
這部分使用：
- Pod：Day 0 Hour 0，共 1,179,029 列
- Summary：前 1,000,000 列
因此適合制定清理規則，但不能直接視為完整 30 天的母體比例。
Workload ID
Dataset	Missing workload ID
Pod sample	23.21%
Summary sample	87.97%


Summary 的缺失比例非常高。因此我建議維持：
WORKLOAD_ID_POLICY = "keep"
不建議直接使用 drop，否則 summary 可能失去將近 88% 的資料。也不建議把缺值全部當成同一個真實 workload。
目前 processed dataset 會保留：
- workload_id
- workload_id_clean
- workload_id_missing
- workload_id_processed
這樣分析 workload 時可以自行篩選，但不會永久刪除資料。
Delay 欄位
Pod sample：
- Schedule delay 缺值：2.07%
- Schedule delay 負值：幾乎為零
- Ready delay 缺值：2.07%
- Ready delay 負值：28.41%
Summary sample：
- Schedule delay 缺值或負值：合計約 1.54%
- Ready delay 缺值或負值：合計約 56.41%
-1 很可能是系統 sentinel，而不是真實負數秒數。Notebook 的處理正確：
- 保留原始 delay
- 在 schedule_delay_sec_clean、ready_delay_sec_clean 中將負值轉為 NULL
如此可以維持可追溯性，又不會把 -1 當成真正的等待時間。
GPU utilization 缺值
Pod sample 中：
- avg_gpu_sm_util 缺值 94.21%
- avg_gpu_mem_gib 缺值 92.72%
- gpu_request 的中位數與第 75 百分位數都是 0
這表示多數 pod-hour 根本沒有要求 GPU，因此 utilization 缺值很可能是結構性缺值，不適合用平均數或 0 全面補值。目前保留 NULL 並增加 gpu_utilization_observed 是合理做法。
3. 分布與探索結果
Execution duration
Summary duration 高度右偏：
- Median：0.428 小時，約 25.7 分鐘
- 75th percentile：1.5 小時
- 99th percentile：69.7 小時
- Maximum：1,824 小時，約 76 天
- Mean：5.35 小時
平均數被少數超長工作拉高。後續分析應優先使用：
- Median
- Quantiles
- 或建模時使用 log1p(duration_hours_clean)
不建議直接刪除長 duration，除非確認是資料錯誤。
類別分布
Pod Day 0 Hour 0：
- state_public 全部是 Unknown
- job_type_public = unknown：92.56%
- model_type_public = unknown：92.85%
- GenAI request：3.09%
Summary 前 100 萬列：
- Offline inference：79.30%
- GenAI model：79.01%
- GenAI request：77.43%
- Low priority：82.45%
- Ready：46.95%
兩張表的差異很大，但不能直接解釋為整體族群差異，因為：
- 表格 grain 不同
- Pod 只取一個小時
- Summary 取檔案前 100 萬列，並非隨機抽樣
4. Correlation 與 PCA
Pod sample 中資源相關欄位高度相關：
- GPU request ↔ GPU memory request：0.963
- GPU request ↔ used GPU hours：0.964
- GPU request ↔ average GPU memory：0.782
- GPU request ↔ SM utilization：0.701
代表 PCA 的第一主成分可以解釋成「GPU 資源規模／使用強度」。
Pod PCA：
- PC1：45.24%
- 前 2 個 PCs：57.14%
- 前 5 個 PCs：86.41%
Summary PCA 沒有明顯的單一主成分：
- PC1：26.46%
- PC2：25.76%
- PC3：24.34%
- PC4：23.44%
也就是 summary 的 GPU request、duration、schedule delay、ready delay 分別代表不同面向，PCA 不會明顯簡化成一個共同尺度。
此外，summary correlation 大多很低，例如：
- GPU request ↔ duration：0.002
- Duration ↔ ready delay：0.073
表示它們幾乎沒有簡單線性關係，但仍可能存在：
- 類別差異
- 非線性關係
- Interaction effects
5. Job/model relationship
一些值得研究的結果：
Job/model group	Ready rate	Median duration
Offline inference / GenAI	41.4%	0.33 hr
Training / recommendation	94.0%	1.11 hr
Training / GenAI	86.4%	1.00 hr
Online inference / CV	46.2%	1.11 hr
Online inference / recommendation	66.8%	10.78 hr


這顯示 job type、model type 與 ready outcome、duration 可能存在明顯關聯，比單純使用 GPU request 更值得深入分析。
目前 preprocessing 結論
目前設定是合理且保守的：
- Workload ID：保留缺值，不刪列。
- Negative delay：只在 *_clean 欄位轉為 NULL。
- 類別缺值：在 *_clean 欄位填入 Unknown/unknown。
- Duration：保留極端值。
- GPU utilization：保留結構性缺值，不全面補值。
- 原始欄位全部保留。
- 處理前後 row count 相同，驗證通過。
