idf_component_register(SRCS "lidar_uart.c" "lidar_wifi.c" INCLUDE_DIRS "."
    REQUIRES driver esp_driver_uart esp_driver_gpio esp_timer esp_wifi esp_event esp_netif nvs_flash lwip)
