# Synapse SDK for Python

This is the Python binding for the Synapse Core.

## Installation

Ensure you have the core libraries (`libsynapse.so` or `libsynapse.dylib`) in `../clib/lib`.

```bash
pip install .
```

## Usage

```python
from synapse import Node

node = Node(8080)

@node.on_message
def handle_msg(conn_id, req_id, data):
    print(f"Received: {data}")
    node.send(conn_id, req_id, b"Ack")

node.start()
```
