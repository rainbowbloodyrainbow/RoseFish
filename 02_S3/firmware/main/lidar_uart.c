#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "lidar_wifi.h"

static const char *TAG = "LIDAR_RX";
static const uart_port_t PORT = UART_NUM_1;

void app_main(void)
{
    if (!GPIO_IS_VALID_GPIO(CONFIG_LIDAR_RX_GPIO)) {
        ESP_LOGE(TAG, "Invalid RX GPIO %d", CONFIG_LIDAR_RX_GPIO);
        return;
    }
    const uart_config_t config = {
        .baud_rate = CONFIG_LIDAR_UART_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    QueueHandle_t queue;
    ESP_ERROR_CHECK(uart_driver_install(PORT, 16384, 0, 64, &queue, 0));
    ESP_ERROR_CHECK(uart_param_config(PORT, &config));
    // UART0 remains the USB-to-serial debug console. No lidar TX is assigned.
    ESP_ERROR_CHECK(uart_set_pin(PORT, UART_PIN_NO_CHANGE,
                               CONFIG_LIDAR_RX_GPIO,
                               UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(gpio_set_pull_mode(CONFIG_LIDAR_RX_GPIO, GPIO_FLOATING));
    ESP_LOGI(TAG, "UART1 RX=GPIO%d baud=%d 8N1; raw WiFi TCP server",
             CONFIG_LIDAR_RX_GPIO, CONFIG_LIDAR_UART_BAUD);
    ESP_LOGI(TAG, "Console is UART0 at 115200. AA55 is a header candidate, not a checksum test.");
    lidar_wifi_init();

    uint64_t total = 0, last_total = 0, headers = 0;
    uint32_t fifo_overflows = 0, ring_overflows = 0;
    uint32_t frame_errors = 0, parity_errors = 0, breaks = 0;
    uint8_t buffer[1024], sample[32];
    size_t sample_size = 0;
    bool sample_printed = false, previous_aa = false;
    int64_t last_report = esp_timer_get_time();
    const int64_t started = last_report;
    uart_event_t event;

    while (true) {
        if (xQueueReceive(queue, &event, pdMS_TO_TICKS(50)) == pdTRUE) {
            switch (event.type) {
            case UART_DATA: {
                size_t remaining = event.size;
                while (remaining > 0) {
                    size_t request = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
                    int count = uart_read_bytes(PORT, buffer, request, 0);
                    if (count <= 0) {
                        break;
                    }
                    remaining -= (size_t)count;
                    total += (uint64_t)count;
                    lidar_wifi_offer(buffer, (size_t)count);
                    for (int i = 0; i < count; ++i) {
                        if (previous_aa && buffer[i] == 0x55) {
                            ++headers;
                        }
                        previous_aa = buffer[i] == 0xAA;
                        if (sample_size < sizeof(sample)) {
                            sample[sample_size++] = buffer[i];
                        }
                    }
                }
                break;
            }
            case UART_FIFO_OVF:
            case UART_BUFFER_FULL:
                if (event.type == UART_FIFO_OVF) {
                    ++fifo_overflows;
                } else {
                    ++ring_overflows;
                }
                ESP_ERROR_CHECK(uart_flush_input(PORT));
                xQueueReset(queue);
                previous_aa = false; // A discarded gap cannot form a header.
                lidar_wifi_mark_gap();
                break;
            case UART_FRAME_ERR:
                ++frame_errors;
                lidar_wifi_mark_gap();
                previous_aa = false;
                break;
            case UART_PARITY_ERR:
                ++parity_errors;
                lidar_wifi_mark_gap();
                previous_aa = false;
                break;
            case UART_BREAK:
                ++breaks;
                lidar_wifi_mark_gap();
                previous_aa = false;
                break;
            default:
                break;
            }
        }
        int64_t now = esp_timer_get_time();
        if (now - last_report >= 1000000) {
            uint64_t bytes_per_second = (total - last_total) * 1000000ULL /
                                        (uint64_t)(now - last_report);
            ESP_LOGI(TAG, "RX bytes/s=%" PRIu64 " total=%" PRIu64
                     " AA55=%" PRIu64 " fifo_ovf=%" PRIu32
                     " ring_ovf=%" PRIu32 " frame_err=%" PRIu32
                     " parity_err=%" PRIu32 " breaks=%" PRIu32,
                     bytes_per_second, total, headers, fifo_overflows,
                     ring_overflows, frame_errors, parity_errors, breaks);
            if (!sample_printed && sample_size > 0) {
                ESP_LOGI(TAG, "First received bytes:");
                ESP_LOG_BUFFER_HEX_LEVEL(TAG, sample, sample_size, ESP_LOG_INFO);
                sample_printed = true;
            }
            if (total == 0 && now - started >= 5000000) {
                ESP_LOGW(TAG, "No UART data: check lidar power/motor, common GND and TX -> RX GPIO.");
            }
            last_total = total;
            last_report = now;
            lidar_wifi_stats_t wifi = lidar_wifi_stats();
            ESP_LOGI(TAG, "NET wifi=%d client=%d sent=%" PRIu64
                     " offline=%" PRIu64 " queue_drop=%" PRIu64
                     " send_err=%" PRIu32 " uart_gaps=%" PRIu32,
                     wifi.wifi_up, wifi.client_up, wifi.sent, wifi.offline_bytes,
                     wifi.queue_dropped, wifi.send_errors, wifi.uart_gaps);
        }
    }
}
