import argparse
import datetime
import json
import os
import sys
import tempfile
import time

from deye_config import DeyeConfig, DeyeLoggerConfig
from deye_connector_factory import DeyeConnectorFactory
from deye_modbus import DeyeModbus


def main():
    parser = argparse.ArgumentParser(description="Get Deye stats.")
    parser.add_argument("ip_address", type=str, help="IP address of the device.")
    parser.add_argument("serial_number", type=int, help="Serial number of the device.")
    parser.add_argument("output", type=str, help="Destination JSON file.")
    parser.add_argument("--interval", type=int, default=10, help="Update interval in seconds.")
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
    while True:
        results = modbus.read_registers(586, 646)
        if results is None:
            raise Exception("no registers read")
        try:
            grid_power = [
                int.from_bytes(results[604], "big"),
                int.from_bytes(results[605], "big"),
                int.from_bytes(results[606], "big"),
            ]

            data = {
                "ts": int(datetime.datetime.now().timestamp() * 1000),
                "battery": {
                    "soc": int.from_bytes(results[588], "big"),
                    "current": int.from_bytes(results[591], "big", signed=True) / 100,
                    "voltage": int.from_bytes(results[587], "big") / 10,
                    "temp": int.from_bytes(results[586], "big") / 100,
                },
                "grid": {
                    "voltage": {
                        "a": int.from_bytes(results[598], "big") / 10,
                        "b": int.from_bytes(results[599], "big") / 10,
                        "c": int.from_bytes(results[600], "big") / 10,
                    },
                    "power": {
                        "a": grid_power[0],
                        "b": grid_power[1],
                        "c": grid_power[2],
                        "total": grid_power[0] + grid_power[1] + grid_power[2],
                    },
                },
                "inverter": {
                    "voltage": {
                        "a": int.from_bytes(results[644], "big") / 10,
                        "b": int.from_bytes(results[645], "big") / 10,
                        "c": int.from_bytes(results[646], "big") / 10,
                    },
                    "power": {
                        "a": int.from_bytes(results[640], "big"),
                        "b": int.from_bytes(results[641], "big"),
                        "c": int.from_bytes(results[642], "big"),
                        "total": int.from_bytes(results[643], "big"),
                    },
                },
            }

            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                json.dump(data, tmp, indent=2)
            os.chmod(tmp.name, 0o0644)
            os.replace(tmp.name, args.output)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
