idf_component_register(SRCS "main.c" INCLUDE_DIRS "." REQUIRES esp_driver_gpio esp_driver_ledc esp_driver_pcnt esp_wifi esp_netif esp_event nvs_flash esp_timer lwip)
