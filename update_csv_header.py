import pandas as pd
import os

CSV_FILE = '/home/aigen/gagan_netra/gagan_netra_flight_log.csv'

def fix_csv_headers(file_path):
    if os.path.exists(file_path):
        # 1. Read the existing data
        df = pd.read_csv(file_path)
        
        # 2. Define the mapping (Old Name: New Name)
        mapping = {
            'fire_classification': 'fire_source',
            'gps_lat': 'latitude',     # Standardizing GPS names if needed
            'gps_lon': 'longitude',
            'gps_alt': 'altitude'
        }
        
        # 3. Rename columns that exist in the file
        df.rename(columns=mapping, inplace=True)
        
        # 4. Overwrite the file with the new headers and original data
        df.to_csv(file_path, index=False)
        print(f"? Headers updated successfully in {file_path}")
    else:
        print("? File not found. Check the path.")

if __name__ == "__main__":
    fix_csv_headers(CSV_FILE)
