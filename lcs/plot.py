import matplotlib.pyplot as plt
import matplotlib as mpl
import osmnx as ox

def plot_heatmap(config, df_residential, figsize=(12, 12)):
    G = ox.graph_from_place(config['placeId'], network_type='all', simplify=True)
    G = ox.project_graph(G)
    fig = plt.figure(figsize=figsize)

    cmap = mpl.colormaps['RdYlGn']
    plt.scatter(
        df_residential.centroid.x, 
        df_residential.centroid.y, 
        color=cmap((df_residential['lcs_perc'] / 100)), 
        alpha=0.5, 
        s=50)

    ox.plot_graph(
        G, 
        show=False, 
        close=False, 
        ax=plt.gca(), 
        edge_color='black', node_color='black', node_size=0, edge_alpha=0.1, node_alpha=0.1)

    plt.set_cmap('RdYlGn')
    cbar = plt.colorbar(ticks=[0, 1], shrink=0.3, orientation='horizontal', label='LCS Range', anchor=(0.0, 2), pad=0)
    cbar.ax.set_xticklabels(['0%', '100%'])

    plt.title(f"{config['name']} ({df_residential['lcs_perc'].mean():.2f}%)", fontsize=20)

    # plt.show()