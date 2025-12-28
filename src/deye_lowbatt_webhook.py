import argparse
import sys
import time

import urllib3

from deye_config import DeyeConfig, DeyeLoggerConfig
from deye_connector_factory import DeyeConnectorFactory
from deye_modbus import DeyeModbus

http = urllib3.PoolManager(retries=10, timeout=10)


def read_register(modbus, reg, signed=False, multiplier=None):
    reg_address = reg
    registers = modbus.read_registers(reg_address, reg_address)
    if registers is None:
        raise Exception("no registers read")
    if reg_address not in registers:
        raise Exception(f"register {reg_address} not read")
    reg_bytes = registers[reg_address]
    reg_value_int = int.from_bytes(reg_bytes, "big", signed=signed)
    if multiplier is None:
        return reg_value_int
    else:
        return reg_value_int / multiplier


def send_requests(urls):
    for url in urls:
        try:
            print(f"Calling {url}")
            http.request("GET", url)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Send a GET request when off-grid & battery is low.")
    parser.add_argument("ip_address", type=str, help="IP address of the device.")
    parser.add_argument("serial_number", type=int, help="Serial number of the device.")
    parser.add_argument("--low_soc", type=int, default=10, help="SOC percentage at which the requests will be sent.")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds.")
    parser.add_argument("--url_trigger", action="extend", nargs="+", type=str, help="Destination URLs to be called when the SoC is equal or less than the value specified in --low_soc.")
    parser.add_argument("--url_restore", action="extend", nargs="+", type=str, help="Destination URLs to be called when the battery starts charging.")
    args = parser.parse_args()
    config = DeyeConfig(
        logger_configs=[DeyeLoggerConfig(
            serial_number=args.serial_number,
            ip_address=args.ip_address,
            port=0,
            protocol="tcp",
            max_register_range_length=256,
        )],
        mqtt=[],
        log_level="DEBUG",
        log_stream=sys.stdout,
        data_read_inverval=60,
        publish_on_change=False,
        event_expiry=360,
        metric_groups=[],
        active_processors=[],
        active_command_handlers=[],
        plugins_dir="",
        plugins_enabled=[],
    )
    logger_config = config.logger
    connector = DeyeConnectorFactory().create_connector(logger_config)
    modbus = DeyeModbus(connector)
    trigger_webhook_called = False
    restore_webhook_called = False
    prev_current = None
    while True:
        try:
            soc = read_register(modbus, 588)
            current = read_register(modbus, 591, signed=True, multiplier=100)
            if soc <= args.low_soc and current >= 0 and not trigger_webhook_called:
                send_requests(args.url_trigger)
                trigger_webhook_called = True
                restore_webhook_called = False
            elif prev_current is not None and current < 0 and not restore_webhook_called:
                send_requests(args.url_restore)
                restore_webhook_called = True
                trigger_webhook_called = False
            prev_current = current

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
