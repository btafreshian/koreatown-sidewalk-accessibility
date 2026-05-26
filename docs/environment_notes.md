# Environment Notes

Target Python version: Python 3.11 or newer.

The project uses the dependency lower bounds requested in the brief:

- `geopandas>=1.1.3`
- `pandas>=3.0.3`
- `shapely>=2.1.2`
- `pyogrio>=0.12.1`
- `requests>=2.32`
- `pyproj>=3.7`
- `matplotlib>=3.9`
- `networkx>=3.4`
- `folium>=0.17`
- `pytest>=8`

The current machine was inspected with Python 3.13.7. Before installing the project dependencies, the base interpreter had `pandas`, `requests`, `networkx`, and `pytest`, but did not have `geopandas`, `shapely`, `pyogrio`, `pyproj`, `matplotlib`, or `folium`.

A local `.venv` was created and successfully installed the requested dependency bounds, including `pandas==3.0.3`, `geopandas==1.1.3`, `shapely==2.1.2`, and `pyogrio==0.12.1`.

If a dependency conflict appears on a future machine, prefer creating a fresh virtual environment and installing from `requirements.txt`. If a package lower bound needs to be relaxed for platform compatibility, document the exact package, attempted version, error, and replacement here.
