#include <stdio.h>
#include <string.h>
#include <math.h>
#include <inttypes.h>
#include <unistd.h>
#include <sys/socket.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/pulse_cnt.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "lwip/inet.h"
#include "link_private.h"
#define LIMIT 350
static const int pins[]={13,15,25,14};
static pcnt_unit_handle_t enc[2];
static portMUX_TYPE mux=portMUX_INITIALIZER_UNLOCKED;
static bool connected=false,fault=false;
static float target[2],pps[2],pwm[2];
static int64_t ticks[2],command_us;
static unsigned ack,boot_id;
static char mode='S';
static void motor(int i,float value){
    value=fmaxf(-LIMIT,fminf(LIMIT,value));
    int on=2*i+(value<0),off=2*i+(value>=0);
    esp_err_t e=ledc_set_duty(LEDC_LOW_SPEED_MODE,off,0);
    e|=ledc_update_duty(LEDC_LOW_SPEED_MODE,off);
    e|=ledc_set_duty(LEDC_LOW_SPEED_MODE,on,(uint32_t)fabsf(value));
    e|=ledc_update_duty(LEDC_LOW_SPEED_MODE,on);
    if(e!=ESP_OK){fault=true;for(int k=0;k<4;k++){ledc_set_duty(LEDC_LOW_SPEED_MODE,k,0);ledc_update_duty(LEDC_LOW_SPEED_MODE,k);}}
}
static void encoder(int i,int a,int b){
    pcnt_unit_config_t u={.high_limit=32767,.low_limit=-32768,.flags.accum_count=true};
    ESP_ERROR_CHECK(pcnt_new_unit(&u,&enc[i]));
    pcnt_glitch_filter_config_t f={.max_glitch_ns=1000};ESP_ERROR_CHECK(pcnt_unit_set_glitch_filter(enc[i],&f));
    pcnt_chan_config_t c={.edge_gpio_num=a,.level_gpio_num=b};pcnt_channel_handle_t ch;
    ESP_ERROR_CHECK(pcnt_new_channel(enc[i],&c,&ch));
    ESP_ERROR_CHECK(pcnt_channel_set_edge_action(ch,PCNT_CHANNEL_EDGE_ACTION_INCREASE,PCNT_CHANNEL_EDGE_ACTION_HOLD));
    ESP_ERROR_CHECK(pcnt_channel_set_level_action(ch,PCNT_CHANNEL_LEVEL_ACTION_KEEP,PCNT_CHANNEL_LEVEL_ACTION_INVERSE));
    ESP_ERROR_CHECK(pcnt_unit_add_watch_point(enc[i],32767));ESP_ERROR_CHECK(pcnt_unit_add_watch_point(enc[i],-32768));
    ESP_ERROR_CHECK(pcnt_unit_enable(enc[i]));ESP_ERROR_CHECK(pcnt_unit_clear_count(enc[i]));ESP_ERROR_CHECK(pcnt_unit_start(enc[i]));
}
static void control(void *unused){
    int prev[2]={0},direction[2]={0};float integral[2]={0};int64_t quiet_until[2]={0};
    int64_t before=esp_timer_get_time();TickType_t wake=xTaskGetTickCount();
    for(;;){
        vTaskDelayUntil(&wake,pdMS_TO_TICKS(20));int64_t now=esp_timer_get_time();float dt=(now-before)*1e-6f;before=now;
        portENTER_CRITICAL(&mux);bool run=connected&&!fault&&command_us&&now-command_us<300000;float ref[2]={target[0],target[1]};char m=mode;portEXIT_CRITICAL(&mux);
        if(dt<=0||dt>.1){run=false;fault=true;}
        for(int i=0;i<2;i++){
            int raw=0;if(pcnt_unit_get_count(enc[i],&raw)!=ESP_OK){fault=true;run=false;}
            int32_t d=(int32_t)((uint32_t)raw-(uint32_t)prev[i]);prev[i]=raw;
            float measured=(i?-1.f:1.f)*d/fmaxf(dt,.001f),out=0;
            if(run&&ref[i]!=0){
                int sign=ref[i]>0?1:-1;
                if(direction[i]&&sign!=direction[i]){quiet_until[i]=now+250000;integral[i]=0;}
                direction[i]=sign;
                if(now>=quiet_until[i]){
                    if(m=='P'){out=ref[i];integral[i]=0;}
                    else{
                        float error=ref[i]-measured,trial=fmaxf(-2500,fminf(2500,integral[i]+error*dt));
                        float candidate=.035f*error+.12f*trial;
                        if(fabsf(candidate)<LIMIT||candidate*error<0)integral[i]=trial;
                        out=.035f*error+.12f*integral[i];if(out*sign<0)out=0;
                        if(measured*sign<-200&&fabsf(pwm[i])>50){fault=true;out=0;}
                    }
                }
            }else integral[i]=0;
            if(fault) { out=0; }
            motor(i,out);
            portENTER_CRITICAL(&mux);ticks[i]+=d;pps[i]=measured;pwm[i]=fmaxf(-LIMIT,fminf(LIMIT,out));portEXIT_CRITICAL(&mux);
        }
    }
}
static void event(void *arg,esp_event_base_t base,int32_t id,void *data){
    if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_START)esp_wifi_connect();
    if(base==WIFI_EVENT&&id==WIFI_EVENT_STA_DISCONNECTED){portENTER_CRITICAL(&mux);connected=false;command_us=0;portEXIT_CRITICAL(&mux);esp_wifi_connect();}
    if(base==IP_EVENT&&id==IP_EVENT_STA_GOT_IP){ip_event_got_ip_t *p=data;portENTER_CRITICAL(&mux);connected=true;command_us=0;portEXIT_CRITICAL(&mux);ESP_LOGI("D0WD_LINK","WiFi IP=" IPSTR,IP2STR(&p->ip_info.ip));}
}
static void network(void *unused){
    int s=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);if(s<0){fault=true;vTaskDelete(NULL);return;}
    struct sockaddr_in local={.sin_family=AF_INET,.sin_port=htons(5005),.sin_addr.s_addr=htonl(INADDR_ANY)};
    if(bind(s,(struct sockaddr*)&local,sizeof(local))<0){fault=true;close(s);vTaskDelete(NULL);return;}
    struct timeval timeout={.tv_sec=0,.tv_usec=2000};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    struct sockaddr_in host={.sin_family=AF_INET,.sin_port=htons(9999)};inet_pton(AF_INET,SERVER_IP,&host.sin_addr);
    int64_t sent=0,logged=0;char buf[512];
    for(;;){
        struct sockaddr_in from;socklen_t size=sizeof(from);int n=recvfrom(s,buf,sizeof(buf)-1,0,(struct sockaddr*)&from,&size);int64_t now=esp_timer_get_time();
        if(n>0&&from.sin_addr.s_addr==host.sin_addr.s_addr&&from.sin_port==host.sin_port){
            buf[n]=0;char kind,key[40],extra;unsigned seq;double x,y;
            if(sscanf(buf,"%c %39s %u %lf %lf %c",&kind,key,&seq,&x,&y,&extra)==5&&!strcmp(key,LINK_TOKEN)&&isfinite(x)&&isfinite(y)&&((kind=='C'&&fabs(x)<=.05&&fabs(y)<=.6)||(kind=='P'&&fabs(x)<=LIMIT&&fabs(y)<=LIMIT))){
                portENTER_CRITICAL(&mux);
                if(seq>ack||now-command_us>2000000){ack=seq;command_us=now;mode=kind;double k=10200.0/(3.141592653589793*.04730);target[0]=kind=='C'?(x-y*.13340*.5)*k:x;target[1]=kind=='C'?(x+y*.13340*.5)*k:y;}
                portEXIT_CRITICAL(&mux);
            }
        }
        if(connected&&now-sent>=50000){
            int64_t l,r;float sl,sr,pl,pr;unsigned sequence;
            portENTER_CRITICAL(&mux);l=ticks[0];r=ticks[1];sl=pps[0];sr=pps[1];pl=pwm[0];pr=pwm[1];sequence=ack;portEXIT_CRITICAL(&mux);
            int len=snprintf(buf,sizeof(buf),"T %s %u %" PRId64 " %" PRId64 " %" PRId64 " %.1f %.1f %.0f %.0f %u %d\n",LINK_TOKEN,boot_id,now,l,r,sl,sr,pl,pr,sequence,fault?1:0);
            sendto(s,buf,len,0,(struct sockaddr*)&host,sizeof(host));sent=now;
        }
        if(now-logged>1000000){ESP_LOGI("D0WD_LINK","wifi=%d fault=%d seq=%u pps=%.1f,%.1f pwm=%.0f,%.0f",connected,fault,ack,pps[0],pps[1],pwm[0],pwm[1]);logged=now;}
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}
void app_main(void){
    for(int i=0;i<4;i++){gpio_reset_pin(pins[i]);gpio_set_direction(pins[i],GPIO_MODE_OUTPUT);gpio_set_level(pins[i],0);}
    ledc_timer_config_t timer={.speed_mode=LEDC_LOW_SPEED_MODE,.duty_resolution=LEDC_TIMER_10_BIT,.timer_num=LEDC_TIMER_0,.freq_hz=1000,.clk_cfg=LEDC_AUTO_CLK};ESP_ERROR_CHECK(ledc_timer_config(&timer));
    for(int i=0;i<4;i++){ledc_channel_config_t c={.gpio_num=pins[i],.speed_mode=LEDC_LOW_SPEED_MODE,.channel=i,.timer_sel=LEDC_TIMER_0,.duty=0};ESP_ERROR_CHECK(ledc_channel_config(&c));}
    motor(0,0);motor(1,0);encoder(0,16,17);encoder(1,18,19);boot_id=esp_random();
    ESP_ERROR_CHECK(nvs_flash_init());ESP_ERROR_CHECK(esp_netif_init());ESP_ERROR_CHECK(esp_event_loop_create_default());esp_netif_create_default_wifi_sta();
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT();ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,event,NULL));ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,event,NULL));
    wifi_config_t cfg={0};strlcpy((char*)cfg.sta.ssid,WIFI_SSID,sizeof(cfg.sta.ssid));strlcpy((char*)cfg.sta.password,WIFI_PASSWORD,sizeof(cfg.sta.password));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&cfg));ESP_ERROR_CHECK(esp_wifi_start());esp_wifi_set_ps(WIFI_PS_NONE);
    xTaskCreate(control,"wheel_control",4096,NULL,8,NULL);xTaskCreate(network,"udp_link",6144,NULL,4,NULL);
    ESP_LOGI("D0WD_LINK","Independent UDP base; stop without fresh commands; server=" SERVER_IP ":9999");
}
