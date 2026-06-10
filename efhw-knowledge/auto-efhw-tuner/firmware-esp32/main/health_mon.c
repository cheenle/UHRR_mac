/*
 * health_mon.c — Health monitor implementation
 */

#include "health_mon.h"
#include "servo_ctrl.h"
#include "protocol.h"
#include "ws_client.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "driver/temperature_sensor.h"

static const char *TAG = "health";
static sys_health_t health = SYS_HEALTHY;
static float bias_voltage = 0;
static adc_oneshot_unit_handle_t adc_handle = NULL;
static adc_cali_handle_t adc_cali = NULL;
static temperature_sensor_handle_t temp_sensor = NULL;

void health_mon_init(void) {
    /* ADC for Bias-T voltage monitoring */
    adc_oneshot_unit_init_cfg_t adc_cfg = {
        .unit_id = ADC_BIAS_V_UNIT,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&adc_cfg, &adc_handle));

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_BIAS_V_ATTEN,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(
        adc_handle, ADC_BIAS_V_CHANNEL, &chan_cfg));

    /* ADC calibration */
    adc_cali_line_fitting_config_t cali_cfg = {
        .unit_id = ADC_BIAS_V_UNIT,
        .atten = ADC_BIAS_V_ATTEN,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_cali_create_scheme_line_fitting(&cali_cfg, &adc_cali));

    /* Temperature sensor */
    temperature_sensor_config_t temp_cfg =
        TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    ESP_ERROR_CHECK(temperature_sensor_install(&temp_cfg, &temp_sensor));
    ESP_ERROR_CHECK(temperature_sensor_enable(temp_sensor));

    ESP_LOGI(TAG, "Health monitor initialized (ADC + temp sensor)");
}

void health_mon_tick(void) {
    bool degraded = false;

    /* Read Bias-T voltage */
    int raw_adc;
    ESP_ERROR_CHECK(adc_oneshot_read(adc_handle, ADC_BIAS_V_CHANNEL, &raw_adc));
    int voltage_mv;
    ESP_ERROR_CHECK(adc_cali_raw_to_voltage(adc_cali, raw_adc, &voltage_mv));
    bias_voltage = (float)voltage_mv * ADC_BIAS_V_DIVIDER / 1000.0f;

    if (bias_voltage < BIAS_V_MIN || bias_voltage > BIAS_V_MAX) {
        ESP_LOGW(TAG, "Bias voltage out of range: %.1fV", bias_voltage);
        degraded = true;
        const char *msg = (bias_voltage < BIAS_V_MIN) ?
            "DC under-voltage" : "DC over-voltage";
        char *json = proto_build_health_alert(1, bias_voltage, msg);
        if (json) { ws_client_send(json); free(json); }
    }

    /* Read core temperature */
    float temp_c;
    ESP_ERROR_CHECK(temperature_sensor_get_celsius(temp_sensor, &temp_c));
    if (temp_c > CORE_TEMP_MAX_C) {
        ESP_LOGW(TAG, "Core temp high: %.1f°C", temp_c);
        degraded = true;
    }

    /* Update health FSM */
    if (degraded && health == SYS_HEALTHY) {
        health = SYS_DEGRADED;
    } else if (!degraded && health == SYS_DEGRADED) {
        health = SYS_HEALTHY;
    }
}

sys_health_t health_get_state(void) {
    return health;
}

float health_get_bias_voltage(void) {
    return bias_voltage;
}
