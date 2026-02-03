#ifndef SYNAPSE_H
#define SYNAPSE_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// --- Configuration ---

typedef enum {
    SYNAPSE_LOG_NONE = 0,
    SYNAPSE_LOG_ERROR,
    SYNAPSE_LOG_WARN,
    SYNAPSE_LOG_INFO,
    SYNAPSE_LOG_DEBUG
} synapse_log_level_t;

typedef struct {
    const char *host;
    uint16_t port;
    int backlog;
    
    // Performance Tuning
    uint32_t buffer_size;        // Internal buffer size per connection
    uint32_t max_events;
    uint32_t max_connections;
    
    synapse_log_level_t log_level;
} synapse_config_t;

// --- Context & Types ---

typedef struct synapse_context synapse_context_t;
typedef uint64_t synapse_conn_id_t;

// --- Callbacks ---

// req_id matches requests to responses for parallel processing.
// If req_id is provided in send, it is sent on wire. Check protocol details.
typedef void (*synapse_on_message_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id, uint64_t req_id, const void *data, size_t len);
typedef void (*synapse_on_connect_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id);
typedef void (*synapse_on_disconnect_cb)(synapse_context_t *ctx, synapse_conn_id_t conn_id);

typedef struct {
    synapse_on_connect_cb on_connect;
    synapse_on_disconnect_cb on_disconnect;
    synapse_on_message_cb on_message;
} synapse_callbacks_t;

// --- API ---

synapse_context_t *synapse_create(const synapse_config_t *config, const synapse_callbacks_t *callbacks);
int synapse_start(synapse_context_t *ctx);
void synapse_stop(synapse_context_t *ctx);
void synapse_destroy(synapse_context_t *ctx);

// Send message with a request ID. 
// Uses a 12-byte header: [Length (4b)][ReqID (8b)][Payload...]
int synapse_send(synapse_context_t *ctx, synapse_conn_id_t conn_id, uint64_t req_id, const void *data, size_t len);

#ifdef __cplusplus
}
#endif

#endif // SYNAPSE_H
