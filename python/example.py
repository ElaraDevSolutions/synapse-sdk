import sys
import time
import signal
from synapse import Node

def main():
    node = Node(8080)

    @node.on_connect
    def on_connect(conn_id):
        print(f"New connection: {conn_id}")

    @node.on_disconnect
    def on_disconnect(conn_id):
        print(f"Disconnected: {conn_id}")

    @node.on_message
    def on_message(conn_id, req_id, data):
        print(f"Received from {conn_id} (ReqID: {req_id}): {data.decode('utf-8')}")
        # Echo back
        node.send(conn_id, req_id, data)

    print("Starting python synapse node on :8080...")
    try:
        node.start()
        # Keep alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        node.stop()

if __name__ == "__main__":
    main()
