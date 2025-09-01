"""CLI tool to assign job IDs to receipt line items."""
import csv
from pathlib import Path

def assign_jobs(csv_path: str):
    rows = list(csv.DictReader(open(csv_path)))
    for row in rows:
        print(f"Item: {row.get('item')} | Cost: {row.get('price')}")
        row['job_id'] = input('Enter job ID: ')
    out_path = Path(csv_path).with_name(Path(csv_path).stem + '_tagged.csv')
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved tagged file to {out_path}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        print('Usage: python job_assigner.py <receipt.csv>')
    else:
        assign_jobs(sys.argv[1])
