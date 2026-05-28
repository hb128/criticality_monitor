from .mapping import MapBuilder

def render_map(result: PipelineResult, config: PipelineConfig) -> str:
    """
    Pure function: Generate HTML map from pipeline result.
    
    Args:
        result: Pipeline computation result
        config: Pipeline configuration
        
    Returns:
        HTML string containing the interactive map
    """
    map_builder = MapBuilder()
    m = map_builder.build(
        filtered=result.filtered,
        outliers=result.outliers,
        path_indices=result.path_indices,
        bounds_expand=config.bounds_expand,
        path_df=result.path_df,
        segment_metrics=result.segment_metrics,
    )
    return m.get_root().render()