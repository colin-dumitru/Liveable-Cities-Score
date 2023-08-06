import json
import warnings
import os
import sys
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(__file__) + "/../")

from lcs.plot import plot_heatmap
from lcs.score import LCSQueryEngine

warnings.filterwarnings('ignore')


CONFIGS = [
    # \"../config/RO/Bucharest/Bucharest.json",
    # "../config/RO/Iasi/Iasi.json\",
    # "./config/RO/Cluj/Cluj-Napoca.json",
    # "./config/RO/Timis/Timisoara.json",
    # "./config/RO/Dolj/Craiova.json",
    "./config/RO/Constanta/Constanta.json"
]

if __name__ == "__main__":
    for config_path in CONFIGS:
        print(f"Generating for {config_path}")

        config = json.load(open(config_path, 'r'))
        df_residential = LCSQueryEngine(config).query_features_with_lcs()
        plot_heatmap(config, df_residential, figsize=(16, 16))
        plt.savefig(f"./figures/{config['name']}.png")
