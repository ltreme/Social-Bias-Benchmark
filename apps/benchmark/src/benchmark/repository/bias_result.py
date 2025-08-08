import csv
import os
from datetime import datetime


class BiasResultRepository:
    """
    Append-only CSV writer for benchmark results.
    Context-manager compatible: ensures file is opened and closed properly.
    """

    def __init__(self, model_name: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model_name = model_name.replace(" ", "_")
        self.dir_path = f"out/{safe_model_name}"
        self.path = os.path.join(self.dir_path, f"{timestamp}.csv")

        # Ensure output directory exists
        os.makedirs(self.dir_path, exist_ok=True)

        self._fh = None
        self._writer = None
        self._fieldnames = ["question_uuid", "persona_uuid", "answer_raw"]

    def __enter__(self):
        """Open file and prepare writer when entering 'with' block."""
        self._fh = open(self.path, mode="a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=self._fieldnames)
        self._writer.writeheader()
        return self

    def write_one(self, question_uuid: str, persona_uuid: str, answer_raw: str):
        """Write a single result row and flush immediately."""
        if self._writer is None:
            raise RuntimeError(
                "File not opened. Use 'with BiasResultRepository(...) as repo'."
            )
        self._writer.writerow(
            {
                "question_uuid": question_uuid,
                "persona_uuid": persona_uuid,
                "answer_raw": answer_raw,
            }
        )
        self._fh.flush()

    def __exit__(self, exc_type, exc_value, traceback):
        """Ensure file is closed on exit from 'with' block."""
        if self._fh:
            self._fh.close()
            self._fh = None
            self._writer = None
