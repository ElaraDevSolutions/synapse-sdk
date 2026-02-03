package synapse

/*
#cgo CFLAGS: -I../clib/include
#cgo LDFLAGS: -L../clib/lib -lsynapse
#cgo linux LDFLAGS: -Wl,-rpath,$ORIGIN/../clib/lib
#cgo darwin LDFLAGS: -Wl,-rpath,@loader_path/../clib/lib

#include <stdlib.h>
#include <stdint.h>
#include "synapse.h"

extern void goOnMessage(synapse_context_t *ctx, uint64_t conn_id, uint64_t req_id, void *data, size_t len);
extern void goOnConnect(synapse_context_t *ctx, uint64_t conn_id);
extern void goOnDisconnect(synapse_context_t *ctx, uint64_t conn_id);

static synapse_callbacks_t get_callbacks() {
    synapse_callbacks_t cb;
    cb.on_message = (synapse_on_message_cb)goOnMessage;
    cb.on_connect = (synapse_on_connect_cb)goOnConnect;
    cb.on_disconnect = (synapse_on_disconnect_cb)goOnDisconnect;
    return cb;
}
*/
import "C"
import (
	"fmt"
	"sync"
	"unsafe"
)

// Config holds configuration for a Synapse node
type Config struct {
	Port int
}

// Handler interface for incoming messages
// Changed to use an ID wrapper instead of net.Conn because we are using the C Core
type Handler interface {
	OnMessage(conn *Connection, reqID uint64, data []byte)
	OnConnect(conn *Connection)
	OnDisconnect(conn *Connection)
}

// Connection represents a connection in the C core
type Connection struct {
	node *Node
	id   uint64
}

// Send sends a message through the connection
func (c *Connection) Send(reqID uint64, data []byte) error {
	return c.node.Send(c.id, reqID, data)
}

// Node represents a Synapse application node (Server & Client capability)
type Node struct {
	config  Config
	handler Handler
	ctx     *C.synapse_context_t
	running bool
}

// Global registry to map C pointers back to Go objects
var (
	nodeRegistry = make(map[*C.synapse_context_t]*Node)
	registryMu   sync.RWMutex
)

// NewNode creates a new Synapse node
func NewNode(config Config, handler Handler) *Node {
	return &Node{
		config:  config,
		handler: handler,
	}
}

// Start begins listening for incoming connections
func (n *Node) Start() error {
	registryMu.Lock()
	defer registryMu.Unlock()

	cConfig := C.synapse_config_t{
		port:            C.uint16_t(n.config.Port),
		backlog:         128,
		buffer_size:     1024 * 16,
		max_events:      64,
		max_connections: 1000,
		log_level:       C.SYNAPSE_LOG_INFO,
	}

	callbacks := C.get_callbacks()
	n.ctx = C.synapse_create(&cConfig, &callbacks)
	if n.ctx == nil {
		return fmt.Errorf("failed to create synapse context")
	}

	nodeRegistry[n.ctx] = n

	res := C.synapse_start(n.ctx)
	if res != 0 {
		delete(nodeRegistry, n.ctx)
		return fmt.Errorf("failed to start synapse: %d", res)
	}

	n.running = true
	return nil
}

// Stop closes the listener
func (n *Node) Stop() {
	if n.ctx != nil {
		C.synapse_stop(n.ctx)
		C.synapse_destroy(n.ctx)

		registryMu.Lock()
		delete(nodeRegistry, n.ctx)
		registryMu.Unlock()

		n.ctx = nil
	}
	n.running = false
}

// Send sends a message to a connection ID
func (n *Node) Send(connID uint64, reqID uint64, data []byte) error {
	if !n.running || n.ctx == nil {
		return fmt.Errorf("node not running")
	}

	var cData unsafe.Pointer
	if len(data) > 0 {
		cData = unsafe.Pointer(&data[0])
	}

	// C.synapse_send returns int (0 success)
	res := C.synapse_send(n.ctx, C.uint64_t(connID), C.uint64_t(reqID), cData, C.size_t(len(data)))
	if res != 0 {
		return fmt.Errorf("send failed: %d", res)
	}
	return nil
}

//export goOnMessage
func goOnMessage(ctx *C.synapse_context_t, connID C.uint64_t, reqID C.uint64_t, data unsafe.Pointer, length C.size_t) {
	registryMu.RLock()
	node, ok := nodeRegistry[ctx]
	registryMu.RUnlock()

	if !ok || node.handler == nil {
		return
	}

	// Copy data to Go slice
	goData := C.GoBytes(data, C.int(length))

	conn := &Connection{node: node, id: uint64(connID)}
	node.handler.OnMessage(conn, uint64(reqID), goData)
}

//export goOnConnect
func goOnConnect(ctx *C.synapse_context_t, connID C.uint64_t) {
	registryMu.RLock()
	node, ok := nodeRegistry[ctx]
	registryMu.RUnlock()

	if !ok || node.handler == nil {
		return
	}

	conn := &Connection{node: node, id: uint64(connID)}
	node.handler.OnConnect(conn)
}

//export goOnDisconnect
func goOnDisconnect(ctx *C.synapse_context_t, connID C.uint64_t) {
	registryMu.RLock()
	node, ok := nodeRegistry[ctx]
	registryMu.RUnlock()

	if !ok || node.handler == nil {
		return
	}

	conn := &Connection{node: node, id: uint64(connID)}
	node.handler.OnDisconnect(conn)
}
