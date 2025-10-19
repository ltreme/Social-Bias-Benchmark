import csv
import sys
import uuid
from pathlib import Path


def add_uuid_to_csv(input_path, output_path=None):
    input_path = Path(input_path)
    output_path = output_path or input_path.with_name(
        input_path.stem + "_with_uuid.csv"
    )

    with open(input_path, "r", encoding="utf-8", newline="") as infile:
        reader = list(csv.DictReader(infile))
        fieldnames = reader[0].keys() if reader else []
        needs_uuid = "uuid" not in fieldnames

        if needs_uuid:
            fieldnames = ["uuid"] + list(fieldnames)
        else:
            fieldnames = list(fieldnames)  # force list (csv requires this)

    with open(output_path, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            if needs_uuid or not row.get("uuid"):
                row["uuid"] = str(uuid.uuid4())
            writer.writerow(row)

    print(f"Done. Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_uuid_to_csv.py <input.csv> [output.csv]")
    else:
        add_uuid_to_csv(*sys.argv[1:])
