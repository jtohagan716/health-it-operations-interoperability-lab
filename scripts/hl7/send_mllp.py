import argparse
import socket
import sys
import time
from pathlib import Path


MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"


def load_hl7_fixture(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")

    segments = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not segments:
        raise ValueError("HL7 fixture is empty.")

    if not segments[0].startswith("MSH|"):
        raise ValueError("First HL7 segment must be MSH.")

    return segments


def get_message_control_id(segments: list[str]) -> str:
    msh_fields = segments[0].split("|")

    if len(msh_fields) <= 9:
        raise ValueError("MSH-10 message control ID is missing.")

    control_id = msh_fields[9].strip()

    if not control_id:
        raise ValueError("MSH-10 message control ID is blank.")

    return control_id


def build_mllp_frame(segments: list[str]) -> bytes:
    hl7_message = "\r".join(segments) + "\r"

    return (
        MLLP_START
        + hl7_message.encode("utf-8")
        + MLLP_END
    )


def receive_mllp_message(sock: socket.socket) -> bytes:
    received = bytearray()

    while MLLP_END not in received:
        chunk = sock.recv(4096)

        if not chunk:
            break

        received.extend(chunk)

    if not received:
        raise RuntimeError("Connection closed without an ACK.")

    return bytes(received)


def remove_mllp_frame(data: bytes) -> str:
    if data.startswith(MLLP_START):
        data = data[1:]

    if data.endswith(MLLP_END):
        data = data[:-2]

    return data.decode("utf-8").strip("\r\n")


def send_mllp_frame(
    frame: bytes,
    host: str = "localhost",
    port: int = 6661,
    timeout: float = 30.0,
) -> bytes:
    with socket.create_connection(
        (host, port),
        timeout=timeout,
    ) as sock:
        sock.settimeout(timeout)
        sock.sendall(frame)

        return receive_mllp_message(sock)


def parse_ack(ack_text: str) -> tuple[str, str]:
    segments = ack_text.replace("\n", "\r").split("\r")

    msa = next(
        (
            segment
            for segment in segments
            if segment.startswith("MSA|")
        ),
        None,
    )

    if msa is None:
        raise ValueError("ACK does not contain an MSA segment.")

    fields = msa.split("|")

    ack_code = fields[1] if len(fields) > 1 else ""
    control_id = fields[2] if len(fields) > 2 else ""

    return ack_code, control_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send an HL7 v2 message using MLLP."
    )

    parser.add_argument(
        "--fixture",
        required=True,
        type=Path,
        help="Path to the source-controlled HL7 fixture.",
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="MLLP listener host. Default: localhost",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=6661,
        help="MLLP listener port. Default: 6661",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Socket timeout in seconds. Default: 30",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and frame the message without "
            "opening a network connection."
        ),
    )

    args = parser.parse_args()

    try:
        segments = load_hl7_fixture(args.fixture)
        control_id = get_message_control_id(segments)
        frame = build_mllp_frame(segments)

        print(f"Fixture:            {args.fixture}")
        print(f"Segments:           {len(segments)}")
        print(f"Message control ID: {control_id}")
        print(f"HL7 payload bytes:  {len(frame) - 3}")
        print(f"MLLP frame bytes:   {len(frame)}")
        print("MLLP start byte:    0x0B")
        print("MLLP end bytes:     0x1C 0x0D")

        if args.dry_run:
            print("Dry run:            PASS")
            return 0

        print(f"Connecting to:      {args.host}:{args.port}")

        start_time = time.perf_counter()

        response = send_mllp_frame(
            frame,
            host=args.host,
            port=args.port,
            timeout=args.timeout,
        )

        elapsed = time.perf_counter() - start_time

        ack_text = remove_mllp_frame(response)
        ack_code, ack_control_id = parse_ack(ack_text)

        print()
        print("ACK received:")
        print(ack_text.replace("\r", "\n"))
        print()
        print(f"ACK code:                   {ack_code}")
        print(f"ACK control ID:             {ack_control_id}")
        print(f"ACK round-trip:             {elapsed:.3f} seconds")

        if ack_control_id != control_id:
            print(
                "Control ID reconciliation: FAIL "
                f"(expected {control_id})"
            )
            return 2

        print("Control ID reconciliation: PASS")

        if ack_code != "AA":
            print(
                "Application result:         FAIL "
                f"(ACK code {ack_code})"
            )
            return 3

        print("Application result:         PASS")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())