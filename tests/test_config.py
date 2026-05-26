from src import config


def test_expected_config_constants_exist():
    assert config.NAVIGATE_LA_BASE_URL.endswith("/NavigateLA/MapServer")
    assert config.AOI_FALLBACK_BBOX == (-118.325, 34.047, -118.280, 34.085)
    assert "sidewalks" in config.ARCGIS_LAYERS
    assert config.ARCGIS_LAYERS["sidewalks"].layer_id == 323
    assert "needs_review" in config.ALLOWED_LABELS

