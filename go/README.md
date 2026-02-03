# Synapse SDK for Go

This is the Go binding for the Synapse Core using CGO.

## Prerequisites

- **CGO Enabled**: `CGO_ENABLED=1`
- **Synapse Core**: The compiled core libraries (`libsynapse.so`, `libsynapse.dylib`, etc.) must be available in the `../clib/lib` directory relative to this package.

## Installation

```bash
go get github.com/your-org/synapse-sdk/go
```

## Usage

```go
package main

import (
	"fmt"
	"log"
	"time"

	"github.com/your-org/synapse-sdk/go"
)

type MyHandler struct{}

func (h *MyHandler) OnConnect(conn *synapse.Connection) {
	fmt.Println("Connected")
}

func (h *MyHandler) OnDisconnect(conn *synapse.Connection) {
	fmt.Println("Disconnected")
}

func (h *MyHandler) OnMessage(conn *synapse.Connection, reqID uint64, data []byte) {
	fmt.Printf("Received: %s\n", string(data))
	// Echo
	conn.Send(reqID, data)
}

func main() {
	cfg := synapse.Config{Port: 8080}
	node := synapse.NewNode(cfg, &MyHandler{})

	if err := node.Start(); err != nil {
		log.Fatal(err)
	}
	defer node.Stop()

	// Keep alive
	select {}
}
```
