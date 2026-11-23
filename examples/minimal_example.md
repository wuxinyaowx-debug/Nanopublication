# 最小调用示例（纯合成）

> 以下输入、输出和数值均为演示工作流的虚构内容，不是正式案例、真实论文结论或预制测试答案。

## 1. 输入材料

将下面内容保存为 `/input/synthetic.txt`：

```text
SYNTHETIC EXAMPLE ONLY. In virtual system C, reagent R increased signal M from 2 to 6 arbitrary units after 4 h.
```

`/input/case.json`：

```json
{
  "case_id": "synthetic-minimal",
  "output_contract": {
    "type": "object",
    "properties": {
      "case_id": {"type": "string"},
      "answer": {"type": "string"},
      "status": {"type": "string"},
      "sources": {"type": "array"},
      "assertions": {"type": "array"},
      "uncertainties": {"type": "array"},
      "change_records": {"type": "array"}
    }
  }
}
```

先运行 README 中的 `index_sources.py`，从 `source_manifest.json` 复制实际的 `source_id`、`source_path` 和 `sha256`。这些值取决于真实输入内容与路径，不能预先编造。

## 2. 示意输出

下面是人工构造的示意草稿。将三个尖括号占位符替换为索引清单中的实际值，保存为 `/app/work/result.draft.json`，然后依次运行 `bind_evidence.py` 与 `audit_result.py`。

```json
{
  "case_id": "synthetic-minimal",
  "status": "success",
  "status_reason": null,
  "answer": "在虚拟系统 C 中，试剂 R 处理 4 h 后，信号 M 从 2 增至 6 个任意单位。（合成示例）",
  "sources": [
    {
      "source_id": "<COPY_SOURCE_ID_FROM_MANIFEST>",
      "source_path": "synthetic.txt",
      "sha256": "<COPY_SHA256_FROM_MANIFEST>",
      "title": "Synthetic minimal example",
      "authors": [],
      "year": null,
      "version": null,
      "identifiers": {},
      "extraction_method": "text"
    }
  ],
  "assertions": [
    {
      "text": "在虚拟系统 C 中，试剂 R 处理 4 h 后，信号 M 从 2 增至 6 个任意单位。",
      "subject": "Reagent R",
      "relation": "increases",
      "relation_type": "quantitative_measurement",
      "object": {"outcome": "signal M", "from": 2, "to": 6, "unit": "arbitrary units"},
      "conditions": {"model_system": "virtual system C", "time_point": "4 h"},
      "epistemic_status": "reported",
      "support_type": "direct",
      "evidence": [
        {
          "source_id": "<COPY_SOURCE_ID_FROM_MANIFEST>",
          "quote": "In virtual system C, reagent R increased signal M from 2 to 6 arbitrary units after 4 h.",
          "evidence_type": "text",
          "role": "supports"
        }
      ],
      "confidence": {
        "level": "high",
        "basis": "合成引文直接包含主体、变化方向、起止值、单位、系统与时间。"
      },
      "uncertainty": [],
      "derivation": null
    }
  ],
  "uncertainties": [
    {
      "type": "other",
      "description": "全部内容为虚构的软件调用示例，不表示真实科研发现。",
      "resolution": "not_applicable"
    }
  ],
  "change_records": []
}
```

完成后，`result.json` 保留全部任务字段，`assertions.jsonl` 含一条完整记录，`quality_report.json` 报告自动检查项。自动校验通过只代表结构与引文定位通过，仍须人工或 Agent 检查语义充分性。

## 3. 20 条断言题集

`synthetic_assertion_samples.json` 含 10 个合成问题、20 条参考断言，覆盖多结局、关联与机制、多时点、来源归因、未检出差异、机制链、图像证据、适用限制、方向/主体和派生计算。该文件是教学回归题集，不参与正式案例运行。
