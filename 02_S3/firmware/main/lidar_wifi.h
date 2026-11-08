#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    bool wifi_up;
    bool client_up;
    uint64_t sent;
    uint64_t offline_bytes;
    uint64_t queue_dropped;
    uint32_t send_errors;
    uint32_t uart_gaps;
    uint32_t connections;
} lidar_wifi_stats_t;

void lidar_wifi_init(void);
void lidar_wifi_offer(const uint8_t *data, size_t size);
void lidar_wifi_mark_gap(void);
lidar_wifi_stats_t lidar_wifi_stats(void);
