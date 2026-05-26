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

If a dependency conflict appears on a future machine, prefer creating a fresh virtual environment and installing from `requirements.txt`. If a package lower bound needs to be relaxed for platform compatibility, document the exact package, attempted version, error, and replacement here.
