import pandas as pd

# Read the existing vehicle data
data = pd.read_csv("vehicle_data.csv")

# Keep only the new 3-zone data
clean_data = data[
    (
        (data["latitude"] >= 28.648) &
        (data["latitude"] <= 28.652) &
        (data["longitude"] >= 77.198) &
        (data["longitude"] <= 77.202)
    )
    |
    (
        (data["latitude"] >= 28.668) &
        (data["latitude"] <= 28.672) &
        (data["longitude"] >= 77.208) &
        (data["longitude"] <= 77.212)
    )
    |
    (
        (data["latitude"] >= 28.688) &
        (data["latitude"] <= 28.692) &
        (data["longitude"] >= 77.188) &
        (data["longitude"] <= 77.192)
    )
]

# Save the clean dataset
clean_data.to_csv("clean_vehicle_data.csv", index=False)

print("Clean dataset created!")
print("Number of records:", len(clean_data))
print("\nFirst 10 records:")
print(clean_data.head(10))