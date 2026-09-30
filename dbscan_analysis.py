import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import DBSCAN

# Read vehicle data
data = pd.read_csv("clean_vehicle_data.csv")

# Select GPS coordinates
coordinates = data[["latitude", "longitude"]]

# DBSCAN
model = DBSCAN(eps=0.003, min_samples=3)
data["cluster"] = model.fit_predict(coordinates)
data.to_csv("clustered_vehicle_data.csv", index=False)

print("\nClustered data saved to clustered_vehicle_data.csv")

# Display results
print("\nVehicle Data with Clusters:")
print(data.head(20))

# Cluster information
print("\nCluster Counts:")
print(data["cluster"].value_counts().sort_index())

# Speed analysis
print("\nSpeed Analysis:")
print("Average speed:", round(data["speed"].mean(), 2))
print("Maximum speed:", data["speed"].max())
print("Minimum speed:", data["speed"].min())

# Average speed for each cluster
print("\nAverage Speed by Cluster:")
cluster_speed = data.groupby("cluster")["speed"].mean().round(2)

print(cluster_speed)

print("\nTraffic Status:")

for cluster, speed in cluster_speed.items():

    if speed < 40:
        status = "High Traffic"
    elif speed < 60:
        status = "Medium Traffic"
    else:
        status = "Low Traffic"

        print("Cluster", cluster, ":", status)


# Save traffic summary
summary = []

for cluster, speed in cluster_speed.items():

    if speed < 40:
        status = "High Traffic"
    elif speed < 60:
        status = "Medium Traffic"
    else:
        status = "Low Traffic"

    summary.append([cluster, speed, status])

summary_data = pd.DataFrame(
    summary,
    columns=["Cluster", "Average Speed", "Traffic Status"]
)

summary_data.to_csv("traffic_summary.csv", index=False)

print("\nTraffic summary saved to traffic_summary.csv")
# Plot clusters

# Plot clusters
plt.figure(figsize=(8, 6))

plt.scatter(
    data["longitude"],
    data["latitude"],
    c=data["cluster"],
    cmap="viridis",
    s=50
)

plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.title("Urban Traffic Zones Detected using DBSCAN")
plt.colorbar(label="Cluster")

plt.show()
# Average speed chart
plt.figure(figsize=(8, 5))

plt.bar(
    cluster_speed.index.astype(str),
    cluster_speed.values
)

plt.xlabel("Traffic Cluster")
plt.ylabel("Average Speed")
plt.title("Average Speed by Traffic Cluster")

plt.show()