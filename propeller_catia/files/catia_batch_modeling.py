"""
CATIA 批量参数化建模
读取采样结果 CSV，批量修改 CATIA 参数并导出 STEP
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, List

import pandas as pd

try:
    from pycatia import catia
except Exception as exc:  # pragma: no cover
    catia = None
    _catia_import_error = exc


class CATIABatchModeler:
    def __init__(self, template_path: str, output_dir: str):
        self.template_path = template_path
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Python 参数名 -> CATIA 参数名
        self.param_mapping = {
            "旋翼直径": "旋翼直径",
            "翼根弦长": "翼根弦长",
            "翼中弦长": "翼中弦长",
            "翼尖弦长": "翼尖弦长",
            "翼根扭转角": "翼根扭转角",
            "翼中扭转角": "翼中扭转角",
            "翼尖扭转角": "翼尖扭转角",
        }

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(output_dir, f"batch_log_{ts}.txt")

        self.success_count = 0
        self.fail_count = 0
        self.failed_cases: List[int] = []

    def log(self, message: str, also_print: bool = True):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{ts}] {message}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
        if also_print:
            print(msg)

    def _ensure_catia(self):
        if catia is None:
            raise RuntimeError(
                f"pycatia 未安装或不可用: {_catia_import_error}"
            )

    def modify_parameters(self, doc, params: Dict[str, float]) -> bool:
        try:
            if self.template_path.endswith(".CATPart"):
                obj = doc.part
            elif self.template_path.endswith(".CATProduct"):
                obj = doc.product
            else:
                raise ValueError("不支持的 CATIA 文件类型")

            parameters = obj.parameters

            for py_name, catia_name in self.param_mapping.items():
                if py_name not in params:
                    continue
                try:
                    param = parameters.item(catia_name)
                    param.value = float(params[py_name])
                except Exception as e:
                    self.log(f"参数修改失败: {catia_name}, {e}", also_print=False)
                    return False

            obj.update()
            time.sleep(0.5)
            return True
        except Exception as e:
            self.log(f"修改参数异常: {e}")
            return False

    def export_step(self, doc, output_path: str) -> bool:
        try:
            doc.export_data(output_path, "stp")
            if os.path.exists(output_path):
                return True
            self.log("STEP 文件未生成", also_print=False)
            return False
        except Exception as e:
            self.log(f"导出 STEP 失败: {e}")
            return False

    def process_single_case(self, case_id: int, params: Dict[str, float], save_catia: bool) -> Dict:
        self._ensure_catia()

        result = {
            "case_id": case_id,
            "success": False,
            "error": None,
            "step_path": None,
            "catia_path": None,
        }

        self.log(f"\n{'='*70}")
        self.log(f"处理案例 #{case_id}")
        self.log(f"{'='*70}")

        for k, v in params.items():
            if isinstance(v, (float, int)):
                self.log(f"  {k}: {v:.2f}", also_print=False)

        try:
            caa = catia()
            documents = caa.documents
            doc = documents.open(self.template_path)

            if not self.modify_parameters(doc, params):
                raise RuntimeError("参数修改失败")

            step_filename = f"xv15_case_{case_id:04d}.stp"
            step_path = os.path.join(self.output_dir, step_filename)
            if not self.export_step(doc, step_path):
                raise RuntimeError("STEP 导出失败")
            result["step_path"] = step_path

            if save_catia:
                catia_filename = f"xv15_case_{case_id:04d}.CATProduct"
                catia_path = os.path.join(self.output_dir, catia_filename)
                doc.save_as(catia_path)
                result["catia_path"] = catia_path

            doc.close()
            result["success"] = True
            self.success_count += 1
        except Exception as e:
            result["error"] = str(e)
            self.fail_count += 1
            self.failed_cases.append(case_id)
            self.log(f"案例 #{case_id} 失败: {e}")
            try:
                doc.close()
            except Exception:
                pass

        return result

    def batch_process(
        self,
        df: pd.DataFrame,
        start_idx: int = 0,
        end_idx: int | None = None,
        save_catia: bool = False,
        save_interval: int = 10,
    ) -> pd.DataFrame:
        if end_idx is None:
            end_idx = len(df)

        total = end_idx - start_idx
        self.log("\n" + "=" * 70)
        self.log("批量建模开始")
        self.log("=" * 70)
        self.log(f"模板文件: {self.template_path}")
        self.log(f"输出目录: {self.output_dir}")
        self.log(f"处理范围: {start_idx} - {end_idx} (共 {total})")

        results = []
        start_time = time.time()

        for i in range(start_idx, end_idx):
            case_id = i + 1
            params = df.iloc[i].to_dict()
            result = self.process_single_case(case_id, params, save_catia)
            results.append(result)

            processed = i - start_idx + 1
            progress = processed / max(total, 1) * 100.0
            elapsed = time.time() - start_time
            eta = (elapsed / max(processed, 1)) * (total - processed)
            self.log(
                f"进度: {processed}/{total} ({progress:.1f}%) | "
                f"成功: {self.success_count} | 失败: {self.fail_count} | "
                f"已用时: {elapsed/60:.1f} 分钟 | 预计剩余: {eta/60:.1f} 分钟"
            )

            if processed % save_interval == 0:
                tmp = pd.DataFrame(results)
                tmp.to_csv(
                    os.path.join(self.output_dir, "temp_results.csv"),
                    index=False,
                    encoding="utf-8-sig",
                )
                self.log("已保存中间结果")

        results_df = pd.DataFrame(results)
        self.log("\n" + "=" * 70)
        self.log("批量建模完成")
        self.log("=" * 70)
        self.log(f"总数: {total}")
        self.log(f"成功: {self.success_count}")
        self.log(f"失败: {self.fail_count}")

        if self.failed_cases:
            self.log(f"失败案例: {self.failed_cases}")

        return results_df


if __name__ == "__main__":
    SAMPLES_FILE = "xv15_design_samples.csv"
    TEMPLATE_FILE = r"D:\17484\Documents\OneDrive\Desktop\XV-15叶片总成\XV-15 ASM.CATProduct"
    OUTPUT_DIR = r"D:\17484\Documents\OneDrive\Desktop\XV-15_Batch_Output"

    if not os.path.exists(SAMPLES_FILE):
        print(f"采样文件不存在: {SAMPLES_FILE}")
        raise SystemExit(1)
    if not os.path.exists(TEMPLATE_FILE):
        print(f"模板文件不存在: {TEMPLATE_FILE}")
        raise SystemExit(1)

    df = pd.read_csv(SAMPLES_FILE, encoding="utf-8-sig")
    modeler = CATIABatchModeler(TEMPLATE_FILE, OUTPUT_DIR)
    results = modeler.batch_process(df, save_catia=False, save_interval=20)
    results.to_csv(os.path.join(OUTPUT_DIR, "final_batch_results.csv"), index=False, encoding="utf-8-sig")
