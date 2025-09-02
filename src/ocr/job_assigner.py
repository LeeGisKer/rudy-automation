"""CLI tool to assign job IDs to receipt line items."""
import csv
from pathlib import Path


def assign_jobs(csv_path: str):
    """Stream rows from the CSV and write tagged output incrementally."""
    in_path = Path(csv_path)
    out_path = in_path.with_name(in_path.stem + '_tagged.csv')
    with open(in_path, newline='') as f_in, open(out_path, 'w', newline='') as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames or []
        if 'job_id' not in fieldnames:
            fieldnames.append('job_id')
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            print(f"Item: {row.get('item')} | Cost: {row.get('price')}")
            row['job_id'] = input('Enter job ID: ')
            writer.writerow(row)
    print(f'Saved tagged file to {out_path}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print('Usage: python job_assigner.py <receipt.csv>')
    else:
        assign_jobs(sys.argv[1])
