import ctypes
import os
import sys
import platform
from enum import IntEnum
from typing import Callable, Optional

# --- Types & Enums ---

class LogLevel(IntEnum):
    NONE = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4

# Opaque pointer for context
class SynapseContext(ctypes.Structure):
    pass

SynapseContextPtr = ctypes.POINTER(SynapseContext)
SynapseConnID = ctypes.c_uint64

# Callbacks
# void (*synapse_on_message_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id, uint64_t req_id, const void *data, size_t len);
OnMessageFunc = ctypes.CFUNCTYPE(None, SynapseContextPtr, SynapseConnID, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t)

# void (*synapse_on_connect_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id);
OnConnectFunc = ctypes.CFUNCTYPE(None, SynapseContextPtr, SynapseConnID)

# void (*synapse_on_disconnect_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id);
OnDisconnectFunc = ctypes.CFUNCTYPE(None, SynapseContextPtr, SynapseConnID)

class SynapseConfig(ctypes.Structure):
    _fields_ = [
        ("host", ctypes.c_char_p),
        ("port", ctypes.c_uint16),
        ("backlog", ctypes.c_int),
        ("buffer_size", ctypes.c_uint32),
        ("max_events", ctypes.c_uint32),
        ("max_connections", ctypes.c_uint32),
        ("log_level", ctypes.c_int), # enum is int
    ]

class SynapseCallbacks(ctypes.Structure):
    _fields_ = [
        ("on_connect", OnConnectFunc),
        ("on_disconnect", OnDisconnectFunc),
        ("on_message", OnMessageFunc),
    ]

# --- Main Class ---

class Node:
    def __init__(self, port: int):
        self._port = port
        self._ctx = None
        self._callbacks_struct = None # Keep reference to avoid GC
        self._handlers = {} # Custom python handlers
        self._lib = self._load_library()
        
        # Define argtypes for safety
        self._lib.synapse_create.argtypes = [ctypes.POINTER(SynapseConfig), ctypes.POINTER(SynapseCallbacks)]
        self._lib.synapse_create.restype = SynapseContextPtr
        
        self._lib.synapse_start.argtypes = [SynapseContextPtr]
        self._lib.synapse_start.restype = ctypes.c_int
        
        self._lib.synapse_stop.argtypes = [SynapseContextPtr]
        self._lib.synapse_stop.restype = None
        
        self._lib.synapse_destroy.argtypes = [SynapseContextPtr]
        self._lib.synapse_destroy.restype = None

        self._lib.synapse_send.argtypes = [SynapseContextPtr, SynapseConnID, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
        self._lib.synapse_send.restype = ctypes.c_int

    def _load_library(self):
        # Locate the shared library relative to this file
        # Assuming structure:
        # synapse-sdk/
        #   python/synapse/core.py
        #   clib/lib/libsynapse.so
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to synapse-sdk root
        root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
        
        lib_name = "libsynapse.so"
        if platform.system() == "Darwin":
            lib_name = "libsynapse.dylib"
        elif platform.system() == "Windows":
            lib_name = "libsynapse.dll"
            
        lib_path = os.path.join(root_dir, "clib", "lib", lib_name)
        
        if not os.path.exists(lib_path):
            raise RuntimeError(f"Synapse library not found at {lib_path}. Please run sync/publish scripts.")
            
        return ctypes.CDLL(lib_path)

    # Decorator-style or assignment handlers
    def on_connect(self, func):
        self._handlers['connect'] = func
        return func

    def on_disconnect(self, func):
        self._handlers['disconnect'] = func
        return func

    def on_message(self, func):
        self._handlers['message'] = func
        return func

    def _c_on_connect(self, ctx, conn_id):
        if 'connect' in self._handlers:
            self._handlers['connect'](conn_id)

    def _c_on_disconnect(self, ctx, conn_id):
        if 'disconnect' in self._handlers:
            self._handlers['disconnect'](conn_id)

    def _c_on_message(self, ctx, conn_id, req_id, data_ptr, length):
        if 'message' in self._handlers:
            # Copy data from C pointer to bytes
            data = ctypes.string_at(data_ptr, length)
            self._handlers['message'](conn_id, req_id, data)

    def start(self):
        if self._ctx:
            return

        config = SynapseConfig()
        config.host = None # Bind all
        config.port = self._port
        config.backlog = 128
        config.buffer_size = 16 * 1024
        config.max_events = 64
        config.max_connections = 1000
        config.log_level = LogLevel.INFO

        # Create C callbacks needed by the struct
        # We must keep references to these CCallback objects so they aren't garbage collected
        self._c_connect_cb = OnConnectFunc(self._c_on_connect)
        self._c_disconnect_cb = OnDisconnectFunc(self._c_on_disconnect)
        self._c_message_cb = OnMessageFunc(self._c_on_message)

        callbacks = SynapseCallbacks()
        callbacks.on_connect = self._c_connect_cb
        callbacks.on_disconnect = self._c_disconnect_cb
        callbacks.on_message = self._c_message_cb
        self._callbacks_struct = callbacks # Keep Reference

        self._ctx = self._lib.synapse_create(ctypes.byref(config), ctypes.byref(callbacks))
        if not self._ctx:
            raise RuntimeError("Failed to create synapse context")

        res = self._lib.synapse_start(self._ctx)
        if res != 0:
            raise RuntimeError(f"Failed to start synapse: {res}")

    def stop(self):
        if self._ctx:
            self._lib.synapse_stop(self._ctx)
            self._lib.synapse_destroy(self._ctx)
            self._ctx = None

    def send(self, conn_id: int, req_id: int, data: bytes):
        if not self._ctx:
            raise RuntimeError("Node is not running")
        
        res = self._lib.synapse_send(self._ctx, conn_id, req_id, data, len(data))
        if res != 0:
            raise RuntimeError(f"Failed to send data: {res}")
