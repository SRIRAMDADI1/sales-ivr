import os

# Keep pytest from binding the metrics port.
os.environ["METRICS_PORT"] = "0"
