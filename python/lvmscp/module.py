import sys
import uuid

from clu.actor import AMQPClient
from cluplus.proxy import Proxy


# TODO: I really don't like this here, but keeping for now. If we keep this type
# of programmatic API it should in some separate repo lvmapi or something like it.


class API:
    @staticmethod
    def ping():

        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        try:
            result = lvmscp.ping()

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)
        return result

    @staticmethod
    def status():

        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        try:
            result = lvmscp.status()

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)
        return result

    @staticmethod
    def expose(
        exptime=0.0,
        Nexp=1,
        imtype=None,
        spectro="sp1",
        binning=1,
        shutter=True,
        metadata=None,
        ccdmodes=None,
    ):

        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        try:
            # 2 is the binning
            # '\'{"test": 1}\'' is the header data
            result = lvmscp.exposure(
                Nexp, imtype, exptime, spectro, binning, "'{\"test\": 1}'"
            )

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)
        return result

    @staticmethod
    def hartmann_set(str):
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        possible_list = ["left", "right", "both", "close"]

        result = None
        if str in possible_list:
            # sequential
            try:
                # 2 is the binning
                # '\'{"test": 1}\'' is the header data
                result = lvmscp.hartmann("set", str)

            except Exception as e:
                print(f"Exception: {e}")
                return

        print(result)

        return result

    @staticmethod
    def gage_set(ccd: str):
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        possible_list = ["r1", "b1", "z1"]

        result = None
        if ccd in possible_list:
            try:
                # 2 is the binning
                # '\'{"test": 1}\'' is the header data
                result = lvmscp.gage("setccd", ccd)

            except Exception as e:
                print(f"Exception: {e}")
                return

        return result

    @staticmethod
    def readout_set(readout: str):
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmscp = Proxy(amqpc, "lvmscp")
            lvmscp.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        possible_list = ["400", "800", "HDR"]

        result = None
        if readout in possible_list:
            try:
                # 2 is the binning
                # '\'{"test": 1}\'' is the header data
                result = lvmscp.readout(readout)

            except Exception as e:
                print(f"Exception: {e}")
                return

        return result

    @staticmethod
    def lvmnps_ping():
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmnps = Proxy(amqpc, "lvmnps")
            lvmnps.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        result = lvmnps.ping()
        try:
            result = lvmnps.ping()

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)
        return result

    @staticmethod
    def lvmieb_ping():
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmieb = Proxy(amqpc, "lvmieb")
            lvmieb.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        result = lvmieb.ping()
        try:
            result = lvmieb.ping()

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)
        return result

    @staticmethod
    def lamp_on(switch="DLI-03", portnum=None):
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmnps = Proxy(amqpc, "lvmnps")
            lvmnps.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        try:
            result = lvmnps.on(switch, portnum)

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)

        return result

    @staticmethod
    def lamp_off(switch="DLI-03", portnum=None):
        try:
            amqpc = AMQPClient(name=f"{sys.argv[0]}.proxy-{uuid.uuid4().hex[:8]}")

            lvmnps = Proxy(amqpc, "lvmnps")
            lvmnps.start()

        except Exception as e:
            print(f"Exception: {e}")
            return

        # sequential
        try:
            result = lvmnps.off(switch, portnum)

        except Exception as e:
            print(f"Exception: {e}")
            return

        print(result)

        return result
