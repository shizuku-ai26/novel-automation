# NOVEL_AUTOMATION — AI小説制作パイプライン

**何を**：企画→プロット→キャラ設計→執筆→推敲までの小説制作を30以上の工程に
分解し、Claude / GPT / Gemini を工程ごとに使い分けるPython製パイプライン。
CLI司令塔（`run_pipeline.py`）で工程を選択実行でき、Notionと連携。

**誰のためか**：AIで小説・長編コンテンツを半自動制作したい作家・AI協創作家のため。

**技術**：Python / マルチLLMオーケストレーション / 工程モジュール化（S1〜S32）/ Notion連携。

> 補足：この「工程分解 × マルチLLM設計」の手法は、小説以外の長尺ワークフローにも応用可能です。

---

## 使い方

```bash
python run_pipeline.py --skill 1        # 工程①のみ実行
python run_pipeline.py --skill 1-4      # 工程①〜④を順番に実行
python run_pipeline.py --skill 2        # 工程②のみ（前回①の結果を引き継ぎ）
```

## 構成

- `run_pipeline.py` … 司令塔。`--skill` で実行する工程を選ぶ
- `skills/`（s01〜s32） … 各工程をモジュール化（どんでん返し選択・投稿形態設計・キャラ設計・本編執筆・推敲 等）
- `common/utils.py` … 共通ユーティリティ（config読込ほか）
- `openai_utils.py` / `gemini_utils.py` … LLM呼び出しの抽象化
- `config.yaml` … 実行設定
- Notion連携 … 生成物のDB管理

## ステータス

個人プロジェクト。AI協創作家「シズク」が、小説制作の属人的・反復工程を
再現可能なスクリプト群に置き換える目的で開発。

---

作者：シズク（AI協創作家）
