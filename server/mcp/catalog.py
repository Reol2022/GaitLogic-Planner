"""Single source for public MCP discovery metadata and accepted arguments."""
PRODUCT_VERSION = '0.16.8'
MCP_SERVER_VERSION = PRODUCT_VERSION + '-facts-v3.2'
TOOL_ARGUMENTS = {
    'get_today_plan': frozenset(),
    'get_recent_training': frozenset({'days', 'limit', 'cursor', 'start_date', 'end_date'}),
    'get_runner_state': frozenset(),
    'retrieve_training_knowledge': frozenset({'query', 'top_k', 'categories', 'tags', 'language'}),
    'get_training_detail': frozenset({'record_ref', 'activity_ref'}),
    'get_recovery_trend': frozenset({'days', 'start_date', 'end_date'}),
}
