
import pandas as pd
import os

print("================================")
print("       CINEFINDER")
print("     Dataset Verification")
print("================================")

path = "dataset"

# Check dataset files
files = ["movies.csv", "ratings.csv", "tags.csv", "links.csv"]

for file in files:
    file_path = os.path.join(path, file)

    if os.path.exists(file_path):
        print(f"{file}: Found")
    else:
        print(f"{file}: Not Found")

# Load movie information
movies = pd.read_csv(f"{path}/movies.csv")

# Load only 10 ratings to avoid high memory usage
ratings = pd.read_csv(f"{path}/ratings.csv", nrows=10)

print("\nDataset Information")
print("-------------------")

print("Total Movies:", len(movies))
print("Rating Columns:", ratings.columns.tolist())

print("\nFirst 5 Movies:")
print(movies.head())

print("\nFirst 5 Ratings:")
print(ratings.head())

print("\nDataset verification completed!")
