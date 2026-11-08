#include "lidar_wifi.h"
#include <errno.h>
#include <inttypes.h>
#include <string.h>
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "LIDAR_WIFI";
typedef struct {
    uint32_t generation;
    size_t size;
    uint8_t bytes[1024];
} chunk_t;
static QueueHandle_t chunks;
static portMUX_TYPE lock = portMUX_INITIALIZER_UNLOCKED;
static lidar_wifi_stats_t stats;
static uint32_t generation;
static bool abort_stream;

lidar_wifi_stats_t lidar_wifi_stats(void)
{
    portENTER_CRITICAL(&lock);
    lidar_wifi_stats_t copy = stats;
    portEXIT_CRITICAL(&lock);
    return copy;
}

void lidar_wifi_mark_gap(void)
{
    portENTER_CRITICAL(&lock);
    ++stats.uart_gaps;
    abort_stream = true;
    portEXIT_CRITICAL(&lock);
}

void lidar_wifi_offer(const uint8_t *data, size_t size)
{
    if (!size) return;
    chunk_t chunk;
    portENTER_CRITICAL(&lock);
    bool enabled = stats.wifi_up && stats.client_up && !abort_stream;
    chunk.generation = generation;
    if (!enabled) stats.offline_bytes += size;
    portEXIT_CRITICAL(&lock);
    if (!enabled) return;
    if (size > sizeof(chunk.bytes)) {
        // Producer contract is <= 1024 bytes. Do not silently truncate a stream.
        lidar_wifi_mark_gap();
        return;
    }
    chunk.size = size;
    memcpy(chunk.bytes, data, size);
    if (xQueueSend(chunks, &chunk, 0) != pdTRUE) {
        portENTER_CRITICAL(&lock);
        stats.queue_dropped += size;
        abort_stream = true;
        portEXIT_CRITICAL(&lock);
    }
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        ESP_ERROR_CHECK(esp_wifi_connect());
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        const wifi_event_sta_disconnected_t *event = data;
        portENTER_CRITICAL(&lock);
        stats.wifi_up = false;
        abort_stream = true;
        portEXIT_CRITICAL(&lock);
        ESP_LOGW(TAG, "WiFi disconnected reason=%u; retrying", event->reason);
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *event = data;
        portENTER_CRITICAL(&lock);
        stats.wifi_up = true;
        portEXIT_CRITICAL(&lock);
        ESP_LOGI(TAG, "TCP_READY ip=" IPSTR " port=%d",
                 IP2STR(&event->ip_info.ip), CONFIG_LIDAR_TCP_PORT);
    }
}

static void tcp_task(void *arg)
{
    (void)arg;
    while (true) {
        while (!lidar_wifi_stats().wifi_up) vTaskDelay(pdMS_TO_TICKS(250));
        int server = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
        if (server < 0) { vTaskDelay(pdMS_TO_TICKS(1000)); continue; }
        int yes = 1;
        setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
        struct sockaddr_in address = {
            .sin_family = AF_INET,
            .sin_port = htons(CONFIG_LIDAR_TCP_PORT),
            .sin_addr.s_addr = htonl(INADDR_ANY),
        };
        if (bind(server, (struct sockaddr *)&address, sizeof(address)) < 0 ||
            listen(server, 1) < 0) {
            ESP_LOGE(TAG, "TCP listen failed errno=%d", errno);
            close(server);
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        ESP_LOGI(TAG, "Listening for one PC on TCP %d", CONFIG_LIDAR_TCP_PORT);
        while (lidar_wifi_stats().wifi_up) {
            fd_set readers;
            FD_ZERO(&readers);
            FD_SET(server, &readers);
            struct timeval poll = {.tv_sec = 0, .tv_usec = 250000};
            int ready = select(server + 1, &readers, NULL, NULL, &poll);
            if (ready < 0) break;
            if (!ready) continue;
            int client = accept(server, NULL, NULL);
            if (client < 0) continue;
            struct timeval timeout = {.tv_sec = 1, .tv_usec = 0};
            setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
            setsockopt(client, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));
            setsockopt(client, SOL_SOCKET, SO_KEEPALIVE, &yes, sizeof(yes));
            xQueueReset(chunks);
            portENTER_CRITICAL(&lock);
            uint32_t session = ++generation;
            abort_stream = false;
            stats.client_up = true;
            ++stats.connections;
            portEXIT_CRITICAL(&lock);
            ESP_LOGI(TAG, "PC connected session=%" PRIu32, session);
            chunk_t chunk;
            bool failed = false;
            while (!failed) {
                portENTER_CRITICAL(&lock);
                bool stop = abort_stream || !stats.wifi_up;
                portEXIT_CRITICAL(&lock);
                if (stop) break;
                // This lidar wiring is RX-only. Consume driver control bytes;
                // do not claim they are forwarded to an unconnected UART TX.
                uint8_t control[128];
                int received = recv(client, control, sizeof(control), MSG_DONTWAIT);
                if (received == 0 || (received < 0 && errno != EAGAIN && errno != EWOULDBLOCK)) break;
                if (xQueueReceive(chunks, &chunk, pdMS_TO_TICKS(100)) != pdTRUE) continue;
                if (chunk.generation != session) continue;
                size_t offset = 0;
                while (offset < chunk.size) {
                    int written = send(client, chunk.bytes + offset, chunk.size - offset, 0);
                    if (written <= 0) {
                        portENTER_CRITICAL(&lock);
                        ++stats.send_errors;
                        portEXIT_CRITICAL(&lock);
                        failed = true;
                        break;
                    }
                    offset += written;
                    portENTER_CRITICAL(&lock);
                    stats.sent += written;
                    portEXIT_CRITICAL(&lock);
                }
            }
            portENTER_CRITICAL(&lock);
            stats.client_up = false;
            portEXIT_CRITICAL(&lock);
            shutdown(client, SHUT_RDWR);
            close(client);
            ESP_LOGW(TAG, "PC disconnected; waiting for reconnect");
        }
        close(server);
    }
}

void lidar_wifi_init(void)
{
    chunks = xQueueCreate(32, sizeof(chunk_t));
    configASSERT(chunks);
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    // Credentials are supplied by the ignored local config, never printed.
    // Keep the runtime WiFi configuration in RAM, not an old saved profile.
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL));
    wifi_config_t config = {0};
    _Static_assert(sizeof(CONFIG_LIDAR_WIFI_SSID) - 1 <= 32, "SSID too long");
    _Static_assert(sizeof(CONFIG_LIDAR_WIFI_PASSWORD) - 1 <= 63, "Password too long");
    memcpy(config.sta.ssid, CONFIG_LIDAR_WIFI_SSID, sizeof(CONFIG_LIDAR_WIFI_SSID) - 1);
    memcpy(config.sta.password, CONFIG_LIDAR_WIFI_PASSWORD, sizeof(CONFIG_LIDAR_WIFI_PASSWORD) - 1);
    config.sta.threshold.authmode = sizeof(CONFIG_LIDAR_WIFI_PASSWORD) > 1 ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    config.sta.pmf_cfg.capable = true;
    config.sta.pmf_cfg.required = false;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));
    BaseType_t result = xTaskCreate(tcp_task, "lidar_tcp", 6144, NULL, 5, NULL);
    configASSERT(result == pdPASS);
}
