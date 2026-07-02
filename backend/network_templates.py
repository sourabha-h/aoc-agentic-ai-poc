"""Minimal node templates for the mock network."""

from __future__ import annotations

NODES = [
    {
        "node_id": "billing_server",
        "display_name": "Oracle BRM Billing Server",
        "dependencies": ["oracle_database", "subscriber_platform"],
    },
    {
        "node_id": "oracle_database",
        "display_name": "Oracle Database",
        "dependencies": ["archive_storage"],
    },
    {
        "node_id": "archive_storage",
        "display_name": "Archive and Backup Storage",
        "dependencies": [],
    },
    {
        "node_id": "order_platform",
        "display_name": "Order Activation Platform",
        "dependencies": ["oracle_database", "subscriber_platform"],
    },
    {
        "node_id": "subscriber_platform",
        "display_name": "Subscriber Data Platform",
        "dependencies": ["oracle_database"],
    },
    {
        "node_id": "sms_gateway",
        "display_name": "SMS Gateway",
        "dependencies": ["api_gateway"],
    },
    {
        "node_id": "api_gateway",
        "display_name": "API Routing Gateway",
        "dependencies": ["order_platform"],
    },
]

